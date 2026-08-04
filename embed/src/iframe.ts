import {
  PROTOCOL_VERSION,
  isHostMessage,
  type FrameEventType,
} from "./protocol";
import "./styles.css";

interface SurfaceAppearance {
  theme: "light" | "dark" | "system";
  primary_color: string;
  title: string;
  placeholder: string;
  welcome_message: string | null;
}

interface SurfaceConfiguration {
  surface_id: string;
  name: string;
  appearance: SurfaceAppearance;
  protocol_version: number;
}

const DEFAULT_APPEARANCE: SurfaceAppearance = {
  theme: "system",
  primary_color: "#5B47E0",
  title: "Woobe",
  placeholder: "Type a message…",
  welcome_message: null,
};

const params = new URLSearchParams(window.location.search);
const surfaceId = params.get("surface") ?? "";
const instanceId = params.get("instance") ?? "";
const rootElement = document.querySelector<HTMLElement>("#woobe-chat");

if (!rootElement || !surfaceId || !instanceId || window.parent === window) {
  throw new Error("Invalid Woobe Chat iframe bootstrap");
}
const root = rootElement;

let parentOrigin: string | null = null;
let hostOrigin = "";
let apiBaseUrl = "";
let sessionToken = "";
let sessionId = "";
let appearance = DEFAULT_APPEARANCE;
let submitting = false;
let initialized = false;
let bootstrapping = false;

function emit(type: FrameEventType, payload?: unknown) {
  if (!parentOrigin) return;
  window.parent.postMessage(
    {
      protocolVersion: PROTOCOL_VERSION,
      instanceId,
      surfaceId,
      type,
      payload,
    },
    parentOrigin,
  );
}

function decodeSessionId(token: string): string {
  const payload = token.split(".")[1];
  if (!payload) throw new Error("Invalid Session token");
  const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
  const decoded = JSON.parse(
    atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=")),
  );
  if (typeof decoded.sid !== "string") throw new Error("Invalid Session token");
  return decoded.sid;
}

function messageElement(role: string, content: string): HTMLElement {
  const item = document.createElement("article");
  item.className = `message message--${role}`;
  item.textContent = content;
  return item;
}

function messagesElement(): HTMLElement | null {
  return root.querySelector<HTMLElement>(".chat__messages");
}

function scrollToLatest() {
  const messages = messagesElement();
  if (messages) messages.scrollTop = messages.scrollHeight;
}

function setSubmitting(value: boolean) {
  submitting = value;
  const input = root.querySelector<HTMLTextAreaElement>("textarea");
  const button = root.querySelector<HTMLButtonElement>("button[type='submit']");
  if (input) input.disabled = value;
  if (button) {
    button.disabled = value;
    button.textContent = value ? "Sending…" : "Send";
  }
}

function applyAppearance(next: SurfaceAppearance) {
  appearance = next;
  root.dataset.theme = next.theme;
  root.style.setProperty("--woobe-primary", next.primary_color);
  document.title = next.title;
}

function renderShell(next: SurfaceAppearance) {
  applyAppearance(next);
  root.innerHTML = `
    <section class="chat">
      <header class="chat__header"></header>
      <div class="chat__messages" role="log" aria-label="Conversation" aria-live="polite"></div>
      <form class="chat__composer">
        <label class="sr-only" for="woobe-message">Message</label>
        <textarea id="woobe-message" rows="1" maxlength="32768" required></textarea>
        <button type="submit">Send</button>
      </form>
    </section>
  `;
  const header = root.querySelector<HTMLElement>(".chat__header");
  const input = root.querySelector<HTMLTextAreaElement>("textarea");
  if (header) header.textContent = next.title;
  if (input) input.placeholder = next.placeholder;
  root.querySelector("form")?.addEventListener("submit", onSubmit);
}

