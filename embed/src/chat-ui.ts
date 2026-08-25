import {
  DEFAULT_APPEARANCE,
  normalizeAppearance,
  type SurfaceAppearance,
} from "./appearance";
import { renderMessageContent } from "./message-renderer";

export { DEFAULT_APPEARANCE } from "./appearance";
export type { SurfaceAppearance } from "./appearance";

type MessageRole = "user" | "assistant";

export interface PublicAgentActivity {
  status?: string;
  tool_name?: string;
}

export interface ChatUi {
  setAppearance(appearance: SurfaceAppearance): void;
  clearMessages(): void;
  appendMessage(role: MessageRole, content: string, forceScroll?: boolean): HTMLElement;
  appendPendingAssistant(): HTMLElement;
  updateAssistantActivity(element: HTMLElement, activity: PublicAgentActivity): string;
  beginAssistantStreaming(element: HTMLElement): void;
  updateAssistantStreaming(element: HTMLElement, content: string): void;
  finishAssistantStreaming(element: HTMLElement): void;
  removeMessage(element: HTMLElement): void;
  appendError(message: string): void;
  showSessionExpired(): void;
  clearSessionExpired(): void;
  setSubmitting(value: boolean): void;
  clearComposer(): void;
  focusComposer(): void;
  scrollToLatest(force?: boolean): void;
}

interface CreateChatUiOptions {
  onSubmit?: (message: string) => void;
}

const ACTIVITY_STATUSES = new Set([
  "preparing",
  "planning_tools",
  "calling_tool",
  "processing_tool_result",
  "generating_answer",
  "formatting_response",
]);

function activityLabel(appearance: SurfaceAppearance, activity: PublicAgentActivity): string {
  const status = ACTIVITY_STATUSES.has(activity.status ?? "")
    ? (activity.status as keyof SurfaceAppearance["activity"]["labels"])
    : "preparing";
  let label = appearance.activity.labels[status];
  if (
    appearance.activity.detail_level === "named" &&
    status === "calling_tool" &&
    activity.tool_name &&
    label.includes("{tool}")
  ) {
    label = label.replaceAll("{tool}", activity.tool_name.slice(0, 120));
  } else {
    label = label.replaceAll("{tool}", "a tool");
  }
  return label;
}

function shadowValue(value: SurfaceAppearance["surface"]["shadow"]): string {
  if (value === "sm") return "0 4px 14px rgba(15, 23, 42, 0.10)";
  if (value === "md") return "0 12px 32px rgba(15, 23, 42, 0.16)";
  if (value === "lg") return "0 22px 54px rgba(15, 23, 42, 0.22)";
  return "none";
}

function messageElement(
  role: MessageRole,
  content: string,
  appearance: SurfaceAppearance,
): HTMLElement {
  const item = document.createElement("article");
  item.className = `message message--${role}`;
  item.dataset.role = role;
  item.dataset.content = content;
  item.dataset.showAvatar = String(appearance.messages[role].show_avatar);

  const body = document.createElement("div");
  body.className = "message__content";
  if (role === "assistant") {
    renderMessageContent(body, content, appearance.response.render_mode);
  } else {
    body.textContent = content;
  }
  item.append(body);
  return item;
}

function setOptionalVariable(root: HTMLElement, name: string, value: string | null) {
  if (value === null) root.style.removeProperty(name);
  else root.style.setProperty(name, value);
}

function renderSendButton(
  button: HTMLButtonElement,
  appearance: SurfaceAppearance,
  submitting: boolean,
) {
  button.replaceChildren();
  if (submitting) {
    button.textContent = "Sending…";
    return;
  }

  const { variant, label, icon } = appearance.send_button;
  const iconText = icon === "arrow_right" ? "→" : icon === "arrow_up" ? "↑" : "";

  if ((variant === "icon" || variant === "icon_text") && iconText) {
    const iconElement = document.createElement("span");
    iconElement.className = "send-button__icon";
    iconElement.setAttribute("aria-hidden", "true");
    iconElement.textContent = iconText;
    button.append(iconElement);
  }

  if (variant === "text" || variant === "icon_text" || !iconText) {
    const labelElement = document.createElement("span");
    labelElement.textContent = label;
    button.append(labelElement);
  }

  button.setAttribute("aria-label", label);
}

