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
      type: "open" | "close" | "destroy";
      payload?: never;
    };

export type FrameEventType =
  | "ready"
  | "history.loaded"
  | "message.sent"
  | "run.started"
  | "run.completed"
  | "session.expired"
  | "error"
  | "opened"
  | "closed";

export interface FrameEvent {
  protocolVersion: 1;
  instanceId: string;
  surfaceId: string;
  type: FrameEventType;
  payload?: unknown;
}

export function isHostMessage(value: unknown): value is HostMessage {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<HostMessage>;
  return (
    candidate.protocolVersion === PROTOCOL_VERSION &&
    typeof candidate.instanceId === "string" &&
    typeof candidate.surfaceId === "string" &&
    typeof candidate.type === "string"
  );
}
