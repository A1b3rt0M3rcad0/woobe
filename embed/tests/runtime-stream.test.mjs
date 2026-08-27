import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import test from "node:test";
import ts from "typescript";

async function loadRuntimeModule() {
  const source = await readFile(new URL("../src/runtime-stream.ts", import.meta.url), "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.ES2022,
      target: ts.ScriptTarget.ES2022,
      strict: true,
    },
  }).outputText;
  const directory = await mkdtemp(join(tmpdir(), "woobe-runtime-stream-"));
  const file = join(directory, "runtime-stream.mjs");
  await writeFile(file, output, "utf8");
  return import(pathToFileURL(file).href);
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

test("terminal state and terminal events are classified explicitly", () => {
  const completed = runtime.parseRuntimeFrame(
    'event: run.state\ndata: {"type":"run.state","sequence":3,"status":"completed","output":"done"}',
  );
  const failed = runtime.parseRuntimeFrame(
    'event: execution_failed\ndata: {"sequence":4,"message":"failed"}',
  );
  const uncertain = runtime.parseRuntimeFrame(
    'event: execution_failed\ndata: {"sequence":4,"uncertain":true}',
  );
  assert.ok(completed && failed && uncertain);
  assert.equal(runtime.runtimeTerminalStatus(completed), "completed");
  assert.equal(runtime.runtimeTerminalStatus(failed), "failed");
  assert.equal(runtime.runtimeTerminalStatus(uncertain), "uncertain");
});
