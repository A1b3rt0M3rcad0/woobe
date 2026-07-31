import { PROTOCOL_VERSION, type FrameEvent } from "./protocol";

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

function resolveContainer(value: string | HTMLElement): HTMLElement {
  const element =
    typeof value === "string" ? document.querySelector<HTMLElement>(value) : value;
  if (!element) throw new Error("Woobe Chat container was not found");
  return element;
}

function mount(options: WoobeChatOptions): WoobeChatInstance {
  const container = resolveContainer(options.container);
  const iframeBaseUrl =
    options.iframeBaseUrl ?? "https://chat.woobe.ai";
  const frameOrigin = new URL(iframeBaseUrl).origin;
  const hostOrigin = window.location.origin;
  const instanceId = crypto.randomUUID();
  const iframe = document.createElement("iframe");
  iframe.title = "Woobe Chat";
  iframe.src = `${frameOrigin}/iframe.html?surface=${encodeURIComponent(
    options.surfaceId,
  )}&instance=${encodeURIComponent(instanceId)}`;
  iframe.allow = "clipboard-write";
  iframe.referrerPolicy = "strict-origin";
  iframe.sandbox.add(
    "allow-forms",
    "allow-scripts",
    "allow-same-origin",
    "allow-popups",
  );
  iframe.dataset.woobeChat = instanceId;
  iframe.style.cssText =
    options.mode === "floating"
      ? "position:fixed;right:24px;bottom:24px;width:min(420px,calc(100vw - 32px));height:min(680px,calc(100vh - 48px));border:0;border-radius:16px;box-shadow:0 18px 60px rgba(0,0,0,.2);z-index:2147483000"
      : "width:100%;height:100%;min-height:480px;border:0";
  let token = options.sessionToken;
  let opened = true;
  let destroyed = false;

  const send = (
    type: "init" | "token.update" | "open" | "close" | "destroy",
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
      send("destroy");
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
