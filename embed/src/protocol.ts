export const PROTOCOL_VERSION = 1 as const;

export type HostMessage =
  | {
      protocolVersion: 1;
      instanceId: string;
      surfaceId: string;
      type: "init";
      payload: { token: string; hostOrigin: string; apiBaseUrl: string };
    }
  | {
      protocolVersion: 1;
      instanceId: string;
      surfaceId: string;
      type: "token.update";
      payload: { token: string };
    }
  | {
      protocolVersion: 1;
      instanceId: string;
      surfaceId: string;
      type: "open" | "close";
      payload?: never;
    };

export type FrameEventType =
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

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function isHostMessage(value: unknown): value is HostMessage {
  if (!isRecord(value)) return false;
  if (
    value.protocolVersion !== PROTOCOL_VERSION ||
    typeof value.instanceId !== "string" ||
    typeof value.surfaceId !== "string" ||
    typeof value.type !== "string"
  ) {
    return false;
  }

  if (value.type === "init") {
    return (
      isRecord(value.payload) &&
      typeof value.payload.token === "string" &&
      typeof value.payload.hostOrigin === "string" &&
      typeof value.payload.apiBaseUrl === "string"
    );
  }
  if (value.type === "token.update") {
    return isRecord(value.payload) && typeof value.payload.token === "string";
  }
  return value.type === "open" || value.type === "close";
}
