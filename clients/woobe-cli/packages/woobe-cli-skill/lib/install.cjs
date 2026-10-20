'use strict';
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const crypto = require('node:crypto');

const packageRoot = path.resolve(__dirname, '..');
const metadata = require('../package.json');
const name = 'woobe-cli';
const marker = '.woobe-skill-install.json';
const presets = {
  codex: { project: '.agents/skills', user: '.agents/skills' },
  'codex-legacy': { project: '.codex/skills', user: '.codex/skills' },
  claude: { project: '.claude/skills', user: '.claude/skills' },
  copilot: { project: '.github/skills', user: '.copilot/skills' },
  cursor: { project: '.cursor/skills', user: '.cursor/skills' },
  agents: { project: '.agents/skills', user: '.agents/skills' }
};
const digest = data => crypto.createHash('sha256').update(data).digest('hex');
const exists = file => { try { return fs.lstatSync(file); } catch (e) { if (e.code === 'ENOENT') return null; throw e; } };
function regular(file) {
  const info = fs.lstatSync(file);
  if (!info.isFile() || info.isSymbolicLink() || info.nlink !== 1 || info.size > 1024 * 1024) throw new Error(`unsafe or oversized skill file: ${file}`);
  return fs.readFileSync(file);
}
function inventory(directory, prefix = '') {
  const files = {};
  for (const item of fs.readdirSync(directory, { withFileTypes: true }).sort((a,b) => a.name.localeCompare(b.name))) {
    const relative = prefix + item.name;
    const target = path.join(directory, item.name);
    if (item.isSymbolicLink()) throw new Error(`linked skill path: ${target}`);
    if (item.isDirectory()) Object.assign(files, inventory(target, relative + '/'));
    else files[relative] = regular(target);
    if (Object.keys(files).length > 64) throw new Error('skill file count exceeds 64');
  }
  return files;
}
function safeParents(target) {
  const absolute = path.resolve(target);
  let parent = path.parse(absolute).root;
  for (const part of absolute.slice(parent.length).split(path.sep).filter(Boolean)) {
    parent = path.join(parent, part);
    const info = exists(parent);
    if (info && (!info.isDirectory() || info.isSymbolicLink())) throw new Error(`installation directory must be a real directory: ${parent}`);
  }
}
function targets(options, cwd = process.cwd(), home = os.homedir()) {
  if (options.scope && !['project', 'user'].includes(options.scope)) throw new Error('--scope must be project or user');
  if (options.path && (options.agent.length || options.scope || options.project)) throw new Error('--path cannot be combined with --agent, --scope or --project');
  if (options.scope === 'user' && options.project) throw new Error('--project cannot be used with user scope');
  if (options.path) {
    const root = path.resolve(fs.realpathSync(cwd), options.path);
    return [path.join(root, name)];
  }
  const scope = options.scope || 'project';
  const root = fs.realpathSync(scope === 'user' ? home : path.resolve(cwd, options.project || '.'));
  const selected = options.agent.length ? options.agent : ['codex'];
  return [...new Set(selected.map(agent => {
    if (!presets[agent]) throw new Error(`unknown agent ${agent}; choose ${Object.keys(presets).join(', ')}`);
    const base = agent === 'codex-legacy' && scope === 'user' && process.env.CODEX_HOME ? path.resolve(process.env.CODEX_HOME, 'skills') : path.join(root, presets[agent][scope]);
    return path.join(base, name);
  }))];
}
function inspect(target) {
  safeParents(target);
  if (!exists(target)) return { status: 'absent', target };
  const files = inventory(target);
  if (!files[marker]) return { status: 'unmanaged', target };
  let recorded;
  try { recorded = JSON.parse(files[marker]); } catch { throw new Error(`invalid installation receipt: ${target}`); }
  if (recorded.schema_version !== 1 || recorded.package !== metadata.name || typeof recorded.version !== 'string' || !recorded.files || Array.isArray(recorded.files) || typeof recorded.files !== 'object' || !recorded.files['SKILL.md']) throw new Error(`invalid installation receipt: ${target}`);
  const names = Object.keys(recorded.files);
  if (names.length > 64 || names.some(file => !/^[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.-]+)*$/.test(file) || file.split('/').some(x => x === '.' || x === '..') || !/^[a-f0-9]{64}$/.test(recorded.files[file]))) throw new Error(`invalid receipt inventory: ${target}`);
  const changed = names.filter(file => !files[file] || digest(files[file]) !== recorded.files[file]);
  const extra = Object.keys(files).filter(file => file !== marker && !names.includes(file));
  return { status: changed.length || extra.length ? 'modified' : 'managed', target, version: recorded.version, changed, extra };
}
function plan(action, options) {
  const payload = inventory(path.join(packageRoot, 'skills', name));
  const hashes = Object.fromEntries(Object.entries(payload).map(([file, data]) => [file, digest(data)]));
  const destinations = targets(options);
  const rows = destinations.map(inspect);
  if (action === 'status') return { rows, payload, hashes };
  for (const row of rows) {
    if (row.status === 'unmanaged' || row.status === 'modified') throw new Error(`refusing to ${action} ${row.status} skill at ${row.target}; preserve or move your local files before retrying`);
  }
  return { rows, payload, hashes };
}
function run(action, options) {
  const planned = plan(action, options);
  if (action === 'status' || options.dryRun) return { action, executed: false, package: metadata.name, version: metadata.version, installations: planned.rows };
  const locked = [];
  const changes = [];
  try {
    // Lock every destination and repeat preflight before changing any skill.
    for (const row of planned.rows) {
      if (action === 'uninstall' && row.status === 'absent') continue;
      const parent = path.dirname(row.target);
      safeParents(parent);
      fs.mkdirSync(parent, { recursive: true });
      const lock = path.join(parent, '.woobe-cli.install.lock');
      const fd = fs.openSync(lock, 'wx', 0o600);
      locked.push({ lock, fd });
    }
    const rechecked = plan(action, options);
    for (const row of rechecked.rows) {
      if (action === 'uninstall' && row.status === 'absent') continue;
      const parent = path.dirname(row.target);
      const stage = fs.mkdtempSync(path.join(parent, '.woobe-cli-stage-'));
      const change = { target: row.target, stage, backup: null, installed: false };
      changes.push(change);
      if (action === 'install') {
        for (const [relative, data] of Object.entries(rechecked.payload)) {
          const file = path.join(stage, relative);
          fs.mkdirSync(path.dirname(file), { recursive: true });
          fs.writeFileSync(file, data, { flag: 'wx' });
        }
        fs.writeFileSync(path.join(stage, marker), JSON.stringify({ schema_version: 1, package: metadata.name, version: metadata.version, source_commit: metadata.woobeSkill.sourceCommit || null, files: rechecked.hashes }, null, 2) + '\n', { flag: 'wx' });
      }
      if (row.status !== 'absent') {
        const previous = inspect(row.target);
        if (previous.status !== row.status || previous.version !== row.version) throw new Error(`skill changed during installation: ${row.target}`);
        const backup = stage + '-previous';
        fs.renameSync(row.target, backup);
        change.backup = backup;
      } else if (exists(row.target)) {
        throw new Error(`destination appeared during installation: ${row.target}`);
      }
      if (action === 'install') { fs.renameSync(stage, row.target); change.installed = true; }
    }
  } catch (error) {
    for (const change of changes.reverse()) {
      if (change.installed) {
        if (inspect(change.target).status !== 'managed') throw new Error(`rollback preserved changed installation at ${change.target}; original backup: ${change.backup || 'none'}; original error: ${error.message}`);
        fs.rmSync(change.target, { recursive: true });
      }
      if (change.backup) fs.renameSync(change.backup, change.target);
      fs.rmSync(change.stage, { recursive: true, force: true });
    }
    throw error;
  } finally {
    for (const { lock, fd } of locked.reverse()) { fs.closeSync(fd); fs.unlinkSync(lock); }
  }
  for (const change of changes) {
    if (change.backup) fs.rmSync(change.backup, { recursive: true });
    fs.rmSync(change.stage, { recursive: true, force: true });
  }
  return { action, executed: true, package: metadata.name, version: metadata.version, installations: planned.rows.map(row => ({ target: row.target, status: action === 'install' ? 'installed' : 'absent' })) };
}
function parse(args) {
  const options = { agent: [], json: false, dryRun: false };
  let action = 'install';
  if (args[0] && !args[0].startsWith('-')) action = args.shift();
  for (let i=0; i<args.length; i++) {
    const flag = args[i];
    if (flag === '--help' || flag === '-h') { options.help = true; continue; }
    if (flag === '--version' || flag === '-v') { options.version = true; continue; }
    if (flag === '--json') { options.json = true; continue; }
    if (flag === '--dry-run') { options.dryRun = true; continue; }
    if (!['--agent','--scope','--project','--path'].includes(flag)) throw new Error(`unknown flag ${flag}`);
    const value = args[++i];
    if (!value || value.startsWith('--')) throw new Error(`${flag} requires a value`);
    if (flag === '--agent') options.agent.push(...value.split(','));
    else {
      const key = flag.slice(2);
      if (options[key]) throw new Error(`${flag} may only be supplied once`);
      options[key] = value;
    }
  }
  if (!['install','status','uninstall','agents'].includes(action)) throw new Error(`unknown command ${action}`);
  return { action, options };
}
function main(args) {
  const { action, options } = parse([...args]);
  if (options.help) {
    console.log('woobe-skill install|status|uninstall [--agent codex,claude,copilot,cursor,codex-legacy,agents] [--scope project|user] [--project DIR] [--dry-run] [--json]\nwoobe-skill install --path CUSTOM_SKILLS_DIR\nwoobe-skill agents\nDefault: Codex project skill in .agents/skills/woobe-cli. Installation is explicit; npm install alone never writes agent settings. Locally edited or unmanaged skills are preserved.');
    return;
  }
  if (options.version) { console.log(metadata.version); return; }
  const result = action === 'agents' ? { agents: presets } : run(action, options);
  if (options.json) console.log(JSON.stringify(result));
  else if (action === 'agents') {
    console.log('AGENT          PROJECT SKILLS ROOT       USER SKILLS ROOT');
    for (const [agent, roots] of Object.entries(presets)) console.log(`${agent.padEnd(15)}${roots.project.padEnd(26)}~/${roots.user}`);
  }
  else {
    console.log(`${result.action}: woobe-cli skill ${result.version}${result.executed ? '' : ' (read-only)'}`);
    for (const row of result.installations) console.log(`${row.status}: ${row.target}${row.version ? ' ('+row.version+')' : ''}`);
  }
}
module.exports = { main, run, targets, inspect, parse, presets };
