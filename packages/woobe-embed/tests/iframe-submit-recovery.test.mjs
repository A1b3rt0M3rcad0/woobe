import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import test from "node:test";
import ts from "typescript";

function stripImports(source) {
  const sourceFile = ts.createSourceFile(
    "iframe.ts",
    source,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  const imports = sourceFile.statements.filter((statement) =>
    ts.isImportDeclaration(statement),
  );
  let cursor = 0;
  let stripped = "";
  for (const declaration of imports) {
    stripped += source.slice(cursor, declaration.getFullStart());
    cursor = declaration.end;
  }
  return stripped + source.slice(cursor);
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
  const sourceFile = ts.createSourceFile(
    "iframe.ts",
    raw,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TS,
  );
  assert.ok(
    sourceFile.statements.some(
      (statement) =>
        ts.isFunctionDeclaration(statement) && statement.name?.text === "sendMessage",
    ),
    "iframe source must expose the sendMessage function expected by the recovery harness",
  );
  const source = stripImports(raw);
  const prelude = `
const normalizeAppearance = (value) => value;
const DEFAULT_APPEARANCE = { welcome_message: "" };
const PROTOCOL_VERSION = 1;
const randomUuid = () => "idempotency-test";
const isHostMessage = () => false;
const RUNTIME_STREAM_MAX_ATTEMPTS = 4;
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
  setExternalContext(value) {
    externalContext = value;
  },
  setSessionExternalContextFields(value) {
    sessionExternalContextFields = new Set(value);
  },
  setLockedExternalContextFields(value) {
    lockedExternalContextFields = new Set(value);
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
  assert.equal(
    typeof context.__woobeIframeTest.sendMessage,
    "function",
    "the iframe recovery harness must expose sendMessage from the evaluated source",
  );
  return {
    sendMessage: context.__woobeIframeTest.sendMessage,
    setExternalContext: context.__woobeIframeTest.setExternalContext,
    setSessionExternalContextFields: context.__woobeIframeTest.setSessionExternalContextFields,
    setLockedExternalContextFields: context.__woobeIframeTest.setLockedExternalContextFields,
    errors,
    messages,
  };
}

test("message submit forwards the current external context", async () => {
  let submittedBody = null;
  const harness = await loadIframeHarness(async (url, init = {}) => {
    const path = new URL(String(url)).pathname;
    if (path.endsWith("/messages:stream")) {
      submittedBody = JSON.parse(String(init.body));
      return sseDone("ok");
    }
    throw new Error(`Unexpected request: ${path}`);
  });

  harness.setExternalContext({
    customer_name: "Mariana Costa",
    plan: "business",
    current_page: "/billing/subscription",
  });
  await harness.sendMessage("Quero alterar meu plano");

  assert.deepEqual(JSON.parse(JSON.stringify(submittedBody)), {
    message: "Quero alterar meu plano",
    external_context: {
      customer_name: "Mariana Costa",
      plan: "business",
      current_page: "/billing/subscription",
    },
  });
  assert.deepEqual(harness.errors, []);
});

test("completed Runs keep the current external context for the next message", async () => {
  const submittedBodies = [];
  const harness = await loadIframeHarness(async (url, init = {}) => {
    const path = new URL(String(url)).pathname;
    if (path.endsWith("/messages:stream")) {
      submittedBodies.push(JSON.parse(String(init.body)));
      return sseDone("ok");
    }
    throw new Error(`Unexpected request: ${path}`);
  });

  harness.setExternalContext({
    customer_id: "cus-1",
    locale: "pt-BR",
  });

  await harness.sendMessage("primeira");
  await harness.sendMessage("segunda");

  assert.equal(submittedBodies.length, 2);
  assert.deepEqual(
    JSON.parse(JSON.stringify(submittedBodies.map((body) => body.external_context))),
    [
      { customer_id: "cus-1", locale: "pt-BR" },
      { customer_id: "cus-1", locale: "pt-BR" },
    ],
    "terminal Run completion must not clear the iframe External Context working values",
  );
  assert.deepEqual(harness.errors, []);
});

test("session-scoped External Context is sent once and omitted from later messages", async () => {
  const submittedBodies = [];
  const harness = await loadIframeHarness(async (url, init = {}) => {
    const path = new URL(String(url)).pathname;
    if (path.endsWith("/messages:stream")) {
      submittedBodies.push(JSON.parse(String(init.body)));
      return sseDone("ok");
    }
    if (path.endsWith("/surface")) {
      return Response.json({
        success: true,
        data: {
          surface_id: "surface-1",
          name: "Support",
          appearance: { welcome_message: "" },
          protocol_version: 1,
          external_context_session_fields: ["customer_id"],
          external_context_locked_fields: ["customer_id"],
        },
      });
    }
    throw new Error(`Unexpected request: ${path}`);
  });

  harness.setExternalContext({ customer_id: "cus-1", current_page: "/billing" });
  harness.setSessionExternalContextFields(["customer_id"]);

  await harness.sendMessage("primeira");
  await harness.sendMessage("segunda");

  assert.deepEqual(
    JSON.parse(JSON.stringify(submittedBodies.map((body) => body.external_context))),
    [
      { customer_id: "cus-1", current_page: "/billing" },
      { current_page: "/billing" },
    ],
  );
  assert.deepEqual(harness.errors, []);
});

test("ambiguous submit failure performs one canonical active Run lookup instead of polling the endpoint", async () => {
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
      return Response.json({ success: true, data: null });
    }
    if (path.endsWith("/active-run/stream")) {
      throw new Error("no Run identity was recovered, so reattach must not start");
    }
    throw new Error(`Unexpected request: ${path}`);
  });

  await harness.sendMessage("hello");

  assert.equal(
    calls.filter((call) => call.path.endsWith("/messages:stream")).length,
    1,
    "recovery must never resubmit the user message",
  );
  assert.equal(
    activeLookups,
    1,
    "the browser must delegate canonical identity reconciliation to one active-run request instead of creating a polling storm",
  );
  assert.equal(
    calls.filter((call) => call.path.endsWith("/active-run/stream")).length,
    0,
  );
  assert.equal(harness.errors.length, 1);
});

test("structured 409 active Run conflict reattaches directly without polling active-run", async () => {
  const calls = [];
  const harness = await loadIframeHarness(async (url, init = {}) => {
    const path = new URL(String(url)).pathname;
    calls.push({ path, method: init.method ?? "GET" });

    if (path.endsWith("/messages:stream")) {
      return new Response(
        JSON.stringify({
          success: false,
          message: "ChatSurface Session already has an active Run",
          data: {
            code: "active_run_conflict",
            run_id: "run-1",
            status: "running",
            target_type: "agent",
          },
        }),
        { status: 409, headers: { "Content-Type": "application/json" } },
      );
    }
    if (path.endsWith("/active-run")) {
      throw new Error("a structured active-run conflict must not trigger active-run polling");
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
    0,
    "the 409 already carries the canonical Run identity",
  );
  assert.equal(
    calls.filter((call) => call.path.endsWith("/active-run/stream")).length,
    1,
    "the existing canonical Run must be observed directly",
  );
  assert.deepEqual(harness.errors, []);
});

test("legacy 409 without Run identity performs at most one active-run fallback lookup", async () => {
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

  await harness.sendMessage("legacy conflict");

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

test("terminal frame drains the HTTP stream instead of cancelling server finalization", async () => {
  let pulls = 0;
  let cancelled = false;
  const encoder = new TextEncoder();
  const terminalBody = new ReadableStream({
    pull(controller) {
      pulls += 1;
      if (pulls === 1) {
        controller.enqueue(
          encoder.encode(
            `event: done\ndata: ${JSON.stringify({ type: "done", answer: "ok" })}\n\n`,
          ),
        );
        return;
      }
      controller.close();
    },
    cancel() {
      cancelled = true;
    },
  });

  const harness = await loadIframeHarness(async (url) => {
    const path = new URL(String(url)).pathname;
    if (path.endsWith("/messages:stream")) {
      return new Response(terminalBody, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      });
    }
    throw new Error(`Unexpected request: ${path}`);
  });

  await harness.sendMessage("hello");

  assert.equal(cancelled, false, "terminal SSE must not abort the server-side response body");
  assert.ok(pulls >= 2, "the observer must read through server EOF after the terminal frame");
  assert.deepEqual(harness.errors, []);
});
