import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import ts from "typescript";

async function loadRuntimeModule() {
  const directory = await mkdtemp(join(tmpdir(), "woobe-runtime-client-"));
  const sourceRoot = new URL("../../woobe-runtime-client/src/", import.meta.url);
  for (const moduleName of ["types", "assistant-messages", "protocol", "sse", "observer", "operations", "index"]) {
    const source = await readFile(new URL(`${moduleName}.ts`, sourceRoot), "utf8");
    let output = ts.transpileModule(source, {
      compilerOptions: {
        module: ts.ModuleKind.ES2022,
        target: ts.ScriptTarget.ES2022,
        strict: true,
      },
    }).outputText;
    output = output.replace(/from ['"]\.\/([^'"]+?)(?:\.(?:js|ts|mjs))?['"]/g, "from './$1.mjs'");
    await writeFile(join(directory, `${moduleName}.mjs`), output, "utf8");
  }
  return import(pathToFileURL(join(directory, "index.mjs")).href);
}

const runtime = await loadRuntimeModule();
const occurredAt = "2026-09-16T20:30:00Z";

function semanticFrame({
  type,
  sequence,
  payload = {},
  runId = "run-1",
  sessionId = "session-1",
  runKind = "AGENT",
}) {
  const envelope = {
    protocol_version: 2,
    event_id: `event-${runKind.toLowerCase()}-${sequence}`,
    run_id: runId,
    session_id: sessionId,
    run_kind: runKind,
    sequence,
    type,
    occurred_at: occurredAt,
    payload,
  };
  return `id: ${sequence}\nevent: ${type}\ndata: ${JSON.stringify(envelope)}`;
}

test("reattach accepts state jump 125 to 131 and then contiguous 132", () => {
  const state = { sequence: 125 };
  const projection = runtime.parseRuntimeFrame(semanticFrame({
    type: "run.state",
    sequence: 131,
    payload: { status: "running", output: "current" },
  }));
  assert.ok(projection);
  assert.equal(runtime.acceptRuntimeFrameSequence(projection, state), true);
  assert.equal(state.sequence, 131);

  const live = runtime.parseRuntimeFrame(semanticFrame({
    type: "token",
    sequence: 132,
    payload: { content: "next" },
  }));
  assert.ok(live);
  assert.equal(runtime.acceptRuntimeFrameSequence(live, state), true);
  assert.equal(state.sequence, 132);
});

test("network envelope exposes canonical identity and logical sequence", () => {
  const frame = runtime.parseRuntimeFrame(semanticFrame({
    type: "run.state",
    sequence: 7,
    runId: "network-run-1",
    sessionId: "network-session-1",
    runKind: "NETWORK",
    payload: { status: "running", output: "hello" },
  }));
  assert.ok(frame);
  assert.equal(frame.sequence, 7);
  assert.equal(frame.runId, "network-run-1");
  assert.equal(frame.sessionId, "network-session-1");
  assert.equal(frame.runKind, "NETWORK");
  assert.equal(frame.payload.output, "hello");
  assert.equal(frame.payload.status, "running");
});

test("duplicate incremental event is ignored", () => {
  const state = { sequence: 10 };
  const duplicate = runtime.parseRuntimeFrame(semanticFrame({
    type: "token",
    sequence: 10,
    payload: { content: "duplicate" },
  }));
  assert.ok(duplicate);
  assert.equal(runtime.acceptRuntimeFrameSequence(duplicate, state), false);
  assert.equal(state.sequence, 10);
});

test("incremental sequence gap forces reattach", () => {
  const state = { sequence: 10 };
  const skipped = runtime.parseRuntimeFrame(semanticFrame({
    type: "token",
    sequence: 12,
    payload: { content: "gap" },
  }));
  assert.ok(skipped);
  assert.throws(
    () => runtime.acceptRuntimeFrameSequence(skipped, state),
    (error) => error?.name === "RuntimeStreamGapError",
  );
  assert.equal(state.sequence, 10);
});

test("stale replacement state is ignored without rewinding sequence", () => {
  const state = { sequence: 20 };
  const stale = runtime.parseRuntimeFrame(semanticFrame({
    type: "run.state",
    sequence: 19,
    payload: { status: "running", output: "old" },
  }));
  assert.ok(stale);
  assert.equal(runtime.acceptRuntimeFrameSequence(stale, state), false);
  assert.equal(state.sequence, 20);
});

test("durable state is accepted without rewinding the hot sequence", () => {
  const state = { sequence: 20 };
  const durable = runtime.parseRuntimeFrame(semanticFrame({
    type: "run.state",
    sequence: 0,
    payload: {
      status: "cancelled",
      output: "partial",
      realtime_available: false,
    },
  }));
  assert.ok(durable);
  assert.equal(runtime.acceptRuntimeFrameSequence(durable, state), true);
  assert.equal(state.sequence, 20);
});

test("snapshot output reconciliation is shared and deterministic", () => {
  assert.deepEqual(runtime.reconcileRuntimeOutput("Hello", "Hello world"), {
    output: "Hello world",
    append: " world",
    retract: 0,
    changed: true,
  });
  assert.deepEqual(runtime.reconcileRuntimeOutput("old", "new"), {
    output: "new",
    append: "new",
    retract: 3,
    changed: true,
  });
  assert.deepEqual(runtime.reconcileRuntimeOutput("same", "same"), {
    output: "same",
    append: "",
    retract: 0,
    changed: false,
  });
});

