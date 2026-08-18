import { normalizeAppearance } from "./appearance";
import {
  createChatUi,
  DEFAULT_APPEARANCE,
  type ChatUi,
  type PublicAgentActivity,
  type SurfaceAppearance,
} from "./chat-ui";
import {
  PROTOCOL_VERSION,
  isHostMessage,
  type FrameEventType,
} from "./protocol";
import { randomUuid } from "./random-uuid";
import "./styles.css";

interface SurfaceConfiguration {
  surface_id: string;
  name: string;
  appearance: SurfaceAppearance;
  protocol_version: number;
}

class SessionExpiredError extends Error {
  constructor() {
    super("Session expired");
    this.name = "SessionExpiredError";
  }
}

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
let ui: ChatUi | null = null;

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

function ensureUi(nextAppearance = appearance): ChatUi {
  appearance = normalizeAppearance(nextAppearance);
  if (!ui) {
    ui = createChatUi(root, appearance, {
      onSubmit(message) {
        void sendMessage(message);
      },
    });
  } else {
    ui.setAppearance(appearance);
  }
  return ui;
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
  if (response.status === 401) {
    ensureUi().showSessionExpired();
    emit("session.expired");
    throw new SessionExpiredError();
  }
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
  const items = Array.isArray(payload.data?.items) ? payload.data.items : [];
  const chatUi = ensureUi();
  chatUi.clearMessages();

  for (const item of items) {
    if (typeof item?.role === "string" && typeof item?.content === "string") {
      if (item.role === "user" || item.role === "assistant") {
        chatUi.appendMessage(item.role, item.content);
      }
    }
  }
  if (items.length === 0 && appearance.welcome_message) {
    chatUi.appendMessage("assistant", appearance.welcome_message);
  }
  chatUi.scrollToLatest(true);
  emit("history.loaded", { count: items.length });
}

function appendError(error: unknown) {
  if (error instanceof SessionExpiredError) return;
  const text = error instanceof Error ? error.message : "Run failed";
  ensureUi().appendError(text);
  emit("error", { message: text });
}

async function bootstrap() {
  if (bootstrapping || initialized) return;
  bootstrapping = true;
  try {
    const configuration = await loadConfiguration();
    appearance = normalizeAppearance(configuration.appearance);
    ensureUi(appearance).clearSessionExpired();
    await loadHistory();
    initialized = true;
  } catch (error) {
    ensureUi(DEFAULT_APPEARANCE);
    appendError(error);
  } finally {
    bootstrapping = false;
  }
}

function publicActivity(data: unknown): PublicAgentActivity | null {
  if (!data || typeof data !== "object" || Array.isArray(data)) return null;
  const value = data as Record<string, unknown>;
  const nested = value.data && typeof value.data === "object" && !Array.isArray(value.data)
    ? (value.data as Record<string, unknown>)
    : value;
  const status = typeof nested.status === "string" ? nested.status : undefined;
  const toolName = typeof nested.tool_name === "string" ? nested.tool_name : undefined;
  if (!status) return null;
  return { status, tool_name: toolName };
}

async function sendMessage(message: string) {
  if (submitting) return;
  const chatUi = ensureUi();
  submitting = true;
  chatUi.clearComposer();
  chatUi.appendMessage("user", message, true);
  const assistant = chatUi.appendPendingAssistant();
  chatUi.setSubmitting(true);
  emit("message.sent");
  emit("run.started");

  let answer = "";
  let streamingStarted = false;

  try {
    const response = await api(`/v1/chat/sessions/${sessionId}/messages:stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": randomUuid(),
      },
      body: JSON.stringify({ message }),
    });
    const reader = response.body?.getReader();
    if (!reader) throw new Error("Streaming is not available");

    const decoder = new TextDecoder();
    let buffer = "";

    const beginStreaming = () => {
      if (streamingStarted) return;
      streamingStarted = true;
      chatUi.beginAssistantStreaming(assistant);
    };

    const consumeFrame = (frame: string) => {
      const lines = frame.split("\n");
      const eventLine = lines.find((line) => line.startsWith("event:"));
      const dataLine = lines.find((line) => line.startsWith("data:"));
      if (!dataLine) return;
      const eventType = eventLine?.slice(6).trim();
      const data = JSON.parse(dataLine.slice(5).trim());

      if (eventType === "agent_activity" || data.type === "agent_activity") {
        const activity = publicActivity(data);
        if (activity) {
          const label = chatUi.updateAssistantActivity(assistant, activity);
          emit("run.activity", {
            status: activity.status,
            message: label || undefined,
          });
        }
        return;
      }

      const token =
        typeof data.token === "string"
          ? data.token
          : typeof data.content === "string"
            ? data.content
            : typeof data.data?.content === "string"
              ? data.data.content
              : "";

      if ((eventType === "token" || data.type === "token") && token) {
        beginStreaming();
        answer += token;
        chatUi.updateAssistantStreaming(assistant, answer);
      }

      if (data.type === "done" && typeof data.answer === "string" && !answer) {
        beginStreaming();
        answer = data.answer;
        chatUi.updateAssistantStreaming(assistant, answer);
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

    if (!answer) {
      chatUi.removeMessage(assistant);
      throw new Error("The Run completed without a response");
    }

    chatUi.finishAssistantStreaming(assistant);
    emit("run.completed");
  } catch (error) {
    if (!answer) chatUi.removeMessage(assistant);
    else chatUi.finishAssistantStreaming(assistant);
    appendError(error);
  } finally {
    submitting = false;
    chatUi.setSubmitting(false);
    chatUi.focusComposer();
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
    ensureUi().clearSessionExpired();
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
