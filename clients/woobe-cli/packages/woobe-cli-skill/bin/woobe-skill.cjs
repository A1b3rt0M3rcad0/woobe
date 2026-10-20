#!/usr/bin/env node
'use strict';
const { main } = require('../lib/install.cjs');
try { main(process.argv.slice(2)); }
catch (error) { process.stderr.write(`woobe-skill: ${error.message}\n`); process.exitCode = 2; }
