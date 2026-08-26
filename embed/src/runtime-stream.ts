export type RuntimeTerminalStatus =
  | "completed"
  | "failed"
  | "cancelled"
  | "timed_out"
  | "uncertain";

export interface RuntimeSequenceState {
  sequence: number | null;
}

export interface ParsedRuntimeFrame {
  eventType: string;
  data: Record<string, unknown>;
  payload: Record<string, unknown>;
  sequence: number | null;
}

export class RuntimeStreamGapError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RuntimeStreamGapError";
  }
}

function objectValue(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function sequenceValue(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= 0
    ? value
    : null;
}

export function parseRuntimeFrame(frame: string): ParsedRuntimeFrame | null {
  const lines = frame.split(/\r?\n/);
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const idLine = lines.find((line) => line.startsWith("id:"));
  const dataLines = lines.filter((line) => line.startsWith("data:"));
  if (!dataLines.length) return null;

  const parsed = JSON.parse(
    dataLines.map((line) => line.slice(5).trimStart()).join("\n"),
  ) as unknown;
  const data = objectValue(parsed);
  if (!data) return null;
  const payload = objectValue(data.data) ?? data;
  const eventType = eventLine?.slice(6).trim()
    || (typeof data.type === "string" ? data.type : "message");
  const headerSequence = sequenceValue(data.sequence);
  const payloadSequence = sequenceValue(payload.sequence);
  const id = idLine?.slice(3).trim() ?? "";
  const idSequence = /^\d+$/.test(id) ? Number(id) : null;

  return {
    eventType,
    data,
    payload,
    sequence: headerSequence ?? payloadSequence ?? idSequence,
  };
}

export function acceptRuntimeFrameSequence(
  frame: ParsedRuntimeFrame,
  state: RuntimeSequenceState,
): boolean {
  const sequence = frame.sequence;
  if (sequence === null) return true;

  if (frame.eventType === "run.state") {
    if (state.sequence !== null && sequence < state.sequence) return false;
    state.sequence = sequence;
    return true;
  }

  if (state.sequence !== null) {
    if (sequence <= state.sequence) return false;
    const expected = state.sequence + 1;
    if (sequence !== expected) {
      throw new RuntimeStreamGapError(
        `Runtime stream sequence gap: expected ${expected}, received ${sequence}`,
      );
    }
  }
  state.sequence = sequence;
  return true;
}

export function runtimeTerminalStatus(
  frame: ParsedRuntimeFrame,
): RuntimeTerminalStatus | null {
  if (frame.eventType === "run.state") {
    const status = typeof frame.payload.status === "string"
      ? frame.payload.status
      : "";
    if (
      status === "completed"
      || status === "failed"
      || status === "cancelled"
      || status === "timed_out"
      || status === "uncertain"
    ) {
      return status;
    }
    return null;
  }

  if (frame.eventType === "done" || frame.eventType === "execution_completed") {
    return "completed";
  }
  if (frame.eventType === "cancelled" || frame.eventType === "execution_cancelled") {
    return "cancelled";
  }
  if (frame.eventType === "execution_timed_out") return "timed_out";
  if (frame.eventType === "error" || frame.eventType === "execution_failed") {
    return frame.payload.uncertain === true ? "uncertain" : "failed";
  }
  return null;
}
