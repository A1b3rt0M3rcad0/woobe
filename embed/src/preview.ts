import {
  normalizeAppearance,
  resolveWelcomeMessage,
  type SurfaceAppearance,
} from "./appearance";
import {
  createChatUi,
  DEFAULT_APPEARANCE,
} from "./chat-ui";
import "./styles.css";
import "./preview-scrollbars.css";

interface PreviewUpdateMessage {
  type: "woobe.preview.update";
  appearance: SurfaceAppearance;
}

function isPreviewUpdateMessage(value: unknown): value is PreviewUpdateMessage {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const message = value as Record<string, unknown>;
  return message.type === "woobe.preview.update"
    && Boolean(message.appearance)
    && typeof message.appearance === "object"
    && !Array.isArray(message.appearance);
}

const rootElement = document.querySelector<HTMLElement>("#woobe-chat");
if (!rootElement) throw new Error("Woobe Chat preview root was not found");
const root: HTMLElement = rootElement;

const PREVIEW_USER_MESSAGE = "Can you help me get started?";

let parentOrigin: string | null = null;
let ui = createChatUi(root, DEFAULT_APPEARANCE);

function render(value: SurfaceAppearance) {
  const appearance = normalizeAppearance(value);
  ui = createChatUi(root, appearance);
  ui.appendMessage("assistant", resolveWelcomeMessage(appearance.welcome_message));
  ui.appendMessage("user", PREVIEW_USER_MESSAGE);
  const pending = ui.appendPendingAssistant();
  ui.updateAssistantActivity(pending, { status: "generating_answer" });
  ui.scrollToLatest(true);
}

render(DEFAULT_APPEARANCE);

window.addEventListener("message", (event) => {
  if (event.source !== window.parent || !isPreviewUpdateMessage(event.data)) return;
  if (parentOrigin !== null && event.origin !== parentOrigin) return;
  parentOrigin = event.origin;
  render(event.data.appearance);
});

window.parent.postMessage({ type: "woobe.preview.ready" }, "*");
