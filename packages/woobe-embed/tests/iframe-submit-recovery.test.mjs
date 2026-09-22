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
  const eventLine = frame.split(/\\r?\\n/).find((line) => line.startsWith("event:"));
  const dataLine = frame.split(/\\r?\\n/).find((line) => line.startsWith("data:"));
  if (!dataLine) return null;
  const data = JSON.parse(dataLine.slice(5).trim());
  const eventType = eventLine?.slice(6).trim() || data.type;
  const payload = data.payload && typeof data.payload === "object" ? data.payload : data;
  return {
    kind: "semantic",
    eventType,
    data,
    payload,
    sequence: typeof data.sequence === "number" ? data.sequence : null,
  };
};
const runtimeAssistantMessage = (parsed) => {
  if (!["assistant_message_delta", "assistant_message_completed"].includes(parsed?.eventType)) return null;
  const value = parsed.payload;
  if (
    !value
    || typeof value.message_id !== "string"
    || !value.message_id
    || typeof value.content !== "string"
    || value.output_mode !== "intermediate"
  ) return null;
  return {
    message_id: value.message_id,
    content: value.content,
    output_mode: "intermediate",
    phase: typeof value.phase === "string" ? value.phase : null,
    provider: typeof value.provider === "string" ? value.provider : null,
    model: typeof value.model === "string" ? value.model : null,
    partial: typeof value.partial === "boolean" ? value.partial : null,
    status: typeof value.status === "string" ? value.status : null,
    completed_at: typeof value.completed_at === "string" ? value.completed_at : null,
  };
};
const runtimeStateAssistantMessages = (parsed) => {
  if (parsed?.eventType !== "run.state" || !Array.isArray(parsed.payload?.messages)) return [];
  return parsed.payload.messages
    .map((message) => runtimeAssistantMessage({
      eventType: "assistant_message_completed",
      payload: message,
    }))
    .filter(Boolean);
};
const runtimeTerminalStatus = (parsed) => {
  if (parsed?.eventType === "done" || parsed?.eventType === "execution_completed") return "completed";
  if (parsed?.eventType === "cancelled" || parsed?.eventType === "execution_cancelled") return "cancelled";
  if (parsed?.eventType === "error" || parsed?.eventType === "execution_failed") return "failed";
  if (parsed?.eventType === "run.state") {
    return ["completed", "failed", "cancelled", "timed_out", "uncertain"].includes(parsed.payload?.status)
      ? parsed.payload.status
      : null;
  }
  return null;
};
const createChatUi = () => globalThis.__ui;
`
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
  const element = (role, content, pending = false) => ({
    role,
    content,
    pending,
    dataset: { content },
  });
  const ui = {
    setAppearance() {},
    setStopping() {},
    showSessionExpired() {},
    clearSessionExpired() {},
    clearMessages() {
      messages.splice(0, messages.length);
    },
    appendMessage(role, content) {
      const item = element(role, content);
      messages.push(item);
      return item;
    },
    insertMessageBefore(role, content, before) {
      const item = element(role, content);
      const index = messages.indexOf(before);
      if (index >= 0) messages.splice(index, 0, item);
      else messages.push(item);
      return item;
    },
    appendPendingAssistant() {
      const item = element("assistant", "", true);
      messages.push(item);
      return item;
    },
    beginAssistantStreaming(item) {
      item.pending = false;
      item.content = "";
      item.dataset.content = "";
    },
    updateAssistantStreaming(item, content) {
      item.content = content;
      item.dataset.content = content;
    },
    updateAssistantActivity() {
      return "";
    },
    updateSkillActivity() {},
    finishAssistantStreaming(item) {
      item.pending = false;
    },
    removeMessage(item) {
      const index = messages.indexOf(item);
      if (index >= 0) messages.splice(index, 1);
    },
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

test("pre-Tool public text becomes a durable intermediate bubble instead of disappearing", async () => {
  const stream = [
    ["token", { content: "Vou procurar.", message_id: "message-final", output_mode: "final" }],
    ["assistant_message_completed", {
      message_id: "message-progress-1",
      content: "Vou procurar.",
      phase: "capability_response_generation",
      output_mode: "intermediate",
      partial: false,
    }],
    ["token_retract", {
      message_id: "message-final",
      content_length: "Vou procurar.".length,
      reason: "tool_call_selected",
    }],
    ["assistant_message_completed", {
      message_id: "message-progress-2",
      content: "Não encontrei. Vou tentar outra possibilidade.",
      phase: "tool_followup_1",
      output_mode: "intermediate",
      partial: false,
    }],
    ["token", { content: "Resultado final.", message_id: "message-final", output_mode: "final" }],
    ["done", { answer: "Resultado final.", message_id: "message-final" }],
  ].map(([type, payload], index) =>
    `event: ${type}\ndata: ${JSON.stringify({
      protocol_version: 2,
      type,
      sequence: index + 1,
      payload,
    })}\n\n`
  ).join("");

  const harness = await loadIframeHarness(async (url) => {
    const pathname = new URL(String(url)).pathname;
    if (pathname.endsWith("/messages:stream")) {
      return new Response(stream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      });
    }
    throw new Error(`Unexpected request: ${pathname}`);
  });

  await harness.sendMessage("procure");

  assert.deepEqual(
    JSON.parse(JSON.stringify(harness.messages.map(({ role, content, dataset }) => ({
      role,
      content,
      messageId: dataset.messageId ?? null,
      outputMode: dataset.outputMode ?? null,
    })))),
    [
      { role: "user", content: "procure", messageId: null, outputMode: null },
      {
        role: "assistant",
        content: "Vou procurar.",
        messageId: "message-progress-1",
        outputMode: "intermediate",
      },
      {
        role: "assistant",
        content: "Não encontrei. Vou tentar outra possibilidade.",
        messageId: "message-progress-2",
        outputMode: "intermediate",
      },
      { role: "assistant", content: "Resultado final.", messageId: null, outputMode: null },
    ],
  );
  assert.deepEqual(harness.errors, []);
});

test("reattach run.state restores intermediate messages before the terminal output", async () => {
  const stateStream = [
    ["run.state", {
      status: "running",
      output: "Resposta parcial",
      messages: [
        {
          message_id: "message-progress-1",
          content: "Vou procurar.",
          phase: "search",
          output_mode: "intermediate",
          partial: false,
          status: "completed",
        },
        {
          message_id: "message-progress-2",
          content: "Achei algo. Vou validar.",
          phase: "verification",
          output_mode: "intermediate",
          partial: false,
          status: "completed",
        },
      ],
    }],
    ["done", { answer: "Resposta final.", message_id: "message-final" }],
  ].map(([type, payload], index) =>
    `event: ${type}\ndata: ${JSON.stringify({
      protocol_version: 2,
      type,
      sequence: index + 1,
      payload,
    })}\n\n`
  ).join("");

  const harness = await loadIframeHarness(async (url) => {
    const pathname = new URL(String(url)).pathname;
    if (pathname.endsWith("/messages:stream")) {
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
    if (pathname.endsWith("/active-run/stream")) {
      return new Response(stateStream, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      });
    }
    throw new Error(`Unexpected request: ${pathname}`);
  });

  await harness.sendMessage("continue");

  assert.deepEqual(
    JSON.parse(JSON.stringify(harness.messages.map(({ role, content, dataset }) => ({
      role,
      content,
      messageId: dataset.messageId ?? null,
    })))),
    [
      { role: "user", content: "continue", messageId: null },
      { role: "assistant", content: "Vou procurar.", messageId: "message-progress-1" },
      { role: "assistant", content: "Achei algo. Vou validar.", messageId: "message-progress-2" },
      { role: "assistant", content: "Resposta final.", messageId: null },
    ],
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
