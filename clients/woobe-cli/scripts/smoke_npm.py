#!/usr/bin/env python3
"""Install the actual npm tarball and test the launcher without install scripts."""
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
        raise ValueError('npm artifact source differs from expected checkout')
    artifact = root / manifest['npm']['name']
    npm = shutil.which('npm')
    if not npm:
        raise RuntimeError('npm is required for the npm installation smoke')
    env = {key: value for key, value in os.environ.items() if not key.startswith('WOOBE_')}
    with tempfile.TemporaryDirectory() as directory:
        directory = pathlib.Path(directory)
        prefix = directory / 'prefix'
        env['npm_config_cache'] = str(directory / 'cache')
        env['npm_config_update_notifier'] = 'false'
        # No dependencies and no lifecycle scripts: the tarball is sufficient.
        install = subprocess.run([npm, 'install', '--global', '--prefix', str(prefix),
                                  '--offline', '--ignore-scripts', '--no-audit', '--no-fund', str(artifact)],
                                 env=env, capture_output=True, text=True, timeout=90,
                                 shell=os.name == 'nt')
        if install.returncode:
            raise ValueError(f'npm installation failed: {install.stderr}')
        launcher = prefix / 'woobe.cmd' if os.name == 'nt' else prefix / 'bin/woobe'

        def invoke(arguments, body=None, expected=0):
            result = subprocess.run([str(launcher), *arguments, '--config', str(directory / 'config.json')],
                                    input=body, env=env, capture_output=True, text=True,
                                    timeout=30, shell=os.name == 'nt', cwd=directory)
            if result.returncode != expected:
                raise ValueError(f'npm launcher exit {result.returncode}, expected {expected}: {result.stderr}')
            envelope = json.loads(result.stdout)
            if envelope['success'] != (expected == 0):
                raise ValueError('npm launcher lost the native output envelope')
            return envelope

        version = invoke(['version'])['data']
        if version['version'] != manifest['version'] or version['commit'] != commit:
            raise ValueError('installed npm binary version/commit differs from artifact identity')
        commands = {item['command'] for item in invoke(['help'])['data']}
        if not {'version', 'manifest validate', 'project agent list', 'skills install'} <= commands:
            raise ValueError('installed package is missing CLI commands')
        for agent, folder in [('codex', '.agents'), ('codex-legacy', '.codex')]:
            invoke(['skill', 'install', '--agent', agent])
            target = directory / folder / 'skills' / 'woobe-cli'
            expected = pathlib.Path('packages/woobe-cli-skill/skills/woobe-cli/SKILL.md').read_bytes()
            if (target / 'SKILL.md').read_bytes() != expected:
                raise ValueError(f'npm launcher did not install the embedded {agent} skill')
            invoke(['skill', 'uninstall', '--agent', agent])
            if target.exists():
                raise ValueError(f'npm launcher did not remove the embedded {agent} skill')
        invoke(['init', '--agents', 'codex,claude'])
        original = (directory / '.woobe-config').read_bytes()
        invoke(['init', '--agents', 'codex-legacy'])
        if (directory / '.woobe-config').read_bytes() != original:
            raise ValueError('npm init changed registry identity')
        for relative in ['AGENTS.md', 'CLAUDE.md', '.agents/skills/woobe-cli/SKILL.md',
                         '.codex/skills/woobe-cli/SKILL.md', '.claude/skills/woobe-cli/SKILL.md']:
            if not (directory / relative).is_file():
                raise ValueError('npm init missing assistant file: ' + relative)
        document = json.dumps({'schema_version': '2', 'workspace_id': 'w', 'resources': [
            {'key': 'reader', 'kind': 'AuthorityCategory', 'action': 'create',
             'spec': {'name': 'reader', 'permissions': ['agent:read']}}]})
        validation = invoke(['manifest', 'validate', '--file', '-'], document)['data']
        if validation['valid'] is not True:
            raise ValueError('npm launcher did not forward stdin to manifest validation')
        failure = invoke(['manifest', 'validate', '--file', '-'], '{', expected=2)
        if failure['error']['exit_code'] != 2:
            raise ValueError('npm launcher did not preserve the structured native error')
        npx = subprocess.run([npm, 'exec', '--offline', '--yes', f'--package={artifact}', '--', 'woobe', 'version'],
                             env=env, capture_output=True, text=True, timeout=90, shell=os.name == 'nt')
        if npx.returncode or json.loads(npx.stdout)['data']['version'] != manifest['version']:
            raise ValueError(f'npm exec did not run the packaged version: {npx.stderr}')
    return {'success': True, 'commit': commit, 'version': manifest['version'],
            'os': version['os'], 'arch': version['arch'], 'package': artifact.name,
            'checks': ['offline-install', 'ignore-scripts', 'version-commit', 'discovery',
                       'codex-preset-install', 'codex-legacy-preset-install', 'integrated-init',
                       'stdin', 'native-error-exit-code', 'npm-exec']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--report', required=True)
    options = parser.parse_args()
    report = smoke(options.commit)
    pathlib.Path(options.report).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
