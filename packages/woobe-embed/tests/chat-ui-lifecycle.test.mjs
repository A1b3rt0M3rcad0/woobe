import assert from "node:assert/strict";
import { after, afterEach, test } from "node:test";
import { mkdtemp, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import ts from "typescript";
import { JSDOM } from "jsdom";

const directory = await mkdtemp(join(tmpdir(), "woobe-chat-lifecycle-"));
for (const name of ["chat-ui", "appearance", "message-renderer", "skill-activity", "operations"]) {
  const url = name === "operations"
    ? new URL("../../woobe-runtime-client/src/operations.ts", import.meta.url)
    : new URL(`../src/${name}.ts`, import.meta.url);
  const source = await readFile(url, "utf8");
  const output = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
  }).outputText
    .replace(/from ['"]@woobe\/runtime-client['"]/g, "from './operations.mjs'")
    .replace(/from ['"]\.\/([^'"]+?)(?:\.mjs)?['"]/g, "from './$1.mjs'");
  await writeFile(join(directory, `${name}.mjs`), output);
}

const { createChatUi, DEFAULT_APPEARANCE } = await import(
  pathToFileURL(join(directory, "chat-ui.mjs")).href
);
const dom = new JSDOM("<!doctype html><body></body>", { pretendToBeVisual: true });
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  requestAnimationFrame: dom.window.requestAnimationFrame.bind(dom.window),
  cancelAnimationFrame: dom.window.cancelAnimationFrame.bind(dom.window),
});

afterEach(() => document.body.replaceChildren());
after(async () => {
  dom.window.close();
  await rm(directory, { recursive: true, force: true });
});

function statusAppearance() {
  return {
    ...DEFAULT_APPEARANCE,
    activity: {
      ...DEFAULT_APPEARANCE.activity,
      mode: "status",
    },
  };
}

test("retracted terminal candidate returns to pending and restores activity", () => {
  const host = document.createElement("div");
  document.body.append(host);
  const ui = createChatUi(host, statusAppearance());
  const message = ui.appendPendingAssistant();

  ui.updateAssistantActivity(message, {
    status: "generating_answer",
    message: "Generating response...",
  });
  ui.beginAssistantStreaming(message);
  ui.updateAssistantStreaming(message, "Vou procurar.");

  assert.equal(message.classList.contains("message--pending"), false);
  assert.equal(message.classList.contains("message--streaming"), true);

  const label = ui.resetAssistantPending(message, {
    status: "calling_tool",
    message: "Calling tool: search...",
    tool_name: "search",
  });

  assert.equal(label, DEFAULT_APPEARANCE.activity.labels.calling_tool);
  assert.equal(message.classList.contains("message--pending"), true);
  assert.equal(message.classList.contains("message--streaming"), false);
  assert.equal(message.dataset.content, "");
  assert.ok(message.textContent.includes("Using a tool"));
  assert.ok(!message.textContent.includes("Vou procurar"));
});

test("dots mode restores the typing indicator after retraction", () => {
  const host = document.createElement("div");
  document.body.append(host);
  const ui = createChatUi(host, DEFAULT_APPEARANCE);
  const message = ui.appendPendingAssistant();

  ui.beginAssistantStreaming(message);
  ui.updateAssistantStreaming(message, "candidate");
  ui.resetAssistantPending(message, { status: "processing_tool_result" });

  assert.equal(message.classList.contains("message--pending"), true);
  assert.equal(message.querySelectorAll(".typing-indicator > span").length, 3);
  assert.equal(message.getAttribute("aria-label"), "Agent is responding");
});

test("unknown strategy activity uses its explicit public message in status mode", () => {
  const host = document.createElement("div");
  document.body.append(host);
  const ui = createChatUi(host, statusAppearance());
  const message = ui.appendPendingAssistant();

  const label = ui.updateAssistantActivity(message, {
    status: "thinking",
    message: "Evidence analysis...",
  });

  assert.equal(label, "Evidence analysis...");
  assert.ok(message.textContent.includes("Evidence analysis..."));
});
