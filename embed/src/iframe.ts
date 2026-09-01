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
import {
  RuntimeStreamGapError,
  acceptRuntimeFrameSequence,
  parseRuntimeFrame,
  runtimeTerminalStatus,
  type ParsedRuntimeFrame,
  type RuntimeSequenceState,
  type RuntimeTerminalStatus,
} from "./runtime-stream";
import "./styles.css";

interface SurfaceConfiguration {
  surface_id: string;
  name: string;
  appearance: SurfaceAppearance;
  protocol_version: number;
}

interface ActiveRun {
  message_request_id: string | null;
  run_id: string | null;
  status: string;
  target_type: "agent" | "network";
}

interface RuntimeObserverState {
  assistant: HTMLElement;
  answer: string;
  streamingStarted: boolean;
  sequence: RuntimeSequenceState;
  terminalStatus: RuntimeTerminalStatus | null;
}

class SessionExpiredError extends Error {
  constructor() {
    super("Session expired");
    this.name = "SessionExpiredError";
  }
}

class ChatApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly data: unknown,
  ) {
    super(message);
    this.name = "ChatApiError";
  }
}

class RuntimeTerminalError extends Error {
  constructor(message: string, readonly status: RuntimeTerminalStatus) {
    super(message);
    this.name = "RuntimeTerminalError";
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
let stopping = false;
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
      onStop() {
        void requestCancel();
      },
    });
  } else {
    ui.setAppearance(appearance);
  }
  return ui;
}

function setStoppingState(next: boolean) {
  if (stopping === next) return;
  stopping = next;
  ensureUi().setStopping(next);
}

function restoreActiveRunState(active: ActiveRun) {
  const cancellationPending = active.status === "cancel_requested";
  stopping = cancellationPending;
  ensureUi().setStopping(cancellationPending);
  if (cancellationPending) {
    emit("run.stopping", { resumed: true, runId: active.run_id });
  }
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
  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    const body = payload && typeof payload === "object" && !Array.isArray(payload)
      ? (payload as Record<string, unknown>)
      : null;
    const message = typeof body?.message === "string"
      ? body.message
      : `Woobe Chat request failed (${response.status})`;
    throw new ChatApiError(message, response.status, body?.data ?? null);
  }
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

async function loadActiveRun(): Promise<ActiveRun | null> {
  const response = await api(`/v1/chat/sessions/${sessionId}/active-run`);
  const payload = await response.json();
  const active = payload.data as ActiveRun | null | undefined;
  return active?.run_id ? active : null;
}

async function recoverAcceptedActiveRun(): Promise<ActiveRun | null> {
  return loadActiveRun();
}

function activeRunFromConflict(error: unknown): ActiveRun | null {
  if (!(error instanceof ChatApiError) || error.status !== 409) return null;
  if (!error.data || typeof error.data !== "object" || Array.isArray(error.data)) {
    return null;
  }
  const data = error.data as Record<string, unknown>;
  if (
    data.code !== "active_run_conflict"
    || typeof data.run_id !== "string"
    || typeof data.status !== "string"
    || (data.target_type !== "agent" && data.target_type !== "network")
  ) {
    return null;
  }
  return {
    message_request_id: null,
    run_id: data.run_id,
    status: data.status,
    target_type: data.target_type,
  };
}