test("retry policy exposes one attempt budget and deterministic backoff", () => {
  assert.equal(runtime.RUNTIME_STREAM_MAX_ATTEMPTS, 4);
  assert.deepEqual([0, 1, 2, 3].map(runtime.runtimeRetryDelayMs), [250, 500, 750, 1000]);
});

test("malformed SSE data is ignored instead of crashing the observer", () => {
  const malformed = runtime.parseRuntimeFrame(
    'id: 21\nevent: token\ndata: {"protocol_version":2,"sequence":21,"payload":',
  );
  assert.equal(malformed, null);
});

test("unsupported declared protocol version is rejected explicitly", () => {
  assert.throws(
    () => runtime.parseRuntimeFrame(
      `event: heartbeat\ndata: ${JSON.stringify({ protocol_version: 99, type: "heartbeat", occurred_at: occurredAt })}`,
    ),
    (error) => error?.name === "RuntimeStreamProtocolError",
  );
});

test("assistant message events expose one typed intermediate message", () => {
  const frame = runtime.parseRuntimeFrame(semanticFrame({
    type: "assistant_message_completed",
    sequence: 30,
    payload: {
      message_id: "message-progress",
      content: "Vou procurar.",
      phase: "capability_response_generation",
      output_mode: "intermediate",
      provider: "custom",
      model: "deepseek-v4-flash",
      partial: false,
      status: "completed",
      completed_at: occurredAt,
    },
  }));
  assert.ok(frame);

  assert.deepEqual(runtime.runtimeAssistantMessage(frame), {
    message_id: "message-progress",
    content: "Vou procurar.",
    phase: "capability_response_generation",
    output_mode: "intermediate",
    provider: "custom",
    model: "deepseek-v4-flash",
    partial: false,
    status: "completed",
    completed_at: occurredAt,
  });
  assert.deepEqual(runtime.runtimeAssistantMessages(frame), [
    runtime.runtimeAssistantMessage(frame),
  ]);
});

test("run.state exposes typed durable intermediate message snapshots", () => {
  const frame = runtime.parseRuntimeFrame(semanticFrame({
    type: "run.state",
    sequence: 31,
    payload: {
      status: "running",
      output: "partial final candidate",
      messages: [
        {
          message_id: "message-1",
          content: "Vou procurar.",
          phase: "search",
          output_mode: "intermediate",
          partial: false,
          status: "completed",
        },
        {
          message_id: "message-2",
          content: "Achei um ponto. Vou validar.",
          phase: "verification",
          output_mode: "intermediate",
          partial: false,
          status: "completed",
        },
        {
          message_id: "",
          content: "invalid",
          output_mode: "intermediate",
        },
      ],
    },
  }));
  assert.ok(frame);

  assert.deepEqual(runtime.runtimeStateAssistantMessages(frame), [
    {
      message_id: "message-1",
      content: "Vou procurar.",
      phase: "search",
      output_mode: "intermediate",
      provider: null,
      model: null,
      partial: false,
      status: "completed",
      completed_at: null,
    },
    {
      message_id: "message-2",
      content: "Achei um ponto. Vou validar.",
      phase: "verification",
      output_mode: "intermediate",
      provider: null,
      model: null,
      partial: false,
      status: "completed",
      completed_at: null,
    },
  ]);
  assert.deepEqual(
    runtime.runtimeAssistantMessages(frame),
    runtime.runtimeStateAssistantMessages(frame),
  );
  assert.equal(runtime.runtimeAssistantMessage(frame), null);
});

test("terminal state and terminal events are classified explicitly", () => {
  const completed = runtime.parseRuntimeFrame(semanticFrame({
    type: "run.state",
    sequence: 3,
    payload: { status: "completed", output: "done" },
  }));
  const failed = runtime.parseRuntimeFrame(semanticFrame({
    type: "execution_failed",
    sequence: 4,
    runKind: "NETWORK",
    payload: { message: "failed" },
  }));
  const cancelled = runtime.parseRuntimeFrame(semanticFrame({
    type: "execution_cancelled",
    sequence: 5,
    runKind: "NETWORK",
    payload: { output: "partial", cancelled: true },
  }));
  const agentCancelled = runtime.parseRuntimeFrame(semanticFrame({
    type: "cancelled",
    sequence: 6,
    payload: { output: "partial", cancelled: true },
  }));
  const timedOut = runtime.parseRuntimeFrame(semanticFrame({
    type: "execution_timed_out",
    sequence: 7,
    runKind: "NETWORK",
    payload: { message: "timeout" },
  }));
  const uncertain = runtime.parseRuntimeFrame(semanticFrame({
    type: "execution_failed",
    sequence: 8,
    runKind: "NETWORK",
    payload: { uncertain: true },
  }));
  assert.ok(completed && failed && cancelled && agentCancelled && timedOut && uncertain);
  assert.equal(runtime.runtimeTerminalStatus(completed), "completed");
  assert.equal(runtime.runtimeTerminalStatus(failed), "failed");
  assert.equal(runtime.runtimeTerminalStatus(cancelled), "cancelled");
  assert.equal(runtime.runtimeTerminalStatus(agentCancelled), "cancelled");
  assert.equal(runtime.runtimeTerminalStatus(timedOut), "timed_out");
  assert.equal(runtime.runtimeTerminalStatus(uncertain), "uncertain");
});