async function api(path: string, init: RequestInit = {}) {
  const response = await fetch(`${apiBaseUrl}${path}`, {
    ...init,
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${sessionToken}`,
      "X-Woobe-Host-Origin": hostOrigin,
      ...(init.headers ?? {}),
    },
  });
  if (response.status === 401) emit("session.expired");
  if (!response.ok) throw new Error(`Woobe Chat request failed (${response.status})`);
  return response;
}

async function loadConfiguration(): Promise<SurfaceConfiguration> {
  const response = await api(`/v1/chat/sessions/${sessionId}/surface`);
  const payload = await response.json();
  const configuration = payload.data as SurfaceConfiguration | undefined;
  if (
    !configuration ||
    configuration.surface_id !== surfaceId ||
    configuration.protocol_version !== PROTOCOL_VERSION
  ) {
    throw new Error("Invalid ChatSurface configuration");
  }
  return configuration;
}

async function loadHistory() {
  const response = await api(`/v1/chat/sessions/${sessionId}/messages?limit=50`);
  const payload = await response.json();
  const messages = messagesElement();
  const items = Array.isArray(payload.data?.items) ? payload.data.items : [];
  for (const item of items) {
    if (typeof item?.role === "string" && typeof item?.content === "string") {
      messages?.appendChild(messageElement(item.role, item.content));
    }
  }
  if (items.length === 0 && appearance.welcome_message) {
    messages?.appendChild(
      messageElement("assistant", appearance.welcome_message),
    );
  }
  scrollToLatest();
  emit("history.loaded", { count: items.length });
}

function appendError(error: unknown) {
  const text = error instanceof Error ? error.message : "Run failed";
  messagesElement()?.appendChild(messageElement("assistant", text));
  scrollToLatest();
  emit("error", { message: text });
}

async function bootstrap() {
  if (bootstrapping || initialized) return;
  bootstrapping = true;
  try {
    const configuration = await loadConfiguration();
    renderShell(configuration.appearance);
    await loadHistory();
    initialized = true;
  } catch (error) {
    renderShell(DEFAULT_APPEARANCE);
    appendError(error);
  } finally {
    bootstrapping = false;
  }
}

async function onSubmit(event: Event) {
  event.preventDefault();
  if (submitting) return;

  const input = root.querySelector<HTMLTextAreaElement>("textarea");
  const messages = messagesElement();
  const message = input?.value.trim() ?? "";
  if (!message || !input) return;

  input.value = "";
  messages?.appendChild(messageElement("user", message));
  scrollToLatest();
  setSubmitting(true);
  emit("message.sent");
  emit("run.started");

  try {
    const response = await api(`/v1/chat/sessions/${sessionId}/messages:stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": crypto.randomUUID(),
      },
      body: JSON.stringify({ message }),
    });
    const reader = response.body?.getReader();
    if (!reader) throw new Error("Streaming is not available");

    const decoder = new TextDecoder();
    let buffer = "";
    let answer = "";
    const assistant = messageElement("assistant", "");
    messages?.appendChild(assistant);

    const consumeFrame = (frame: string) => {
      const lines = frame.split("\n");
      const eventLine = lines.find((line) => line.startsWith("event:"));
      const dataLine = lines.find((line) => line.startsWith("data:"));
      if (!dataLine) return;
      const eventType = eventLine?.slice(6).trim();
      const data = JSON.parse(dataLine.slice(5).trim());
      const token =
        typeof data.token === "string"
          ? data.token
          : typeof data.content === "string"
            ? data.content
            : typeof data.data?.content === "string"
              ? data.data.content
              : "";
      if ((eventType === "token" || data.type === "token") && token) {
        answer += token;
        assistant.textContent = answer;
        scrollToLatest();
      }
      if (data.type === "done" && typeof data.answer === "string" && !answer) {
        assistant.textContent = data.answer;
        scrollToLatest();
      }
      if (
        data.type === "error" ||
        eventType === "execution_failed" ||
        eventType === "execution_timed_out" ||
        eventType === "execution_cancelled"
      ) {
        throw new Error(data.message ?? data.data?.message ?? "Run failed");
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) consumeFrame(frame);
    }
    buffer += decoder.decode();
    if (buffer.trim()) consumeFrame(buffer);
    emit("run.completed");
  } catch (error) {
    appendError(error);
  } finally {
    setSubmitting(false);
    input.focus();
  }
}

window.addEventListener("message", async (event) => {
  if (event.source !== window.parent || !isHostMessage(event.data)) return;
  if (
    event.data.instanceId !== instanceId ||
    event.data.surfaceId !== surfaceId ||
    (parentOrigin !== null && event.origin !== parentOrigin)
  ) {
    return;
  }

  if (event.data.type === "init") {
    if (parentOrigin !== null) return;
    if (event.data.payload.hostOrigin !== event.origin) return;
    parentOrigin = event.origin;
    hostOrigin = event.data.payload.hostOrigin;
    apiBaseUrl = new URL(event.data.payload.apiBaseUrl).origin;
    sessionToken = event.data.payload.token;
    sessionId = decodeSessionId(sessionToken);
    await bootstrap();
  } else if (event.data.type === "token.update") {
    const nextSessionId = decodeSessionId(event.data.payload.token);
    if (sessionId && nextSessionId !== sessionId) {
      emit("error", {
        message: "Session token cannot replace the mounted ChatSurface Session",
      });
      return;
    }
    sessionToken = event.data.payload.token;
    sessionId = nextSessionId;
    await bootstrap();
  } else if (event.data.type === "open") {
    emit("opened");
  } else if (event.data.type === "close") {
    emit("closed");
  }
});

window.parent.postMessage(
  {
    protocolVersion: PROTOCOL_VERSION,
    instanceId,
    surfaceId,
    type: "ready",
  },
  "*",
);
