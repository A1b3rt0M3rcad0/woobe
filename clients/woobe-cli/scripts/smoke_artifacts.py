#!/usr/bin/env python3
"""Exercise the downloaded executable for this host, without a backend or secrets."""
import argparse
import hashlib
import json
import os
import pathlib
import platform
import http.server
import threading
import subprocess
import tarfile
import tempfile
import zipfile
import uuid


def smoke(root, commit):
    manifest = json.loads((root / 'artifacts.json').read_text())
    if manifest['commit'] != commit:
        raise ValueError('artifact source commit differs from expected checkout')
    system = {'Linux': 'linux', 'Darwin': 'darwin', 'Windows': 'windows'}[platform.system()]
    arch = {'x86_64': 'amd64', 'AMD64': 'amd64', 'arm64': 'arm64', 'ARM64': 'arm64', 'aarch64': 'arm64'}[platform.machine()]
    matches = [a for a in manifest['artifacts'] if a['os'] == system and a['arch'] == arch]
    if len(matches) != 1:
        raise ValueError('exactly one archive must match the native host')
    artifact = matches[0]
    executable = 'woobe.exe' if system == 'windows' else 'woobe'
    archive_path = root / artifact['name']
    if system == 'windows':
        with zipfile.ZipFile(archive_path) as archive:
            binary = archive.read(executable)
    else:
        with tarfile.open(archive_path) as archive:
            binary = archive.extractfile(executable).read()
    # Extract only the known executable; never trust archive paths for extraction.
    with tempfile.TemporaryDirectory() as directory:
        directory = str(pathlib.Path(directory).resolve())
        path = pathlib.Path(directory) / executable
        path.write_bytes(binary)
        path.chmod(0o700)
        from validate_skill_commands import validate
        validate(path.resolve())
        env = {k: v for k, v in os.environ.items() if not k.startswith('WOOBE_')}

        def invoke(args, body=None, code=0, cwd=None):
            command = [str(path), *args, '--output', 'json', '--config', str(pathlib.Path(directory) / 'config.json')]
            result = subprocess.run(command, input=body, capture_output=True, text=True, env=env, cwd=cwd or directory, timeout=30)
            if result.returncode != code:
                raise ValueError(f'{args}: exit {result.returncode}, expected {code}: {result.stderr}')
            envelope = json.loads(result.stdout)
            if envelope['success'] != (code == 0):
                raise ValueError(f'{args}: envelope success differs from exit code')
            if code and envelope['error']['exit_code'] != code:
                raise ValueError(f'{args}: structured error code differs from exit code')
            return envelope

        # Exact project-local commands reported by Windows users. Run the real
        # packaged executable, without --project-dir or a saved connection.
        for agent, folder in [('codex', '.agents'), ('codex-legacy', '.codex')]:
            target = pathlib.Path(directory) / folder / 'skills' / 'woobe-cli'
            invoke(['skill', 'install', '--agent', agent, '--dry-run'])
            if target.exists():
                raise ValueError(f'{agent}: dry-run wrote the project skill')
            invoke(['skill', 'install', '--agent', agent])
            source = pathlib.Path('packages/woobe-cli-skill/skills/woobe-cli')
            for file in source.rglob('*'):
                if file.is_file() and (target / file.relative_to(source)).read_bytes() != file.read_bytes():
                    raise ValueError(f'{agent}: project skill differs from embedded source: {file}')
            invoke(['skill', 'install', '--agent', agent])
            state = invoke(['skill', 'status', '--agent', agent])['data']
            if state['installations'][0]['status'] != 'managed':
                raise ValueError(f'{agent}: project skill not recognized')
            invoke(['skill', 'uninstall', '--agent', agent])
            if target.exists():
                raise ValueError(f'{agent}: project skill retained after removal')

        skill_root = pathlib.Path(directory) / 'assistant-skills'
        installed_skill = invoke(['skill', 'install', '--path', str(skill_root)])['data']
        skill_target = skill_root / 'woobe-cli'
        if not installed_skill['executed'] or not (skill_target / 'SKILL.md').is_file():
            raise ValueError('packaged binary did not install its embedded skill offline')
        if (skill_target / 'SKILL.md').read_bytes() != pathlib.Path('packages/woobe-cli-skill/skills/woobe-cli/SKILL.md').read_bytes():
            raise ValueError('embedded skill differs from canonical npm source')
        invoke(['skills', 'status', '--path', str(skill_root)])
        # Native and standalone installers share one ownership/integrity receipt.
        launcher = pathlib.Path('packages/woobe-cli-skill/bin/woobe-skill.cjs').resolve()
        subprocess.run(['node', str(launcher), 'install', '--path', str(skill_root)], check=True, capture_output=True)
        native_status = invoke(['skills', 'status', '--path', str(skill_root)])['data']
        if native_status['installations'][0]['status'] != 'managed':
            raise ValueError('native installer did not recognize the npm receipt')
        invoke(['skill', 'install', '--path', str(skill_root)])
        invoke(['skill', 'uninstall', '--path', str(skill_root)])
        outside = pathlib.Path(directory) / 'outside-skills'
        outside.mkdir()
        linked = pathlib.Path(directory) / 'linked-skills'
        subprocess.run(['node', '-e', "require('fs').symlinkSync(process.argv[1], process.argv[2], process.platform === 'win32' ? 'junction' : 'dir')", str(outside), str(linked)], check=True, capture_output=True)
        invoke(['skill', 'install', '--path', str(linked)], code=2)
        if list(outside.iterdir()):
            raise ValueError('embedded installer followed linked destination')
        if skill_target.exists():
            raise ValueError('native installer did not remove its managed skill')
        version = invoke(['version'])['data']
        if any(version[k] != v for k, v in {'commit': commit, 'version': manifest['version'], 'os': system, 'arch': arch}.items()):
            raise ValueError('packaged binary identity differs from archive metadata')
        project = pathlib.Path(directory) / 'assistant-project'
        project.mkdir()
        invoke(['init', '--agents', 'codex,codex-legacy,claude', '--dry-run'], cwd=project)
        if list(project.iterdir()):
            raise ValueError('integrated setup dry-run wrote files')
        (project / 'AGENTS.md').write_bytes(b'# Project rules\r\nPreserve user instructions.\r\n')
        invoke(['init', '--agents', 'codex,codex-legacy,claude'], cwd=project)
        config_before = (project / '.woobe-config').read_bytes()
        instructions_before = (project / 'AGENTS.md').read_bytes()
        invoke(['init', '--agents', 'claude'], cwd=project)
        if (project / '.woobe-config').read_bytes() != config_before or (project / 'AGENTS.md').read_bytes() != instructions_before:
            raise ValueError('integrated setup changed registry or duplicated instructions')
        if not instructions_before.startswith(b'# Project rules\r\nPreserve user instructions.\r\n'):
            raise ValueError('integrated setup lost project instructions')
        for folder in ['.agents', '.codex', '.claude']:
            installed = project / folder / 'skills/woobe-cli'
            for file in source.rglob('*'):
                if file.is_file() and (installed / file.relative_to(source)).read_bytes() != file.read_bytes():
                    raise ValueError('integrated setup skill differs from canonical payload')
        if not (project / 'CLAUDE.md').is_file() or not (project / '.woobe-lab').is_dir():
            raise ValueError('integrated setup missing host instructions/lab')
        edited = project / '.agents/skills/woobe-cli/SKILL.md'
        edited.write_bytes(edited.read_bytes() + b'\nLocal edit\n')
        invoke(['init', '--agents', 'copilot'], code=2, cwd=project)
        if (project / '.github').exists() or (project / 'AGENTS.md').read_bytes() != instructions_before:
            raise ValueError('conflicting skill caused partial assistant installation')
        invoke(['init'])
        author = pathlib.Path(directory) / 'author.json'
        author.write_text(json.dumps({'kind': 'Agent', 'metadata': {'name': 'Support'}, 'spec': {'instructions': 'First line\nSecond line\n', 'limit': 9007199254740993}}), encoding='utf-8')
        invoke(['resources', 'create', 'agent', 'support', '--file', str(author)])
        rendered = (pathlib.Path(directory) / '.woobe/agents/support/agent.yaml').read_text(encoding='utf-8')
        if not rendered.startswith('kind: Agent\nmetadata:\n  key: support\n') or '  instructions: |\n    First line\n    Second line\n' not in rendered or '  limit: 9007199254740993\n' not in rendered:
            raise ValueError('packaged CLI did not write readable, lossless block YAML')
        invoke(['resources', 'move', 'agent', '@support', '--path', 'agents/support.json'])
        moved = json.loads((pathlib.Path(directory) / '.woobe/agents/support.json').read_text(encoding='utf-8'))
        if moved['spec'] != json.loads(author.read_text(encoding='utf-8'))['spec']:
            raise ValueError('packaged CLI changed author values when moving YAML to JSON')
        invoke(['resources', 'clone', 'agent', '@support', '--alias', 'copy', '--path', 'agents/copy.json'])
        invoke(['resources', 'used-by', 'agent', '@copy'])
        (pathlib.Path(directory) / '.woobe/agents/copy.json').unlink()
        invoke(['config', 'check'], code=2)
        invoke(['resources', 'prune'], code=2)
        preview = invoke(['resources', 'prune', '--dry-run'])['data']
        if preview['executed'] is not False or len(preview['resources']) != 1 or preview['resources'][0]['alias'] != 'copy':
            raise ValueError('packaged stale registry preview has incorrect scope')
        invoke(['config', 'check'], code=2)
        applied = invoke(['resources', 'prune', '--yes'])['data']
        if applied['remote_deleted'] is not False or applied['bindings_retained'] is not True:
            raise ValueError('packaged stale registry cleanup has incorrect safety semantics')
        invoke(['config', 'check'])
        discovery = invoke(['help'])['data']
        commands = {row['command'] for row in discovery}
        if not {'manifest validate', 'manifest apply', 'manifest reconcile', 'runtime target run', 'version', 'workspace authority category diff', 'develop agent deploy', 'develop network deploy'} <= commands:
            raise ValueError('discovery is missing essential executable commands')
        for kind in ('agent', 'network'):
            rejected = invoke([kind, '12345678-1234-4321-8321-123456789012', 'deploy',
                               '--from', 'release', '--release', 'invalid', '--notes', 'Smoke preflight',
                               '--plan-only'], code=2)
            if '--release UUID' not in rejected['error']['message']:
                raise ValueError('packaged unified deploy did not reject invalid identity before authentication')
        for revision, identity in [('1', 'urn:woobe:manifest:steps:1'), ('2', 'urn:woobe:manifest:resources:2')]:
            schema = invoke(['schema', '--command', 'manifest validate', '--kind', 'document', '--manifest-version', revision])['data']
            if schema['$id'] != identity:
                raise ValueError('packaged manifest schema has incorrect identity')
        fixture = json.loads((pathlib.Path(__file__).resolve().parent.parent / 'testdata/package/shared/complete.json').read_text())['files']
        bundle = pathlib.Path(directory) / 'complete-package'
        bundle.mkdir()
        for relative, content in fixture.items():
            destination = bundle / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content.encode('utf-8'))
        # Execute ASaC author history on every real packaged native binary,
        # including Windows DACL initialization and scratch compilation.
        author_project = pathlib.Path(directory) / 'asac-project'
        author_project.mkdir()
        (author_project / ".git").mkdir()  # Independent project boundary.
        invoke(['init'], cwd=author_project)
        author_root = author_project / '.woobe'
        resources = []
        for relative, content in fixture.items():
            destination = author_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content.encode('utf-8'))
            if relative.endswith('.yaml') and relative != 'woobe.yaml':
                document = json.loads(content)
                resources.append({'uid': str(uuid.uuid4()), 'kind': document['kind'], 'key': document['metadata']['key'], 'alias': document['metadata']['key'], 'path': relative})
        public_config = {'schema_version': 1, 'registry_id': str(uuid.uuid4()), 'context': '', 'root': '.woobe', 'defaults': {'pull_environment': 'draft'}, 'resources': resources}
        (author_project / '.woobe-config').write_text(json.dumps(public_config), encoding='utf-8')
        requirements = json.loads(fixture['woobe.yaml'])['spec']['requires']
        for kind, key, filename in [('Agent', 'support', 'agent.yaml'), ('Network', 'support-network', 'network.yaml')]:
            resource = next(item for item in resources if item['key'] == key)
            tracking = {'format': 'woobe-tracking', 'schema_version': '1.0', 'resource_uid': resource['uid'], 'origin': {'target': '', 'workspace_id': '', 'project_id': '', 'resource_id': '', 'environment': 'unknown', 'origin_status': 'unknown_origin'}, 'tracking_environment': 'unknown', 'write_environment': 'draft', 'requires': requirements}
            lock = author_root / (pathlib.Path(filename).stem + '.asac') / (kind.lower() + '.lock.yaml')
            lock.parent.mkdir(parents=True, exist_ok=True)
            lock.write_text(json.dumps(tracking), encoding='utf-8')
            prefix = [kind.lower(), '@' + key]
            first = invoke([*prefix, 'revision', 'create', '--message', 'Native source baseline'], cwd=author_project)['data']
            descriptor = author_root / filename
            original = descriptor.read_bytes()
            descriptor.write_bytes(b'# native source comment\n' + original)
            second = invoke([*prefix, 'revision', 'create', '--message', 'Native source comment'], cwd=author_project)['data']
            if first['definition_digest'] != second['definition_digest'] or first['author_artifact_digest'] == second['author_artifact_digest']:
                raise ValueError('native checkpoint conflated author comments with executable identity')
            invoke([*prefix, 'checkout', '--revision', first['revision_id']], cwd=author_project)
            if descriptor.read_bytes() != original:
                raise ValueError('native checkout did not preserve exact source bytes')
            rebased = invoke([*prefix, 'rebase', '--onto', second['revision_id']], cwd=author_project)['data']
            if descriptor.read_bytes() != b'# native source comment\n' + original:
                raise ValueError('native rebase lost a comment-only remote author edit')
            if rebased['remote_changed'] or rebased['rebased_from'] != first['revision_id']:
                raise ValueError('native rebase changed remote scope or original identity')
            invoke([*prefix, 'revision', 'merge', first['revision_id'], rebased['revision']['revision_id'], '--message', 'Resolved native content'], cwd=author_project)
            invoke([*prefix, 'history', 'verify'], cwd=author_project)
        validated = invoke(['package', 'validate', str(bundle)])['data']
        if not validated['valid'] or validated['entrypoint']['kind'] != 'Network':
            raise ValueError('complete Package fixture was not validated offline')
        inventory = [{'path': relative, 'size_bytes': len(content.encode('utf-8')), 'sha256': hashlib.sha256(content.encode('utf-8')).hexdigest()} for relative, content in sorted(fixture.items())]
        tuples = [[item['path'], item['size_bytes'], item['sha256']] for item in inventory]
        digest = hashlib.sha256(b'woobe-package@1.0\n' + json.dumps(tuples, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).hexdigest()
        if validated['artifact_digest'] != digest or validated['inventory'] != inventory:
            raise ValueError('native Package inventory differs from Python canonical digest')
        lock = {'format': 'woobe-package', 'schema_version': '1.0', 'kind': 'PackageLock', 'algorithm': 'sha256', 'inventory': inventory, 'artifact_digest': digest}
        lock_bytes = json.dumps(lock).encode()
        (bundle / 'woobe.lock.json').write_bytes(lock_bytes)
        invoke(['package', 'validate', str(bundle), '--locked'])
        (bundle / 'agent.yaml').write_bytes(fixture['agent.yaml'].encode() + b'\n')
        invoke(['package', 'validate', str(bundle), '--locked'], code=2)
        if (bundle / 'woobe.lock.json').read_bytes() != lock_bytes:
            raise ValueError('Package validation rewrote an inventory lock')
        body = json.dumps({'schema_version': '2', 'project_id': 'p', 'resources': [{'key': 'a', 'kind': 'Agent', 'action': 'update', 'resource_id': 'a', 'spec': {'name': 'Smoke'}}]})
        validation = invoke(['manifest', 'validate', '--file', '-', '--project', 'p'], body)['data']
        if validation['valid'] is not True or validation['source_schema_version'] != '2' or len(validation['manifest_hash']) != 64:
            raise ValueError('local manifest validation has incorrect semantics')
        category_body = json.dumps({'schema_version': '2', 'workspace_id': 'w', 'resources': [{'key': 'reader', 'kind': 'AuthorityCategory', 'action': 'create', 'spec': {'name': 'reader', 'permissions': ['agent:read']}}]})
        category = invoke(['manifest', 'compile', '--file', '-'], category_body)['data']
        if category['document']['workspace_id'] != 'w' or category['executed'] is not False:
            raise ValueError('packaged category compilation lost its Workspace')
        invoke(['manifest', 'validate', '--file', '-'], '{', code=2)
        protected_plan = json.dumps({'schema_version': '2', 'project_id': 'p', 'resources': [{'key': 'tool', 'kind': 'Tool', 'action': 'create', 'spec': {'config': {'headers': [{'name': 'Authorization', 'value': {'$secret_ref': 'tool-auth'}}]}}}]})
        protected = invoke(['manifest', 'compile', '--file', '-'], protected_plan)['data']['document']
        if protected['steps'][0]['body']['config']['headers'][0]['value'] != {'$secret_ref': 'tool-auth'}:
            raise ValueError('packaged compilation lost protected credential reference')
        invoke(['project', 'tool', 'mcp', 'bulk', '--project', 'p', '--file', '-', '--dry-run'], json.dumps({'tool_id': '11111111-1111-4111-8111-111111111111', 'mode': 'invalid'}), code=2)
        for permission_mode in ['allow', 'deny', 'review']:
            invoke(['project', 'tool', 'mcp', 'bulk', '--project', 'p', '--file', '-', '--dry-run'], json.dumps({'tool_id': '11111111-1111-4111-8111-111111111111', 'mode': permission_mode}))

        # A loopback fixture verifies the packaged client's body pagination on
        # each native OS; real Woobe policy remains the separate backend gate.
        class Pages(http.server.BaseHTTPRequestHandler):
            requests = []
            validation_reads = 0
            writes = 0

            def do_GET(self):
                from urllib.parse import urlparse, parse_qs
                route = urlparse(self.path)
                query = parse_qs(route.query)
                if route.path == '/openapi.json':
                    type(self).validation_reads += 1
                    schema = {'openapi': '3.1.0', 'paths': {'/ai/agents': {'post': {'requestBody': {'content': {'application/json': {'schema': {
                        'type': 'object', 'required': ['id', 'model_id', 'created_at'], 'properties': {
                            'id': {'type': 'string', 'readOnly': True},
                            'model_id': {'type': 'string', 'format': 'uuid'},
                            'created_at': {'type': 'string', 'format': 'date-time'}}}}}}}}}}
                    schema['paths']['/runtime/agents/{agent_id}/sessions'] = {'get': {'parameters': [
                        {'name': 'agent_id', 'in': 'path', 'required': True, 'schema': {'type': 'string'}},
                        {'name': 'project_id', 'in': 'query', 'required': True, 'schema': {'type': 'string'}},
                        {'name': 'limit', 'in': 'query', 'schema': {'type': 'integer', 'minimum': 1, 'maximum': 100}},
                        {'name': 'cursor', 'in': 'query', 'schema': {'type': 'string'}}]}}
                    schema['paths']['/identity/workspaces/{workspace_id}/authority-categories/{category_id}'] = {'get': {'operationId': 'get_category'}}
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(schema).encode())
                    return
                if route.path == '/identity/workspaces/w/authority-categories/c':
                    revision = int(query['revision'][0])
                    payload = {'data': {'id': 'c', 'workspace_id': 'w', 'revision': revision, 'name': 'reader', 'description': None, 'scope': 'project', 'permissions': ['agent:read'] if revision == 1 else ['agent:write', 'agent:read'], 'conditions': {}, 'catalog_revision': 'fixture'}}
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(payload).encode())
                    return
                self.requests.append(query)
                if route.path != '/runtime/agents/a/sessions' or query.get('project_id') != ['p'] or query.get('limit') != ['1']:
                    self.send_error(400)
                    return
                terminal = query.get('cursor') == ['first']
                payload = {'success': True, 'data': {'items': [{'id': 'second' if terminal else 'first'}], 'has_next': not terminal, 'next_cursor': None if terminal else 'first'}}
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(payload).encode())

            def do_POST(self):
                type(self).writes += 1
                if self.path != '/ai/agents':
                    self.send_error(400)
                    return
                self.rfile.read(int(self.headers.get('Content-Length', '0')))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"id":"a"}')

            def log_message(self, *_):
                pass

        server = http.server.HTTPServer(('127.0.0.1', 0), Pages)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            origin = f'http://127.0.0.1:{server.server_port}'
            pages = invoke(['runtime', 'agent', 'sessions', 'a', '--project', 'p', '--api-url', origin, '--limit', '1', '--all'])
            if pages['data']['page_count'] != 2 or pages['meta']['collection_complete'] != 'verified' or pages['meta']['complete'] is not True or len(Pages.requests) != 2:
                raise ValueError('packaged pagination failed to consume both pages')
            partial = invoke(['runtime', 'agent', 'sessions', 'a', '--project', 'p', '--api-url', origin, '--limit', '1'])
            if partial['meta']['complete'] is not False or partial['meta']['collection_complete'] != 'partial':
                raise ValueError('single page incorrectly claims collection completeness')
            valid_body = {'model_id': '6ba7b810-9dad-11d1-80b4-00c04fd430c8', 'created_at': '2026-10-05T20:40:46-03:00'}
            valid = invoke(['validate-input', '--command', 'project agent create', '--api-url', origin, '--file', '-'], json.dumps(valid_body))
            if valid['data']['validation_direction'] != 'request' or valid['data']['executed'] is not False:
                raise ValueError('packaged input validation did not report request direction')
            for invalid in [dict(valid_body, model_id='invalid'), dict(valid_body, id='server'), dict(valid_body, created_at='2026-02-29T00:00:00Z')]:
                denied = invoke(['project', 'agent', 'create', '--validate-body', '--api-url', origin, '--file', '-'], json.dumps(invalid), code=2)
                if denied['error']['write_outcome'] != 'not_attempted':
                    raise ValueError('invalid body was not refused before mutation')
            if Pages.writes != 0:
                raise ValueError('invalid request body caused a mutation')
            invoke(['project', 'agent', 'create', '--validate-body', '--api-url', origin, '--file', '-'], json.dumps(valid_body))
            if Pages.writes != 1 or Pages.validation_reads != 5:
                raise ValueError('packaged request validation/write counts differ')
            parameter_preflight = invoke(['validate-input', '--command', 'runtime agent sessions', '--validate-parameters', '--path-param', 'agent_id=a', '--query', 'project_id=p', '--query', 'limit=1', '--api-url', origin])
            if parameter_preflight['data']['path_query_validation'] != 'supported_schema_subset' or parameter_preflight['data']['body_validation'] != 'not_evaluated':
                raise ValueError('parameter-only preflight incorrectly reports its scope')
            pages_before = len(Pages.requests)
            invoke(['runtime', 'agent', 'sessions', 'a', '--project', 'p', '--api-url', origin, '--query', 'limit=101', '--validate-parameters'], code=2)
            if len(Pages.requests) != pages_before:
                raise ValueError('invalid query caused a resource read')
            invoke(['runtime', 'agent', 'sessions', 'a', '--project', 'p', '--api-url', origin, '--limit', '1', '--all', '--validate-parameters'])
            if len(Pages.requests) != pages_before + 2:
                raise ValueError('validated packaged pagination did not consume both pages')
            category_diff = invoke(['workspace', 'authority', 'category', 'diff', 'c', '--workspace', 'w', '--from-revision', '1', '--to-revision', '2', '--api-url', origin])['data']
            if category_diff['grants_changed'] is not False or category_diff['executed'] is not False or [row['field'] for row in category_diff['changes']] != ['permissions']:
                raise ValueError('packaged category diff has incorrect authority semantics')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
    return {'commit': commit, 'version': manifest['version'], 'os': system, 'arch': arch,
            'archive': artifact['name'], 'success': True, 'checks': ['integrated-project-init', 'init-preserves-edits-and-identity', 'project-codex-preset-lifecycle', 'project-codex-legacy-preset-lifecycle', 'embedded-assistant-skill', 'native-npm-receipt-compatibility', 'linked-skill-destination-refusal', 'identity', 'discovery', 'schemas', 'complete-package-offline', 'package-python-inventory-parity', 'package-lock-tamper', 'manifest', 'invalid-input', 'body-pagination', 'partial-collection', 'request-direction', 'uuid-date-time', 'validation-before-write', 'path-query-validation', 'validated-pagination', 'workspace-category-manifest', 'category-revision-diff', 'protected-reference-compile', 'canonical-mcp-permissions'],
            'local_registry_checks': ['readable-yaml', 'yaml-json-move', 'json-clone', 'stale-registry-preview', 'explicit-stale-registry-prune', 'agent-network-source-checkout-rebase-merge'],
            'backend_acceptance': 'not_evaluated', 'credential_provider_acceptance': 'not_evaluated'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--report', required=True)
    options = parser.parse_args()
    report = smoke(pathlib.Path('dist'), options.commit)
    pathlib.Path(options.report).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
