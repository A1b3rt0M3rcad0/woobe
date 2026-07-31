import {
  PROTOCOL_VERSION,
  isHostMessage,
  type FrameEventType,
} from "./protocol";
import "./styles.css";

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
  const decoded = JSON.parse(atob(normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=")));
  if (typeof decoded.sid !== "string") throw new Error("Invalid Session token");
  return decoded.sid;
}

function messageElement(role: string, content: string): HTMLElement {
  const item = document.createElement("article");
  item.className = `message message--${role}`;
  item.textContent = content;
  return item;
}

function renderShell() {
  root.innerHTML = `
    <section class="chat">
      <header class="chat__header">Woobe</header>
      <div class="chat__messages" role="log" aria-label="Conversation"></div>
      <form class="chat__composer">
        <label class="sr-only" for="woobe-message">Message</label>
        <textarea id="woobe-message" rows="1" maxlength="32768" placeholder="Type a message…" required></textarea>
        <button type="submit">Send</button>
      </form>
    </section>
  `;
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

async function loadHistory() {
  const response = await api(`/v1/chat/sessions/${sessionId}/messages?limit=50`);
  const payload = await response.json();
  const messages = root?.querySelector<HTMLElement>(".chat__messages");
  for (const item of payload.data?.items ?? []) {
    messages?.appendChild(messageElement(item.role, item.content));
  }
  emit("history.loaded");
}

async function onSubmit(event: Event) {
  event.preventDefault();
  const input = root?.querySelector<HTMLTextAreaElement>("textarea");
  const messages = root?.querySelector<HTMLElement>(".chat__messages");
  const message = input?.value.trim() ?? "";
  if (!message || !input) return;
  input.value = "";
  messages?.appendChild(messageElement("user", message));
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
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const eventLine = frame
          .split("\n")
          .find((line) => line.startsWith("event:"));
        const dataLine = frame.split("\n").find((line) => line.startsWith("data:"));
        if (!dataLine) continue;
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
        }
        if (data.type === "done" && typeof data.answer === "string" && !answer) {
          assistant.textContent = data.answer;
        }
        if (
          data.type === "error" ||
          eventType === "execution_failed" ||
          eventType === "execution_timed_out" ||
          eventType === "execution_cancelled"
        ) {
          throw new Error(data.message ?? data.data?.message ?? "Run failed");
        }
      }
    }
    emit("run.completed");
  } catch (error) {
    const message = error instanceof Error ? error.message : "Run failed";
    messages?.appendChild(messageElement("assistant", message));
    emit("error", { message });
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
    renderShell();
    try {
      await loadHistory();
    } catch (error) {
      emit("error", { message: String(error) });
    }
  } else if (event.data.type === "token.update") {
    sessionToken = event.data.payload.token;
    sessionId = decodeSessionId(sessionToken);
  } else if (event.data.type === "open") {
    emit("opened");
  } else if (event.data.type === "close") {
    emit("closed");
  } else if (event.data.type === "destroy") {
    root?.replaceChildren();
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
