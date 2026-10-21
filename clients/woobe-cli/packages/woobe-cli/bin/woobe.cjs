#!/usr/bin/env node
'use strict';

const { existsSync } = require('node:fs');
const { join } = require('node:path');
const { spawn } = require('node:child_process');
const { constants } = require('node:os');

const platform = { linux: 'linux', darwin: 'darwin', win32: 'windows' }[process.platform];
const arch = { x64: 'amd64', arm64: 'arm64' }[process.arch];
if (!platform || !arch) {
  console.error(`woobe-cli: unsupported platform ${process.platform}/${process.arch}; use Linux, macOS or Windows on x64 or arm64.`);
  process.exit(1);
}
const binary = join(__dirname, '..', 'vendor', `${platform}-${arch}`, platform === 'windows' ? 'woobe.exe' : 'woobe');
if (!existsSync(binary)) {
  console.error('woobe-cli: packaged executable is missing. Reinstall the published package or download a binary from https://github.com/A1b3rt0M3rcad0/woobe-cli/releases.');
  process.exit(1);
}

const child = spawn(binary, process.argv.slice(2), { stdio: 'inherit', shell: false });
const handlers = new Map(['SIGINT', 'SIGTERM'].map(signal => {
  const handler = () => child.kill(signal);
  process.on(signal, handler);
  return [signal, handler];
}));
function cleanup() {
  for (const [signal, handler] of handlers) process.removeListener(signal, handler);
}
child.once('error', error => {
  cleanup();
  console.error(`woobe-cli: unable to start the executable: ${error.message}`);
  process.exitCode = 1;
});
child.once('exit', (code, signal) => {
  cleanup();
  process.exitCode = signal ? 128 + (constants.signals[signal] || 1) : (code ?? 1);
});
