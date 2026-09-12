export type SurfaceTheme = "light" | "dark" | "system";
export type ResponseRenderMode = "plain" | "rich";
export type ActivityMode = "dots" | "status";
export type ActivityDetailLevel = "generic" | "named";

export interface SurfaceStyle {
  background_color: string | null;
  border_color: string | null;
  border_width: number;
  border_radius: number;
  shadow: "none" | "sm" | "md" | "lg";
}

export interface HeaderStyle {
  visible: boolean;
  background_color: string | null;
  text_color: string | null;
  border_color: string | null;
  border_width: number;
  height: number;
  padding: number;
  alignment: "left" | "center" | "right";
}

export interface ConversationStyle {
  background_color: string | null;
  padding: number;
  message_gap: number;
  max_content_width: number;
}

export interface MessageStyle {
  background_color: string | null;
  text_color: string | null;
  border_color: string | null;
  border_width: number;
  border_radius: number;
  padding_y: number;
  padding_x: number;
  max_width: number;
  show_avatar: boolean;
}

export interface ComposerStyle {
  background_color: string | null;
  border_color: string | null;
  padding: number;
}

export interface InputStyle {
  background_color: string | null;
  text_color: string | null;
  placeholder_color: string | null;
  border_color: string | null;
  focus_border_color: string | null;
  border_radius: number;
  font_size: number;
  padding_y: number;
  padding_x: number;
}

export interface SendButtonStyle {
  variant: "text" | "icon" | "icon_text";
  background_color: string | null;
  text_color: string | null;
  border_color: string | null;
  border_width: number;
  border_radius: number;
  label: string;
  icon: "arrow_up" | "arrow_right" | "none";
}

export interface ActivityLabels {
  preparing: string;
  planning_tools: string;
  calling_tool: string;
  processing_tool_result: string;
  generating_answer: string;
  formatting_response: string;
}

export interface ActivityStyle {
  mode: ActivityMode;
  detail_level: ActivityDetailLevel;
  show_icon: boolean;
  labels: ActivityLabels;
}

export interface SurfaceAppearance {
  schema_version: 2;
  theme: SurfaceTheme;
  primary_color: string;
  title: string;
  placeholder: string;
  welcome_message: string | null;
  surface: SurfaceStyle;
  header: HeaderStyle;
  conversation: ConversationStyle;
  messages: {
    user: MessageStyle;
    assistant: MessageStyle;
    system: MessageStyle;
  };
  composer: ComposerStyle;
  input: InputStyle;
  send_button: SendButtonStyle;
  activity: ActivityStyle;
  response: {
    render_mode: ResponseRenderMode;
  };
}

export const DEFAULT_WELCOME_MESSAGE = "Hi! How can I help you today?";

export function resolveWelcomeMessage(value: string | null | undefined): string {
  const message = value?.trim();
  return message || DEFAULT_WELCOME_MESSAGE;
}

export const DEFAULT_APPEARANCE: SurfaceAppearance = {
  schema_version: 2,
  theme: "system",
  primary_color: "#3B82F6",
  title: "Woobe",
  placeholder: "Type a message…",
  welcome_message: null,
  surface: {
    background_color: null,
    border_color: null,
    border_width: 1,
    border_radius: 4,
    shadow: "none",
  },
  header: {
    visible: true,
    background_color: null,
    text_color: null,
    border_color: null,
    border_width: 1,
    height: 48,
    padding: 14,
    alignment: "left",
  },
  conversation: {
    background_color: null,
    padding: 16,
    message_gap: 8,
    max_content_width: 100,
  },
  messages: {
    user: {
      background_color: null,
      text_color: null,
      border_color: null,
      border_width: 0,
      border_radius: 6,
      padding_y: 8,
      padding_x: 11,
      max_width: 80,
      show_avatar: false,
    },
    assistant: {
      background_color: null,
      text_color: null,
      border_color: null,
      border_width: 1,
      border_radius: 6,
      padding_y: 8,
      padding_x: 11,
      max_width: 80,
      show_avatar: false,
    },
    system: {
      background_color: null,
      text_color: null,
      border_color: null,
      border_width: 1,
      border_radius: 4,
      padding_y: 8,
      padding_x: 10,
      max_width: 100,
      show_avatar: false,
    },
  },
  composer: {
    background_color: null,
    border_color: null,
    padding: 10,
  },
  input: {
    background_color: null,
    text_color: null,
    placeholder_color: null,
    border_color: null,
    focus_border_color: null,
    border_radius: 4,
    font_size: 14,
    padding_y: 8,
    padding_x: 10,
  },
  send_button: {
    variant: "text",
    background_color: null,
    text_color: null,
    border_color: null,
    border_width: 1,
    border_radius: 4,
    label: "Send",
    icon: "arrow_up",
  },
  activity: {
    mode: "dots",
    detail_level: "generic",
    show_icon: true,
    labels: {
      preparing: "Preparing response…",
      planning_tools: "Checking whether tools are needed…",
      calling_tool: "Using a tool…",
      processing_tool_result: "Processing tool result…",
      generating_answer: "Generating response…",
      formatting_response: "Formatting response…",
    },
  },
  response: {
    render_mode: "rich",
  },
};

