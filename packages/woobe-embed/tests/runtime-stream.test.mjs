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
  for (const moduleName of ["types", "protocol", "sse", "observer", "index"]) {
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

test("reattach accepts state jump 125 to 131 and then contiguous 132", () => {
  const state = { sequence: 125 };
  const projection = runtime.parseRuntimeFrame(
    'id: 131\nevent: run.state\ndata: {"type":"run.state","sequence":131,"status":"running","output":"current"}',
  );
  assert.ok(projection);
  assert.equal(runtime.acceptRuntimeFrameSequence(projection, state), true);
  assert.equal(state.sequence, 131);

  const live = runtime.parseRuntimeFrame(
    'id: 132\nevent: token\ndata: {"type":"token","sequence":132,"content":"next"}',
  );
  assert.ok(live);
  assert.equal(runtime.acceptRuntimeFrameSequence(live, state), true);
  assert.equal(state.sequence, 132);
});

test("network envelope resolves nested payload and logical sequence", () => {
  const frame = runtime.parseRuntimeFrame(
    'id: 7\nevent: run.state\ndata: {"protocol_version":1,"sequence":7,"execution_id":"run-1","data":{"status":"running","output":"hello","sequence":7}}',
  );
  assert.ok(frame);
  assert.equal(frame.sequence, 7);
  assert.equal(frame.payload.output, "hello");
  assert.equal(frame.payload.status, "running");
});

test("duplicate incremental event is ignored", () => {
  const state = { sequence: 10 };
  const duplicate = runtime.parseRuntimeFrame(
    'id: 10\nevent: token\ndata: {"type":"token","sequence":10,"content":"duplicate"}',
  );
  assert.ok(duplicate);
  assert.equal(runtime.acceptRuntimeFrameSequence(duplicate, state), false);
  assert.equal(state.sequence, 10);
});

test("incremental sequence gap forces reattach", () => {
  const state = { sequence: 10 };
  const skipped = runtime.parseRuntimeFrame(
    'id: 12\nevent: token\ndata: {"type":"token","sequence":12,"content":"gap"}',
  );
  assert.ok(skipped);
  assert.throws(
    () => runtime.acceptRuntimeFrameSequence(skipped, state),
    (error) => error?.name === "RuntimeStreamGapError",
  );
  assert.equal(state.sequence, 10);
});

test("stale replacement state is ignored without rewinding sequence", () => {
  const state = { sequence: 20 };
  const stale = runtime.parseRuntimeFrame(
    'id: 19\nevent: run.state\ndata: {"type":"run.state","sequence":19,"status":"running","output":"old"}',
  );
  assert.ok(stale);
  assert.equal(runtime.acceptRuntimeFrameSequence(stale, state), false);
  assert.equal(state.sequence, 20);
});

test("durable state is accepted without rewinding the hot sequence", () => {
  const state = { sequence: 20 };
  const durable = runtime.parseRuntimeFrame(
    'event: run.state\ndata: {"type":"run.state","status":"cancelled","output":"partial","realtime_available":false}',
  );
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
    'id: 21\nevent: token\ndata: {"protocol_version":1,"sequence":21,"content":',
  );
  assert.equal(malformed, null);
});

test("unsupported declared protocol version is rejected explicitly", () => {
  assert.throws(
    () => runtime.parseRuntimeFrame(
      'id: 1\nevent: token\ndata: {"protocol_version":99,"sequence":1,"content":"x"}',
    ),
    (error) => error?.name === "RuntimeStreamProtocolError",
  );
});

test("terminal state and terminal events are classified explicitly", () => {
  const completed = runtime.parseRuntimeFrame(
    'event: run.state\ndata: {"type":"run.state","sequence":3,"status":"completed","output":"done"}',
  );
  const failed = runtime.parseRuntimeFrame(
    'event: execution_failed\ndata: {"sequence":4,"message":"failed"}',
  );
  const cancelled = runtime.parseRuntimeFrame(
    'event: execution_cancelled\ndata: {"sequence":5,"output":"partial","cancelled":true}',
  );
  const agentCancelled = runtime.parseRuntimeFrame(
    'event: cancelled\ndata: {"sequence":6,"output":"partial","cancelled":true}',
  );
  const timedOut = runtime.parseRuntimeFrame(
    'event: execution_timed_out\ndata: {"sequence":7,"message":"timeout"}',
  );
  const uncertain = runtime.parseRuntimeFrame(
    'event: execution_failed\ndata: {"sequence":8,"uncertain":true}',
  );
  assert.ok(completed && failed && cancelled && agentCancelled && timedOut && uncertain);
  assert.equal(runtime.runtimeTerminalStatus(completed), "completed");
  assert.equal(runtime.runtimeTerminalStatus(failed), "failed");
  assert.equal(runtime.runtimeTerminalStatus(cancelled), "cancelled");
  assert.equal(runtime.runtimeTerminalStatus(agentCancelled), "cancelled");
  assert.equal(runtime.runtimeTerminalStatus(timedOut), "timed_out");
  assert.equal(runtime.runtimeTerminalStatus(uncertain), "uncertain");
});