function appendError(error: unknown) {
  if (error instanceof SessionExpiredError) return;
  const text = error instanceof Error ? error.message : "Run failed";
  ensureUi().appendError(text);
  emit("error", { message: text });
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

function createRuntimeObserver(): RuntimeObserverState {
  return {
    assistant: ensureUi().appendPendingAssistant(),
    answer: "",
    streamingStarted: false,
    sequence: { sequence: null },
    terminalStatus: null,
  };
}

function beginStreaming(observer: RuntimeObserverState) {
  if (observer.streamingStarted) return;
  observer.streamingStarted = true;
  ensureUi().beginAssistantStreaming(observer.assistant);
}

function replaceAnswer(observer: RuntimeObserverState, content: string) {
  beginStreaming(observer);
  observer.answer = content;
  ensureUi().updateAssistantStreaming(observer.assistant, observer.answer);
}

function applyRuntimeFrame(
  parsed: ParsedRuntimeFrame,
  observer: RuntimeObserverState,
): RuntimeTerminalStatus | null {
  if (!acceptRuntimeFrameSequence(parsed, observer.sequence)) return null;

  const { eventType, data, payload } = parsed;
  if (eventType === "run.state") {
    replaceAnswer(observer, typeof payload.output === "string" ? payload.output : "");
    if (payload.status === "cancel_requested") {
      const wasStopping = stopping;
      setStoppingState(true);
      if (!wasStopping) emit("run.stopping", { resumed: true });
    }
  } else if (eventType === "agent_activity" || data.type === "agent_activity") {
    const activity = publicActivity(data);
    if (activity) {
      const label = ensureUi().updateAssistantActivity(observer.assistant, activity);
      emit("run.activity", {
        status: activity.status,
        message: label || undefined,
      });
    }
  } else {
    const token =
      typeof data.token === "string"
        ? data.token
        : typeof data.content === "string"
          ? data.content
          : typeof payload.content === "string"
            ? payload.content
            : "";

    if ((eventType === "token" || data.type === "token") && token) {
      beginStreaming(observer);
      observer.answer += token;
      ensureUi().updateAssistantStreaming(observer.assistant, observer.answer);
    }

    if (eventType === "token_retract" || data.type === "token_retract") {
      const length = typeof payload.content_length === "number" ? payload.content_length : 0;
      if (length > 0) {
        replaceAnswer(
          observer,
          observer.answer.slice(0, Math.max(0, observer.answer.length - length)),
        );
      }
    }

    if (eventType === "done" && typeof data.answer === "string") {
      replaceAnswer(observer, data.answer);
    }

    if (
      (eventType === "cancelled" || eventType === "execution_cancelled")
      && typeof payload.output === "string"
    ) {
      replaceAnswer(observer, payload.output);
    }
  }

  const terminal = runtimeTerminalStatus(parsed);
  if (terminal !== null) observer.terminalStatus = terminal;
  return terminal;
}

async function consumeRuntimeStream(
  response: Response,
  observer: RuntimeObserverState,
): Promise<RuntimeTerminalStatus | null> {
  const reader = response.body?.getReader();
  if (!reader) throw new Error("Streaming is not available");
  const decoder = new TextDecoder();
  let buffer = "";

  const consumeFrame = (frame: string) => {
    const parsed = parseRuntimeFrame(frame);
    if (!parsed) return;
    applyRuntimeFrame(parsed, observer);
  };

  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      if (observer.terminalStatus !== null) {
        // A terminal frame is authoritative, but the HTTP body still needs to be
        // drained until EOF. Cancelling the Fetch reader here aborts the server-side
        // StreamingResponse while ChatSurface finalization may still be committing.
        continue;
      }
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split(/\r?\n\r?\n/);
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        consumeFrame(frame);
        if (observer.terminalStatus !== null) break;
      }
    }
    if (observer.terminalStatus === null) {
      buffer += decoder.decode();
      if (buffer.trim()) consumeFrame(buffer);
    }
    return observer.terminalStatus;
  } catch (error) {
    await reader.cancel().catch(() => undefined);
    throw error;
  }
}

function finalizeObserver(
  observer: RuntimeObserverState,
  terminal: RuntimeTerminalStatus,
  resumed: boolean,
) {
  const chatUi = ensureUi();
  if (!observer.answer) {
    chatUi.removeMessage(observer.assistant);
  } else {
    chatUi.finishAssistantStreaming(observer.assistant);
  }

  if (terminal === "completed") {
    if (!observer.answer && !resumed) {
      throw new Error("The Run completed without a response");
    }
    emit("run.completed", { resumed });
    return;
  }

  if (terminal === "cancelled") {
    chatUi.appendStatus("Stopped");
    emit("run.cancelled", {
      resumed,
      partial: Boolean(observer.answer),
    });
    return;
  }

  throw new RuntimeTerminalError(
    terminal === "timed_out"
      ? "Run timed out"
      : terminal === "uncertain"
        ? "Run outcome is uncertain"
        : "Run failed",
    terminal,
  );
}

