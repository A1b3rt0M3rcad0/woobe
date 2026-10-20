'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const cp = require('node:child_process');
const installer = require('../../packages/woobe-cli-skill/lib/install.cjs');
const launcher = path.resolve(__dirname, '../../packages/woobe-cli-skill/bin/woobe-skill.cjs');
const opts = (project, agent=['codex'], more={}) => ({project, agent, ...more});
function sandbox(t) {
  const root = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'woobe-skill-test-')));
  t.after(()=>fs.rmSync(root,{recursive:true,force:true}));
  return root;
}
function skill(root, agent='codex') { return path.join(root, installer.presets[agent].project,'woobe-cli'); }
test('installs exact portable skill for all hosts, deduplicates and updates idempotently', t=>{
  const root=sandbox(t), agents=Object.keys(installer.presets);
  const result=installer.run('install',opts(root,agents));
  assert.equal(result.installations.length,5);
  for (const agent of agents) {
    const target=skill(root,agent);
    assert.equal(installer.inspect(target).status,'managed');
    assert.equal(fs.readFileSync(path.join(target,'SKILL.md'),'utf8'),fs.readFileSync(path.resolve(__dirname,'../../packages/woobe-cli-skill/skills/woobe-cli/SKILL.md'),'utf8'));
    assert.ok(fs.existsSync(path.join(target,'references/development.md')));
    assert.ok(fs.existsSync(path.join(target,'assets/agent-author.yaml')));
  }
  const receipt=path.join(skill(root),'.woobe-skill-install.json');
  const old=JSON.parse(fs.readFileSync(receipt));old.version='0.0.1';fs.writeFileSync(receipt,JSON.stringify(old));
  installer.run('install',opts(root,agents));
  assert.equal(installer.inspect(skill(root)).version,require('../../packages/woobe-cli-skill/package.json').version);
  installer.run('install',opts(root,agents));
});
test('dry-run/status are read-only; custom root and user layouts are explicit',t=>{
  const root=sandbox(t);
  installer.run('install',opts(root,['codex'],{dryRun:true}));
  installer.run('status',opts(root));assert.deepEqual(fs.readdirSync(root),[]);
  const custom=path.join(root,'custom');
  installer.run('install',{agent:[],path:custom});
  assert.equal(installer.inspect(path.join(custom,'woobe-cli')).status,'managed');
  assert.equal(installer.targets({agent:['claude'],scope:'user'},root,root)[0],path.join(root,'.claude/skills/woobe-cli'));
  const home=os.homedir;os.homedir=()=>root;
  try{installer.run('install',{agent:['claude'],scope:'user'});assert.equal(installer.inspect(skill(root,'claude')).status,'managed');}finally{os.homedir=home;}
  const previous=process.env.CODEX_HOME;process.env.CODEX_HOME=path.join(root,'codex-home');
  try{assert.equal(installer.targets({agent:['codex-legacy'],scope:'user'},root,root)[0],path.join(root,'codex-home/skills/woobe-cli'));}
  finally{if(previous===undefined)delete process.env.CODEX_HOME;else process.env.CODEX_HOME=previous;}
});
test('preflight preserves edited, extra and unmanaged files without partial installs',t=>{
  const root=sandbox(t);installer.run('install',opts(root,['claude']));
  const file=path.join(skill(root,'claude'),'SKILL.md');fs.appendFileSync(file,'\nUser changes\n');
  assert.throws(()=>installer.run('install',opts(root,['codex','claude'])),/modified/);
  assert.equal(fs.existsSync(skill(root)),false);
  assert.throws(()=>installer.run('uninstall',opts(root,['claude'])),/modified/);
  assert.match(fs.readFileSync(file,'utf8'),/User changes/);
  const other=sandbox(t);fs.mkdirSync(skill(other),{recursive:true});fs.writeFileSync(path.join(skill(other),'SKILL.md'),'local');
  assert.throws(()=>installer.run('install',opts(other)),/unmanaged/);
  const clean=sandbox(t);installer.run('install',opts(clean));fs.writeFileSync(path.join(skill(clean),'extra.md'),'mine');
  assert.equal(installer.inspect(skill(clean)).status,'modified');assert.throws(()=>installer.run('uninstall',opts(clean)),/modified/);
});
test('uninstall removes only unchanged managed skills and preserves settings',t=>{
  const root=sandbox(t);fs.writeFileSync(path.join(root,'AGENTS.md'),'project rules');fs.writeFileSync(path.join(root,'CLAUDE.md'),'claude rules');
  installer.run('install',opts(root));const sibling=path.join(root,'.agents/skills/other');fs.mkdirSync(sibling);fs.writeFileSync(path.join(sibling,'SKILL.md'),'other');
  installer.run('uninstall',opts(root));installer.run('uninstall',opts(root));
  assert.equal(fs.existsSync(skill(root)),false);assert.equal(fs.readFileSync(path.join(root,'AGENTS.md'),'utf8'),'project rules');assert.ok(fs.existsSync(path.join(sibling,'SKILL.md')));
});
test('rejects malformed/traversal receipts and linked or hardlinked files',t=>{
  const root=sandbox(t);installer.run('install',opts(root));const receipt=path.join(skill(root),'.woobe-skill-install.json');
  fs.writeFileSync(receipt,'{');assert.throws(()=>installer.inspect(skill(root)),/receipt/);
  fs.writeFileSync(receipt,JSON.stringify({schema_version:1,package:'woobe-cli-skill',version:'1',files:{'SKILL.md':'a'.repeat(64),'../outside':'a'.repeat(64)}}));assert.throws(()=>installer.inspect(skill(root)),/receipt inventory/);
  const hard=sandbox(t);installer.run('install',opts(hard));fs.linkSync(path.join(skill(hard),'SKILL.md'),path.join(hard,'hard.md'));
  assert.throws(()=>installer.run('install',opts(hard)),/unsafe/);
  const linked=sandbox(t),outside=sandbox(t);fs.symlinkSync(outside,path.join(linked,'.agents'),os.platform()==='win32'?'junction':'dir');
  assert.throws(()=>installer.run('install',opts(linked)),/real directory/);assert.deepEqual(fs.readdirSync(outside),[]);
});
test('oversized extra file is refused and stale locks prevent mutation',t=>{
  const root=sandbox(t);installer.run('install',opts(root));fs.writeFileSync(path.join(skill(root),'huge'),Buffer.alloc(1024*1024+1));assert.throws(()=>installer.inspect(skill(root)),/oversized/);
  const locked=sandbox(t);const parent=path.dirname(skill(locked));fs.mkdirSync(parent,{recursive:true});const lock=path.join(parent,'.woobe-cli.install.lock');fs.writeFileSync(lock,'in progress');
  assert.throws(()=>installer.run('install',opts(locked)),/EEXIST/);assert.equal(fs.existsSync(skill(locked)),false);assert.equal(fs.readFileSync(lock,'utf8'),'in progress');
});
test('failed second destination rolls back first and restores original installation',t=>{
  const root=sandbox(t);installer.run('install',opts(root));const before=fs.readFileSync(path.join(skill(root),'SKILL.md'));
  const rename=fs.renameSync;fs.renameSync=(source,target)=>{if(target===skill(root,'claude'))throw new Error('simulated disk error');return rename(source,target);};
  try{assert.throws(()=>installer.run('install',opts(root,['codex','claude'])),/simulated disk error/);}finally{fs.renameSync=rename;}
  assert.deepEqual(fs.readFileSync(path.join(skill(root),'SKILL.md')),before);assert.equal(installer.inspect(skill(root)).status,'managed');assert.equal(fs.existsSync(skill(root,'claude')),false);
  assert.equal(fs.existsSync(path.join(path.dirname(skill(root)),'.woobe-cli.install.lock')),false);
});
test('rollback never deletes a concurrently edited installed copy',t=>{
  const root=sandbox(t);installer.run('install',opts(root));const rename=fs.renameSync;
  fs.renameSync=(source,target)=>{if(target===skill(root,'claude')){fs.appendFileSync(path.join(skill(root),'SKILL.md'),'concurrent edit');throw new Error('simulated error');}return rename(source,target);};
  try{assert.throws(()=>installer.run('install',opts(root,['codex','claude'])),/rollback preserved/);}finally{fs.renameSync=rename;}
  assert.match(fs.readFileSync(path.join(skill(root),'SKILL.md'),'utf8'),/concurrent edit/);
  assert.ok(fs.readdirSync(path.dirname(skill(root))).some(x=>x.endsWith('-previous')));
});
test('CLI help, JSON status, invalid flags and option conflicts preserve exit codes',t=>{
  const root=sandbox(t);const invoke=args=>cp.spawnSync(process.execPath,[launcher,...args],{cwd:root,encoding:'utf8'});
  assert.match(invoke(['--help']).stdout,/Installation is explicit/);assert.equal(invoke(['--version']).stdout.trim(),require('../../packages/woobe-cli-skill/package.json').version);
  assert.match(invoke(['agents']).stdout,/AGENT/);assert.ok(JSON.parse(invoke(['agents','--json']).stdout).agents.claude);
  const status=invoke(['status','--json']);assert.equal(status.status,0);assert.equal(JSON.parse(status.stdout).installations[0].status,'absent');
  for(const args of [['install','--unknown'],['install','--agent'],['install','--agent','missing'],['install','--scope','all'],['install','--path','here','--agent','codex'],['install','--scope','user','--project',root]]){const result=invoke(args);assert.equal(result.status,2,result.stdout);assert.match(result.stderr,/woobe-skill:/);}
});
