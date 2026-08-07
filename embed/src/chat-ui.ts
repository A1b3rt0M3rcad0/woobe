export interface SurfaceAppearance {
  theme: "light" | "dark" | "system";
  primary_color: string;
  title: string;
  placeholder: string;
  welcome_message: string | null;
}

export const DEFAULT_APPEARANCE: SurfaceAppearance = {
  theme: "system",
  primary_color: "#5B47E0",
  title: "Woobe",
  placeholder: "Type a message…",
  welcome_message: null,
};

type MessageRole = "user" | "assistant";

export interface ChatUi {
  setAppearance(appearance: SurfaceAppearance): void;
  clearMessages(): void;
  appendMessage(role: MessageRole, content: string, forceScroll?: boolean): HTMLElement;
  appendPendingAssistant(): HTMLElement;
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

function messageElement(role: MessageRole, content: string): HTMLElement {
  const item = document.createElement("article");
  item.className = `message message--${role}`;
  item.textContent = content;
  return item;
}

export function createChatUi(
  root: HTMLElement,
  initialAppearance: SurfaceAppearance,
  options: CreateChatUiOptions = {},
): ChatUi {
  let appearance = initialAppearance;
  let submitting = false;
  let sessionExpired = false;
  let followLatest = true;

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

  const updateComposerState = () => {
    const disabled = submitting || sessionExpired;
    input.disabled = disabled;
    button.disabled = disabled;
    button.textContent = submitting ? "Sending…" : "Send";
  };

  const setAppearance = (next: SurfaceAppearance) => {
    appearance = next;
    root.dataset.theme = next.theme;
    root.style.setProperty("--woobe-primary", next.primary_color);
    header.textContent = next.title;
    input.placeholder = next.placeholder;
    document.title = next.title;
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

  setAppearance(initialAppearance);
  updateComposerState();

  return {
    setAppearance,
    clearMessages() {
      messages.innerHTML = "";
      followLatest = true;
    },
    appendMessage(role, content, forceScroll = false) {
      const item = messageElement(role, content);
      messages.appendChild(item);
      scrollToLatest(forceScroll);
      return item;
    },
    appendPendingAssistant() {
      const item = messageElement("assistant", "");
      item.classList.add("message--pending");
      item.setAttribute("aria-label", "Agent is responding");
      item.innerHTML = `
        <span class="typing-indicator" aria-hidden="true">
          <span></span><span></span><span></span>
        </span>
      `;
      messages.appendChild(item);
      scrollToLatest(true);
      return item;
    },
    beginAssistantStreaming(element) {
      element.classList.remove("message--pending");
      element.classList.add("message--streaming");
      element.removeAttribute("aria-label");
      element.textContent = "";
    },
    updateAssistantStreaming(element, content) {
      element.textContent = content;
      scrollToLatest();
    },
    finishAssistantStreaming(element) {
      element.classList.remove("message--pending", "message--streaming");
      element.removeAttribute("aria-label");
    },
    removeMessage(element) {
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
