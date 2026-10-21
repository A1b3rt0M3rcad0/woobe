#!/usr/bin/env python3
"""Exercise the exact skill tarball through npm installation and npm exec offline."""
import argparse
import json
import os
import pathlib
import shutil
import subprocess
import tempfile


def smoke(commit):
    root = pathlib.Path('dist').resolve()
    manifest = json.loads((root / 'artifacts.json').read_text())
    if manifest['commit'] != commit:
        raise ValueError('skill artifact source differs from checkout')
    artifact = root / manifest['skill_npm']['name']
    npm = shutil.which('npm')
    if not npm:
        raise RuntimeError('npm is required')
    with tempfile.TemporaryDirectory(prefix='woobe-skill-smoke-') as temporary:
        directory = pathlib.Path(temporary)
        project = directory / 'project'
        project.mkdir()
        prefix = directory / 'prefix'
        env = dict(os.environ, npm_config_cache=str(directory / 'cache'), npm_config_update_notifier='false')
        result = subprocess.run([npm, 'install', '--global', '--prefix', str(prefix), '--offline',
                                 '--ignore-scripts', '--no-audit', '--no-fund', str(artifact)],
                                env=env, capture_output=True, text=True, timeout=90, shell=os.name == 'nt')
        if result.returncode:
            raise ValueError(f'skill npm install failed: {result.stderr}')
        launcher = prefix / 'woobe-skill.cmd' if os.name == 'nt' else prefix / 'bin/woobe-skill'

        def invoke(args, expected=0):
            result = subprocess.run([str(launcher), *args], cwd=project, env=env, capture_output=True,
                                    text=True, timeout=30, shell=os.name == 'nt')
            if result.returncode != expected:
                raise ValueError(f'skill launcher exit {result.returncode}, expected {expected}: {result.stderr}')
            return result.stdout

        assert invoke(['--version']).strip() == manifest['version']
        agents = 'codex,claude,copilot,cursor,codex-legacy'
        invoke(['install', '--agent', agents, '--dry-run'])
        assert not list(project.iterdir()), 'dry-run wrote files'
        installed = json.loads(invoke(['install', '--agent', agents, '--json']))
        assert len(installed['installations']) == 5
        for row in installed['installations']:
            target = pathlib.Path(row['target'])
            receipt = json.loads((target / '.woobe-skill-install.json').read_text())
            assert receipt['source_commit'] == commit and receipt['version'] == manifest['version']
            assert (target / 'references/development.md').is_file()
        invoke(['install', '--agent', agents])
        edited = project / '.agents/skills/woobe-cli/SKILL.md'
        original = edited.read_bytes()
        edited.write_bytes(original + b'\nlocal edit\n')
        status = json.loads(invoke(['status', '--agent', 'codex', '--json']))
        assert status['installations'][0]['status'] == 'modified'
        invoke(['install', '--agent', agents], expected=2)
        invoke(['uninstall', '--agent', agents], expected=2)
        assert edited.read_bytes().endswith(b'local edit\n')
        edited.write_bytes(original)
        invoke(['uninstall', '--agent', agents])
        assert not edited.exists()
        npx = subprocess.run([npm, 'exec', '--offline', '--yes', f'--package={artifact}', '--',
                              'woobe-skill', 'install', '--agent', 'codex', '--json'],
                             cwd=project, env=env, capture_output=True, text=True, timeout=90, shell=os.name == 'nt')
        if npx.returncode:
            raise ValueError(f'skill npm exec failed: {npx.stderr}')
        assert json.loads(npx.stdout)['version'] == manifest['version']
        assert edited.is_file()
    return dict(success=True, commit=commit, version=manifest['version'], package=artifact.name,
                checks=['offline-install', 'ignore-scripts', 'version-source-receipt', 'five-host-layouts',
                        'read-only-dry-run', 'idempotent-update', 'modified-refusal', 'uninstall', 'npm-exec'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--report', required=True)
    args = parser.parse_args()
    report = smoke(args.commit)
    pathlib.Path(args.report).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