function renderPendingContent(
  item: HTMLElement,
  appearance: SurfaceAppearance,
  activity: PublicAgentActivity = { status: "preparing" },
): string {
  item.replaceChildren();
  if (appearance.activity.mode === "dots") {
    const indicator = document.createElement("span");
    indicator.className = "typing-indicator";
    indicator.setAttribute("aria-hidden", "true");
    for (let index = 0; index < 3; index += 1) indicator.append(document.createElement("span"));
    item.append(indicator);
    item.setAttribute("aria-label", "Agent is responding");
    return "Agent is responding";
  }

  const label = activityLabel(appearance, activity);
  const status = document.createElement("span");
  status.className = "activity-status";
  if (appearance.activity.show_icon) {
    const spinner = document.createElement("span");
    spinner.className = "activity-status__spinner";
    spinner.setAttribute("aria-hidden", "true");
    status.append(spinner);
  }
  const text = document.createElement("span");
  text.textContent = label;
  status.append(text);
  item.append(status);
  item.setAttribute("aria-label", label);
  return label;
}

export function createChatUi(
  root: HTMLElement,
  initialAppearance: SurfaceAppearance,
  options: CreateChatUiOptions = {},
): ChatUi {
  let appearance = normalizeAppearance(initialAppearance);
  let submitting = false;
  let sessionExpired = false;
  let followLatest = true;
  const streamingFrames = new Map<HTMLElement, number>();

  root.innerHTML = `
    <section class="chat">
      <header class="chat__header"></header>
      <div class="chat__messages" role="log" aria-label="Conversation" aria-live="polite"></div>
      <form class="chat__composer">
        <label class="sr-only" for="woobe-message">Message</label>
        <textarea id="woobe-message" rows="1" maxlength="32768" required></textarea>
        <button class="chat__send" type="submit"></button>
      </form>
    </section>
  `;

  const header = root.querySelector<HTMLElement>(".chat__header");
  const messages = root.querySelector<HTMLElement>(".chat__messages");
  const form = root.querySelector<HTMLFormElement>(".chat__composer");
  const input = root.querySelector<HTMLTextAreaElement>("#woobe-message");
  const button = root.querySelector<HTMLButtonElement>("button[type='submit']");

  if (!header || !messages || !form || !input || !button) {
    throw new Error("Unable to render Woobe Chat UI");
  }

  const isNearBottom = () =>
    messages.scrollHeight - messages.scrollTop - messages.clientHeight <= 72;

  const scrollToLatest = (force = false) => {
    if (!force && !followLatest) return;
    messages.scrollTop = messages.scrollHeight;
    followLatest = true;
  };

  const renderAssistant = (element: HTMLElement, content: string) => {
    element.dataset.content = content;
    let body = element.querySelector<HTMLElement>(".message__content");
    if (!body) {
      body = document.createElement("div");
      body.className = "message__content";
      element.replaceChildren(body);
    }
    renderMessageContent(body, content, appearance.response.render_mode);
  };

  const flushStreaming = (element: HTMLElement) => {
    const frame = streamingFrames.get(element);
    if (frame !== undefined) {
      cancelAnimationFrame(frame);
      streamingFrames.delete(element);
    }
    renderAssistant(element, element.dataset.pendingContent ?? element.dataset.content ?? "");
    delete element.dataset.pendingContent;
  };

  const updateComposerState = () => {
    const disabled = submitting || sessionExpired;
    input.disabled = disabled;
    button.disabled = disabled;
    renderSendButton(button, appearance, submitting);
  };

  const setAppearance = (next: SurfaceAppearance) => {
    appearance = normalizeAppearance(next);
    root.dataset.theme = appearance.theme;
    root.style.setProperty("--woobe-primary", appearance.primary_color);

    setOptionalVariable(root, "--woobe-chat-background-custom", appearance.surface.background_color);
    setOptionalVariable(root, "--woobe-chat-border-custom", appearance.surface.border_color);
    root.style.setProperty("--woobe-chat-border-width", `${appearance.surface.border_width}px`);
    root.style.setProperty("--woobe-chat-border-radius", `${appearance.surface.border_radius}px`);
    root.style.setProperty("--woobe-chat-shadow", shadowValue(appearance.surface.shadow));

    setOptionalVariable(root, "--woobe-header-background-custom", appearance.header.background_color);
    setOptionalVariable(root, "--woobe-header-text-custom", appearance.header.text_color);
    setOptionalVariable(root, "--woobe-header-border-custom", appearance.header.border_color);
    root.style.setProperty("--woobe-header-border-width", `${appearance.header.border_width}px`);
    root.style.setProperty("--woobe-header-height", `${appearance.header.height}px`);
    root.style.setProperty("--woobe-header-padding", `${appearance.header.padding}px`);
    root.style.setProperty("--woobe-header-alignment", appearance.header.alignment);

    setOptionalVariable(root, "--woobe-conversation-background-custom", appearance.conversation.background_color);
    root.style.setProperty("--woobe-conversation-padding", `${appearance.conversation.padding}px`);
    root.style.setProperty("--woobe-message-gap", `${appearance.conversation.message_gap}px`);
    root.style.setProperty("--woobe-conversation-content-width", `${appearance.conversation.max_content_width}%`);

    for (const role of ["user", "assistant", "system"] as const) {
      const style = appearance.messages[role];
      const prefix = `--woobe-${role}-message`;
      setOptionalVariable(root, `${prefix}-background-custom`, style.background_color);
      setOptionalVariable(root, `${prefix}-text-custom`, style.text_color);
      setOptionalVariable(root, `${prefix}-border-custom`, style.border_color);
      root.style.setProperty(`${prefix}-border-width`, `${style.border_width}px`);
      root.style.setProperty(`${prefix}-border-radius`, `${style.border_radius}px`);
      root.style.setProperty(`${prefix}-padding-y`, `${style.padding_y}px`);
      root.style.setProperty(`${prefix}-padding-x`, `${style.padding_x}px`);
      root.style.setProperty(`${prefix}-max-width`, `${style.max_width}%`);
    }

    setOptionalVariable(root, "--woobe-composer-background-custom", appearance.composer.background_color);
    setOptionalVariable(root, "--woobe-composer-border-custom", appearance.composer.border_color);
    root.style.setProperty("--woobe-composer-padding", `${appearance.composer.padding}px`);

    setOptionalVariable(root, "--woobe-input-background-custom", appearance.input.background_color);
    setOptionalVariable(root, "--woobe-input-text-custom", appearance.input.text_color);
    setOptionalVariable(root, "--woobe-input-placeholder-custom", appearance.input.placeholder_color);
    setOptionalVariable(root, "--woobe-input-border-custom", appearance.input.border_color);
    setOptionalVariable(root, "--woobe-input-focus-border-custom", appearance.input.focus_border_color);
    root.style.setProperty("--woobe-input-border-radius", `${appearance.input.border_radius}px`);
    root.style.setProperty("--woobe-input-font-size", `${appearance.input.font_size}px`);
    root.style.setProperty("--woobe-input-padding-y", `${appearance.input.padding_y}px`);
    root.style.setProperty("--woobe-input-padding-x", `${appearance.input.padding_x}px`);

    setOptionalVariable(root, "--woobe-send-background-custom", appearance.send_button.background_color);
    setOptionalVariable(root, "--woobe-send-text-custom", appearance.send_button.text_color);
    setOptionalVariable(root, "--woobe-send-border-custom", appearance.send_button.border_color);
    root.style.setProperty("--woobe-send-border-width", `${appearance.send_button.border_width}px`);
    root.style.setProperty("--woobe-send-border-radius", `${appearance.send_button.border_radius}px`);

    header.hidden = !appearance.header.visible;
    header.textContent = appearance.title;
    input.placeholder = appearance.placeholder;
    document.title = appearance.title;

    messages.querySelectorAll<HTMLElement>(".message--user, .message--assistant").forEach((element) => {
      const role = element.dataset.role as MessageRole | undefined;
      if (!role) return;
      element.dataset.showAvatar = String(appearance.messages[role].show_avatar);
      if (role === "assistant" && !element.classList.contains("message--pending")) {
        renderAssistant(element, element.dataset.content ?? "");
      }
    });
    messages.querySelectorAll<HTMLElement>(".message--pending").forEach((element) => {
      renderPendingContent(element, appearance);
    });
    updateComposerState();
  };

  messages.addEventListener("scroll", () => {
    followLatest = isNearBottom();
  }, { passive: true });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (submitting || sessionExpired) return;
    const message = input.value.trim();
    if (!message) return;
    options.onSubmit?.(message);
  });

  input.addEventListener("keydown", (event) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.isComposing &&
      !submitting &&
      !sessionExpired
    ) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  setAppearance(appearance);

  return {
    setAppearance,
    clearMessages() {
      for (const frame of streamingFrames.values()) cancelAnimationFrame(frame);
      streamingFrames.clear();
      messages.replaceChildren();
      followLatest = true;
    },
    appendMessage(role, content, forceScroll = false) {
      const item = messageElement(role, content, appearance);
      messages.appendChild(item);
      scrollToLatest(forceScroll);
      return item;
    },
    appendPendingAssistant() {
      const item = messageElement("assistant", "", appearance);
      item.classList.add("message--pending");
      renderPendingContent(item, appearance);
      messages.appendChild(item);
      scrollToLatest(true);
      return item;
    },
    updateAssistantActivity(element, activity) {
      if (!element.classList.contains("message--pending")) return "";
      const label = renderPendingContent(element, appearance, activity);
      scrollToLatest();
      return label;
    },
    beginAssistantStreaming(element) {
      element.classList.remove("message--pending");
      element.classList.add("message--streaming");
      element.removeAttribute("aria-label");
      element.dataset.content = "";
      element.dataset.pendingContent = "";
      renderAssistant(element, "");
    },
    updateAssistantStreaming(element, content) {
      element.dataset.pendingContent = content;
      if (streamingFrames.has(element)) return;
      const frame = requestAnimationFrame(() => {
        streamingFrames.delete(element);
        renderAssistant(element, element.dataset.pendingContent ?? content);
        scrollToLatest();
      });
      streamingFrames.set(element, frame);
    },
    finishAssistantStreaming(element) {
      flushStreaming(element);
      element.classList.remove("message--pending", "message--streaming");
      element.removeAttribute("aria-label");
    },
    removeMessage(element) {
      const frame = streamingFrames.get(element);
      if (frame !== undefined) cancelAnimationFrame(frame);
      streamingFrames.delete(element);
      element.remove();
    },
    appendError(message) {
      const item = document.createElement("article");
      item.className = "message message--system message--error";
      const title = document.createElement("strong");
      title.textContent = "Unable to generate response";
      const detail = document.createElement("span");
      detail.textContent = message;
      item.append(title, detail);
      messages.appendChild(item);
      scrollToLatest(true);
    },
    showSessionExpired() {
      sessionExpired = true;
      updateComposerState();
      if (messages.querySelector(".message--session-expired")) return;
      const item = document.createElement("article");
      item.className = "message message--system message--session-expired";
      const title = document.createElement("strong");
      title.textContent = "Session expired";
      const detail = document.createElement("span");
      detail.textContent = "Reconnect to continue the conversation.";
      item.append(title, detail);
      messages.appendChild(item);
      scrollToLatest(true);
    },
    clearSessionExpired() {
      sessionExpired = false;
      messages.querySelector(".message--session-expired")?.remove();
      updateComposerState();
    },
    setSubmitting(value) {
      submitting = value;
      updateComposerState();
    },
    clearComposer() {
      input.value = "";
    },
    focusComposer() {
      if (!sessionExpired) input.focus();
    },
    scrollToLatest,
  };
}