type UnknownRecord = Record<string, unknown>;

function record(value: unknown): UnknownRecord {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as UnknownRecord)
    : {};
}

function stringValue(value: unknown, fallback: string): string {
  return typeof value === "string" ? value : fallback;
}

function nullableString(value: unknown, fallback: string | null): string | null {
  return value === null || typeof value === "string" ? value : fallback;
}

function numberValue(value: unknown, fallback: number): number {
  return typeof value === "number" && Number.isFinite(value) ? value : fallback;
}

function booleanValue(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

function choice<T extends string>(value: unknown, values: readonly T[], fallback: T): T {
  return typeof value === "string" && values.includes(value as T) ? (value as T) : fallback;
}

function messageStyle(value: unknown, fallback: MessageStyle): MessageStyle {
  const raw = record(value);
  return {
    background_color: nullableString(raw.background_color, fallback.background_color),
    text_color: nullableString(raw.text_color, fallback.text_color),
    border_color: nullableString(raw.border_color, fallback.border_color),
    border_width: numberValue(raw.border_width, fallback.border_width),
    border_radius: numberValue(raw.border_radius, fallback.border_radius),
    padding_y: numberValue(raw.padding_y, fallback.padding_y),
    padding_x: numberValue(raw.padding_x, fallback.padding_x),
    max_width: numberValue(raw.max_width, fallback.max_width),
    show_avatar: booleanValue(raw.show_avatar, fallback.show_avatar),
  };
}

export function normalizeAppearance(value: unknown): SurfaceAppearance {
  const raw = record(value);
  const surface = record(raw.surface);
  const header = record(raw.header);
  const conversation = record(raw.conversation);
  const messages = record(raw.messages);
  const composer = record(raw.composer);
  const input = record(raw.input);
  const sendButton = record(raw.send_button);
  const activity = record(raw.activity);
  const labels = record(activity.labels);
  const response = record(raw.response);

  return {
    schema_version: 2,
    theme: choice(raw.theme, ["light", "dark", "system"] as const, DEFAULT_APPEARANCE.theme),
    primary_color: stringValue(raw.primary_color, DEFAULT_APPEARANCE.primary_color),
    title: stringValue(raw.title, DEFAULT_APPEARANCE.title),
    placeholder: stringValue(raw.placeholder, DEFAULT_APPEARANCE.placeholder),
    welcome_message: resolveWelcomeMessage(nullableString(raw.welcome_message, DEFAULT_APPEARANCE.welcome_message)),
    surface: {
      background_color: nullableString(surface.background_color, DEFAULT_APPEARANCE.surface.background_color),
      border_color: nullableString(surface.border_color, DEFAULT_APPEARANCE.surface.border_color),
      border_width: numberValue(surface.border_width, DEFAULT_APPEARANCE.surface.border_width),
      border_radius: numberValue(surface.border_radius, DEFAULT_APPEARANCE.surface.border_radius),
      shadow: choice(surface.shadow, ["none", "sm", "md", "lg"] as const, DEFAULT_APPEARANCE.surface.shadow),
    },
    header: {
      visible: booleanValue(header.visible, DEFAULT_APPEARANCE.header.visible),
      background_color: nullableString(header.background_color, DEFAULT_APPEARANCE.header.background_color),
      text_color: nullableString(header.text_color, DEFAULT_APPEARANCE.header.text_color),
      border_color: nullableString(header.border_color, DEFAULT_APPEARANCE.header.border_color),
      border_width: numberValue(header.border_width, DEFAULT_APPEARANCE.header.border_width),
      height: numberValue(header.height, DEFAULT_APPEARANCE.header.height),
      padding: numberValue(header.padding, DEFAULT_APPEARANCE.header.padding),
      alignment: choice(header.alignment, ["left", "center", "right"] as const, DEFAULT_APPEARANCE.header.alignment),
    },
    conversation: {
      background_color: nullableString(conversation.background_color, DEFAULT_APPEARANCE.conversation.background_color),
      padding: numberValue(conversation.padding, DEFAULT_APPEARANCE.conversation.padding),
      message_gap: numberValue(conversation.message_gap, DEFAULT_APPEARANCE.conversation.message_gap),
      max_content_width: numberValue(conversation.max_content_width, DEFAULT_APPEARANCE.conversation.max_content_width),
    },
    messages: {
      user: messageStyle(messages.user, DEFAULT_APPEARANCE.messages.user),
      assistant: messageStyle(messages.assistant, DEFAULT_APPEARANCE.messages.assistant),
      system: messageStyle(messages.system, DEFAULT_APPEARANCE.messages.system),
    },
    composer: {
      background_color: nullableString(composer.background_color, DEFAULT_APPEARANCE.composer.background_color),
      border_color: nullableString(composer.border_color, DEFAULT_APPEARANCE.composer.border_color),
      padding: numberValue(composer.padding, DEFAULT_APPEARANCE.composer.padding),
    },
    input: {
      background_color: nullableString(input.background_color, DEFAULT_APPEARANCE.input.background_color),
      text_color: nullableString(input.text_color, DEFAULT_APPEARANCE.input.text_color),
      placeholder_color: nullableString(input.placeholder_color, DEFAULT_APPEARANCE.input.placeholder_color),
      border_color: nullableString(input.border_color, DEFAULT_APPEARANCE.input.border_color),
      focus_border_color: nullableString(input.focus_border_color, DEFAULT_APPEARANCE.input.focus_border_color),
      border_radius: numberValue(input.border_radius, DEFAULT_APPEARANCE.input.border_radius),
      font_size: numberValue(input.font_size, DEFAULT_APPEARANCE.input.font_size),
      padding_y: numberValue(input.padding_y, DEFAULT_APPEARANCE.input.padding_y),
      padding_x: numberValue(input.padding_x, DEFAULT_APPEARANCE.input.padding_x),
    },
    send_button: {
      variant: choice(sendButton.variant, ["text", "icon", "icon_text"] as const, DEFAULT_APPEARANCE.send_button.variant),
      background_color: nullableString(sendButton.background_color, DEFAULT_APPEARANCE.send_button.background_color),
      text_color: nullableString(sendButton.text_color, DEFAULT_APPEARANCE.send_button.text_color),
      border_color: nullableString(sendButton.border_color, DEFAULT_APPEARANCE.send_button.border_color),
      border_width: numberValue(sendButton.border_width, DEFAULT_APPEARANCE.send_button.border_width),
      border_radius: numberValue(sendButton.border_radius, DEFAULT_APPEARANCE.send_button.border_radius),
      label: stringValue(sendButton.label, DEFAULT_APPEARANCE.send_button.label),
      icon: choice(sendButton.icon, ["arrow_up", "arrow_right", "none"] as const, DEFAULT_APPEARANCE.send_button.icon),
    },
    activity: {
      mode: choice(activity.mode, ["dots", "status"] as const, DEFAULT_APPEARANCE.activity.mode),
      detail_level: choice(activity.detail_level, ["generic", "named"] as const, DEFAULT_APPEARANCE.activity.detail_level),
      show_icon: booleanValue(activity.show_icon, DEFAULT_APPEARANCE.activity.show_icon),
      labels: {
        preparing: stringValue(labels.preparing, DEFAULT_APPEARANCE.activity.labels.preparing),
        planning_tools: stringValue(labels.planning_tools, DEFAULT_APPEARANCE.activity.labels.planning_tools),
        calling_tool: stringValue(labels.calling_tool, DEFAULT_APPEARANCE.activity.labels.calling_tool),
        processing_tool_result: stringValue(labels.processing_tool_result, DEFAULT_APPEARANCE.activity.labels.processing_tool_result),
        generating_answer: stringValue(labels.generating_answer, DEFAULT_APPEARANCE.activity.labels.generating_answer),
        formatting_response: stringValue(labels.formatting_response, DEFAULT_APPEARANCE.activity.labels.formatting_response),
      },
    },
    response: {
      render_mode: choice(response.render_mode, ["plain", "rich"] as const, DEFAULT_APPEARANCE.response.render_mode),
    },
  };
}