function retryDelay(attempt: number): Promise<void> {
  return new Promise((resolve) => window.setTimeout(resolve, 250 * (attempt + 1)));
}

async function observeRuntimeRun(
  firstResponse: Response,
  options: { resumed: boolean },
): Promise<void> {
  const { resumed } = options;
  const observer = createRuntimeObserver();
  let response = firstResponse;
  let lastTransportError: unknown = null;

  for (let attempt = 0; attempt < 4; attempt += 1) {
    try {
      const terminal = await consumeRuntimeStream(response, observer);
      if (terminal !== null) {
        finalizeObserver(observer, terminal, resumed);
        return;
      }
      lastTransportError = new Error("Runtime stream ended before a terminal event");
    } catch (error) {
      if (error instanceof SessionExpiredError || error instanceof RuntimeTerminalError) {
        throw error;
      }
      if (!(error instanceof RuntimeStreamGapError) && !(error instanceof Error)) {
        throw error;
      }
      lastTransportError = error;
    }

    if (attempt === 3) break;
    await retryDelay(attempt);
    response = await api(`/v1/chat/sessions/${sessionId}/active-run/stream`);
  }

  if (!observer.answer) ensureUi().removeMessage(observer.assistant);
  else ensureUi().finishAssistantStreaming(observer.assistant);
  throw lastTransportError instanceof Error
    ? lastTransportError
    : new Error("Active Run reattach failed");
}

async function requestCancel() {
  if (!submitting || stopping || !sessionId) return;
  const chatUi = ensureUi();
  setStoppingState(true);
  emit("run.stopping");
  try {
    await api(`/v1/chat/sessions/${sessionId}/active-run/cancel`, {
      method: "POST",
    });
  } catch (error) {
    setStoppingState(false);
    appendError(error);
  }
}

async function resumeActiveRun() {
  if (submitting) return;
  const active = await loadActiveRun();
  if (!active) return;

  const chatUi = ensureUi();
  submitting = true;
  restoreActiveRunState(active);
  chatUi.setSubmitting(true);
  emit("run.started", { resumed: true, runId: active.run_id });
  try {
    const response = await api(`/v1/chat/sessions/${sessionId}/active-run/stream`);
    await observeRuntimeRun(response, { resumed: true });
    await loadHistory();
  } catch (error) {
    appendError(error);
  } finally {
    submitting = false;
    stopping = false;
    chatUi.setStopping(false);
    chatUi.setSubmitting(false);
    chatUi.focusComposer();
  }
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
    void resumeActiveRun();
  } catch (error) {
    ensureUi(DEFAULT_APPEARANCE);
    appendError(error);
  } finally {
    bootstrapping = false;
  }
}

async function sendMessage(message: string) {
  if (submitting) return;
  const chatUi = ensureUi();
  submitting = true;
  stopping = false;
  chatUi.setStopping(false);
  chatUi.clearComposer();
  chatUi.appendMessage("user", message, true);
  chatUi.setSubmitting(true);
  emit("message.sent");
  emit("run.started", { resumed: false });

  try {
    let response: Response;
    try {
      response = await api(`/v1/chat/sessions/${sessionId}/messages:stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Idempotency-Key": randomUuid(),
        },
        body: JSON.stringify({ message }),
      });
    } catch (error) {
      if (error instanceof SessionExpiredError) throw error;
      // A structured admission conflict already carries the canonical Run identity.
      // Other ambiguous failures get one server-side reconciliation request; the
      // iframe never polls active-run or resubmits the user's message.
      const active = activeRunFromConflict(error) ?? await recoverAcceptedActiveRun();
      if (!active) throw error;
      restoreActiveRunState(active);
      response = await api(`/v1/chat/sessions/${sessionId}/active-run/stream`);
    }
    await observeRuntimeRun(response, { resumed: false });
  } catch (error) {
    appendError(error);
  } finally {
    submitting = false;
    stopping = false;
    chatUi.setStopping(false);
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
  } else if (event.data.type === "run.cancel") {
    await requestCancel();
  } else if (event.data.type === "open") {
    emit("opened");
  } else if (event.data.type === "close") {
    // Closing the surface only disconnects/hides the observer. It never requests
    // execution cancellation; Stop/run.cancel is the explicit lifecycle command.
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
