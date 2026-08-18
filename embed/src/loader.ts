const PROTOCOL_VERSION = 1 as const;

type FrameEventType =
  | "ready"
  | "history.loaded"
  | "message.sent"
  | "run.started"
  | "run.activity"
  | "run.completed"
  | "session.expired"
  | "error"
  | "opened"
  | "closed";

interface FrameEvent {
  protocolVersion: 1;
  instanceId: string;
  surfaceId: string;
  type: FrameEventType;
  payload?: unknown;
}

export interface WoobeChatOptions {
  container: string | HTMLElement;
  surfaceId: string;
  sessionToken: string;
  mode?: "inline" | "floating";
  iframeBaseUrl?: string;
  apiBaseUrl?: string;
  onEvent?: (event: FrameEvent) => void;
}

export interface WoobeChatInstance {
  updateToken(token: string): void;
  open(): void;
  close(): void;
  destroy(): void;
}

const loaderScriptUrl =
  document.currentScript instanceof HTMLScriptElement && document.currentScript.src
    ? new URL(document.currentScript.src)
    : new URL("https://chat.woobe.ai/chat/v1/embed.js");

function resolveContainer(value: string | HTMLElement): HTMLElement {
  const element =
    typeof value === "string" ? document.querySelector<HTMLElement>(value) : value;
  if (!element) throw new Error("Woobe Chat container was not found");
  return element;
}

function resolveFrameUrl(iframeBaseUrl?: string): URL {
  if (!iframeBaseUrl) return new URL("iframe.html", loaderScriptUrl);
  const normalized = iframeBaseUrl.endsWith("/")
    ? iframeBaseUrl
    : `${iframeBaseUrl}/`;
  return new URL("iframe.html", normalized);
}

function randomUuid(): string {
  const cryptoApi = globalThis.crypto;
  if (cryptoApi && typeof cryptoApi.randomUUID === "function") {
    return cryptoApi.randomUUID();
  }
  if (!cryptoApi || typeof cryptoApi.getRandomValues !== "function") {
    throw new Error("Secure random generation is not available");
  }

  const bytes = cryptoApi.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;

  const hex = Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function mount(options: WoobeChatOptions): WoobeChatInstance {
  const container = resolveContainer(options.container);
  const frameUrl = resolveFrameUrl(options.iframeBaseUrl);
  const frameOrigin = frameUrl.origin;
  const hostOrigin = window.location.origin;
  const instanceId = randomUuid();
  const iframe = document.createElement("iframe");
  frameUrl.searchParams.set("surface", options.surfaceId);
  frameUrl.searchParams.set("instance", instanceId);
  iframe.title = "Woobe Chat";
  iframe.src = frameUrl.toString();
  iframe.referrerPolicy = "no-referrer";
  iframe.sandbox.add("allow-forms", "allow-scripts", "allow-same-origin");
  iframe.dataset.woobeChat = instanceId;
  iframe.style.cssText =
    options.mode === "floating"
      ? "position:fixed;right:24px;bottom:24px;width:min(420px,calc(100vw - 32px));height:min(680px,calc(100vh - 48px));border:0;border-radius:16px;box-shadow:0 18px 60px rgba(0,0,0,.2);z-index:2147483000"
      : "width:100%;height:100%;min-height:480px;border:0";
  let token = options.sessionToken;
  let opened = true;
  let destroyed = false;

  const send = (
    type: "init" | "token.update" | "open" | "close",
    payload?: Record<string, string>,
  ) => {
    if (destroyed || !iframe.contentWindow) return;
    iframe.contentWindow.postMessage(
      {
        protocolVersion: PROTOCOL_VERSION,
        instanceId,
        surfaceId: options.surfaceId,
        type,
        payload,
      },
      frameOrigin,
    );
  };

  const onMessage = (event: MessageEvent) => {
    if (
      event.origin !== frameOrigin ||
      event.source !== iframe.contentWindow ||
      !event.data ||
      event.data.protocolVersion !== PROTOCOL_VERSION ||
      event.data.instanceId !== instanceId ||
      event.data.surfaceId !== options.surfaceId
    ) {
      return;
    }
    const frameEvent = event.data as FrameEvent;
    if (frameEvent.type === "ready") {
      send("init", {
        token,
        hostOrigin,
        apiBaseUrl: options.apiBaseUrl ?? "https://api.woobe.ai",
      });
    }
    options.onEvent?.(frameEvent);
  };

  window.addEventListener("message", onMessage);
  container.appendChild(iframe);

  return {
    updateToken(nextToken: string) {
      token = nextToken;
      send("token.update", { token });
    },
    open() {
      if (destroyed || opened) return;
      opened = true;
      iframe.hidden = false;
      send("open");
    },
    close() {
      if (destroyed || !opened) return;
      opened = false;
      send("close");
      iframe.hidden = true;
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      window.removeEventListener("message", onMessage);
      iframe.remove();
    },
  };
}

declare global {
  interface Window {
    WoobeChat: { mount: typeof mount };
  }
}

window.WoobeChat = Object.freeze({ mount });
