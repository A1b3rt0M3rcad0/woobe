import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import test from "node:test";
import ts from "typescript";

function stripImports(source) {
  const lines = source.split("\n");
  const kept = [];
  let skipping = false;
  for (const line of lines) {
    const trimmed = line.trimStart();
    if (!skipping && trimmed.startsWith("import ")) {
      skipping = !trimmed.endsWith(";");
      continue;
    }
    if (skipping) {
      if (trimmed.endsWith(";")) skipping = false;
      continue;
    }
    kept.push(line);
  }
  return kept.join("\n");
}

function sseDone(answer = "recovered") {
  return new Response(
    `event: done\ndata: ${JSON.stringify({ type: "done", answer })}\n\n`,
    {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    },
  );
}

async function loadIframeHarness(fetchImpl) {
  const raw = await readFile(new URL("../src/iframe.ts", import.meta.url), "utf8");
  const source = stripImports(raw);
  const prelude = `
const normalizeAppearance = (value) => value;
const DEFAULT_APPEARANCE = { welcome_message: "" };
const PROTOCOL_VERSION = 1;
const randomUuid = () => "idempotency-test";
const isHostMessage = () => false;
class RuntimeStreamGapError extends Error {}
const acceptRuntimeFrameSequence = () => true;
const parseRuntimeFrame = (frame) => {
  if (!frame.includes("event: done")) return null;
  const dataLine = frame.split(/\\r?\\n/).find((line) => line.startsWith("data:"));
  const data = dataLine ? JSON.parse(dataLine.slice(5).trim()) : {};
  return { eventType: "done", data, payload: data, sequence: null };
};
const runtimeTerminalStatus = (parsed) => parsed?.eventType === "done" ? "completed" : null;
const createChatUi = () => globalThis.__ui;
`;
  const hooks = `
globalThis.__woobeIframeTest = {
  sendMessage,
  configure() {
    parentOrigin = "https://host.example.com";
    hostOrigin = "https://host.example.com";
    apiBaseUrl = "http://woobe.test";
    sessionToken = "test-token";
    sessionId = "session-1";
    initialized = true;
    ui = globalThis.__ui;
  },
};
`;
  const output = ts.transpileModule(`${prelude}\n${source}\n${hooks}`, {
    compilerOptions: {
      module: ts.ModuleKind.None,
      target: ts.ScriptTarget.ES2022,
      strict: true,
    },
  }).outputText;

  const errors = [];
  const messages = [];
  const ui = {
    setAppearance() {},
    setStopping() {},
    showSessionExpired() {},
    clearSessionExpired() {},
    clearMessages() {},
    appendMessage(role, content) {
      messages.push({ role, content });
      return {};
    },
    appendPendingAssistant() {
      return {};
    },
    beginAssistantStreaming() {},
    updateAssistantStreaming() {},
    updateAssistantActivity() {
      return "";
    },
    finishAssistantStreaming() {},
    removeMessage() {},
    appendStatus() {},
    appendError(message) {
      errors.push(String(message));
    },
    scrollToLatest() {},
    setSubmitting() {},
    clearComposer() {},
    focusComposer() {},
  };
  const parent = { postMessage() {} };
  const windowObject = {
    location: { search: "?surface=surface-1&instance=instance-1" },
    parent,
    addEventListener() {},
    setTimeout(callback) {
      callback();
      return 0;
    },
    clearTimeout() {},
  };
  const context = vm.createContext({
    console,
    URL,
    URLSearchParams,
    Response,
    Request,
    Headers,
    ReadableStream,
    TextEncoder,
    TextDecoder,
    setTimeout,
    clearTimeout,
    fetch: fetchImpl,
    window: windowObject,
    document: { querySelector: () => ({}) },
    __ui: ui,
  });
  vm.runInContext(output, context, { filename: "iframe-under-test.js" });
  context.__woobeIframeTest.configure();
  return {
    sendMessage: context.__woobeIframeTest.sendMessage,
    errors,
    messages,
  };
}

test("submit failure waits for delayed active Run identity and reattaches instead of orphaning the Run", async () => {
  const calls = [];
  let activeLookups = 0;
  const harness = await loadIframeHarness(async (url, init = {}) => {
    const path = new URL(String(url)).pathname;
    calls.push({ path, method: init.method ?? "GET" });

    if (path.endsWith("/messages:stream")) {
      return new Response(
        JSON.stringify({ success: false, message: "Internal server error", data: null }),
        { status: 500, headers: { "Content-Type": "application/json" } },
      );
    }
    if (path.endsWith("/active-run")) {
      activeLookups += 1;
      const data = activeLookups < 2
        ? null
        : {
            message_request_id: "message-request-1",
            run_id: "run-1",
            status: "running",
            target_type: "agent",
          };
      return Response.json({ success: true, data });
    }
    if (path.endsWith("/active-run/stream")) {
      return sseDone();
    }
    throw new Error(`Unexpected request: ${path}`);
  });

  await harness.sendMessage("hello");

  assert.equal(
    calls.filter((call) => call.path.endsWith("/messages:stream")).length,
    1,
    "recovery must never resubmit the user message",
  );
  assert.ok(
    activeLookups >= 2,
    "active Run identity must be retried when Acceptance won but identity is not visible yet",
  );
  assert.equal(
    calls.filter((call) => call.path.endsWith("/active-run/stream")).length,
    1,
    "the already accepted Run must be observed through reattach",
  );
  assert.deepEqual(harness.errors, []);
});

test("409 active Run conflict is recovered by reattaching and never creates a second message", async () => {
  const calls = [];
  const harness = await loadIframeHarness(async (url, init = {}) => {
    const path = new URL(String(url)).pathname;
    calls.push({ path, method: init.method ?? "GET" });

    if (path.endsWith("/messages:stream")) {
      return new Response(
        JSON.stringify({
          success: false,
          message: "ChatSurface Session already has an active Run",
          data: null,
        }),
        { status: 409, headers: { "Content-Type": "application/json" } },
      );
    }
    if (path.endsWith("/active-run")) {
      return Response.json({
        success: true,
        data: {
          message_request_id: "message-request-1",
          run_id: "run-1",
          status: "running",
          target_type: "agent",
        },
      });
    }
    if (path.endsWith("/active-run/stream")) {
      return sseDone();
    }
    throw new Error(`Unexpected request: ${path}`);
  });

  await harness.sendMessage("second attempt");

  assert.equal(
    calls.filter((call) => call.path.endsWith("/messages:stream")).length,
    1,
  );
  assert.equal(
    calls.filter((call) => call.path.endsWith("/active-run")).length,
    1,
  );
  assert.equal(
    calls.filter((call) => call.path.endsWith("/active-run/stream")).length,
    1,
  );
  assert.deepEqual(harness.errors, []);
});
