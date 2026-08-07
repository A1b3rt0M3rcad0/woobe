import {
  createChatUi,
  DEFAULT_APPEARANCE,
  type SurfaceAppearance,
} from "./chat-ui";
import "./styles.css";

interface PreviewUpdateMessage {
  type: "woobe.preview.update";
  appearance: SurfaceAppearance;
}

function isPreviewUpdateMessage(value: unknown): value is PreviewUpdateMessage {
  if (!value || typeof value !== "object" || Array.isArray(value)) return false;
  const message = value as Record<string, unknown>;
  if (message.type !== "woobe.preview.update") return false;
  const appearance = message.appearance;
  if (!appearance || typeof appearance !== "object" || Array.isArray(appearance)) {
    return false;
  }
  const candidate = appearance as Record<string, unknown>;
  return (
    ["light", "dark", "system"].includes(String(candidate.theme)) &&
    typeof candidate.primary_color === "string" &&
    typeof candidate.title === "string" &&
    typeof candidate.placeholder === "string" &&
    (typeof candidate.welcome_message === "string" || candidate.welcome_message === null)
  );
}

const root = document.querySelector<HTMLElement>("#woobe-chat");
if (!root) throw new Error("Woobe Chat preview root was not found");

let parentOrigin: string | null = null;
let ui = createChatUi(root, DEFAULT_APPEARANCE);

function render(appearance: SurfaceAppearance) {
  ui = createChatUi(root, appearance);
  if (appearance.welcome_message) {
    ui.appendMessage("assistant", appearance.welcome_message, true);
  }
}

window.addEventListener("message", (event) => {
  if (event.source !== window.parent || !isPreviewUpdateMessage(event.data)) return;
  if (parentOrigin !== null && event.origin !== parentOrigin) return;
  parentOrigin = event.origin;
  render(event.data.appearance);
});

window.parent.postMessage({ type: "woobe.preview.ready" }, "*");
