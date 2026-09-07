import assert from "node:assert/strict";
import { after, afterEach, describe, test } from "node:test";
import { mkdtemp, readFile, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import ts from "typescript";
import { JSDOM } from "jsdom";

// Exercise the embed's own modules with its declared dependencies and build inputs.
const directory = await mkdtemp(join(tmpdir(), "woobe-skill-ui-"));
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
const { createChatUi, DEFAULT_APPEARANCE } = await import(pathToFileURL(join(directory, "chat-ui.mjs")).href);
const dom = new JSDOM("<!doctype html><body></body>", { pretendToBeVisual: true });
Object.assign(globalThis, {
  window: dom.window,
  document: dom.window.document,
  requestAnimationFrame: dom.window.requestAnimationFrame.bind(dom.window),
  cancelAnimationFrame: dom.window.cancelAnimationFrame.bind(dom.window),
});
afterEach(() => document.body.replaceChildren());
after(async () => { dom.window.close(); await rm(directory, { recursive: true, force: true }); });

const activation = { tool_name: 'skills_activate', tool_call_id: 's1', success: true, status: 'success', output: { success: true, output: { name: 'inverse-math', version: '1.0.0' } } }

describe('ChatSurface Skill activity', () => {
  test('shows explicit activity even with dots and retains evidence after streaming', () => {
    const host = document.createElement('div'); document.body.append(host)
    const ui = createChatUi(host, DEFAULT_APPEARANCE)
    const message = ui.appendPendingAssistant()
    assert.equal(ui.updateAssistantActivity(message, { tool_name: 'skills_activate', status: 'calling_tool' }), 'Activate Skill…')
    ui.updateSkillActivity(message, { ...activation, success: null, status: 'running' })
    ui.updateSkillActivity(message, activation)
    ui.beginAssistantStreaming(message)
    ui.finishAssistantStreaming(message)
    assert.equal(message.querySelectorAll('.skill-activity p').length, 1)
    assert.ok(message.textContent.includes('Activate Skill'))
    assert.ok(message.textContent.includes('completed'))
    assert.ok(!message.textContent.includes('Tool'))
  })
  test('does not leave unfinished Skill activity running after a terminal response', () => {
    const host = document.createElement('div'); document.body.append(host)
    const ui = createChatUi(host, DEFAULT_APPEARANCE)
    const message = ui.appendPendingAssistant()
    ui.updateSkillActivity(message, { tool_name: 'skills_activate', status: 'running' })
    ui.finishAssistantStreaming(message)
    assert.ok(message.textContent.includes('interrupted'))
    assert.ok(!message.textContent.includes('running'))
  })
  test('renders history evidence and respects generic versus named detail', () => {
    const host = document.createElement('div'); document.body.append(host)
    const ui = createChatUi(host, { ...DEFAULT_APPEARANCE, activity: { ...DEFAULT_APPEARANCE.activity, detail_level: 'generic' } })
    const message = ui.appendMessage('assistant', 'Answer')
    ui.updateSkillActivity(message, activation)
    assert.ok(!message.textContent.includes('inverse-math'))
    ui.setAppearance({ ...DEFAULT_APPEARANCE, activity: { ...DEFAULT_APPEARANCE.activity, detail_level: 'named' } })
    ui.updateSkillActivity(message, activation)
    assert.ok(message.textContent.includes('inverse-math @ 1.0.0'))
    ui.updateSkillActivity(message, { tool_name: 'skills_read_resource', skill_name: 'invoice-review', skill_version: '2.0.0', success: true })
    assert.ok(message.textContent.includes('invoice-review @ 2.0.0'))
    ui.updateSkillActivity(message, { tool_name: 'http', success: true })
    assert.equal(message.querySelectorAll('.skill-activity p').length, 2)
  })
})
