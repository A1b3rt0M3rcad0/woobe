#!/usr/bin/env python3
"""Exercise the published container's identity, discovery, stdin and errors."""
import argparse
import json
import subprocess


def smoke(image, version, commit):
    def invoke(args, body=None, code=0):
        result = subprocess.run(['docker', 'run', '--rm', '--interactive', '--read-only',
                                 '--network', 'none', image, *args, '--output', 'json'],
                                input=body, capture_output=True, text=True, timeout=60)
        if result.returncode != code:
            raise ValueError(f'container {args}: expected {code}, got {result.returncode}: {result.stderr}')
        payload = json.loads(result.stdout)
        if payload['success'] != (code == 0):
            raise ValueError('container structured result differs from native exit code')
        return payload
    identity = invoke(['version'])['data']
    if identity['version'] != version or identity['commit'] != commit or identity['os'] != 'linux':
        raise ValueError('container executable differs from validated native source')
    commands = {row['command'] for row in invoke(['help'])['data']}
    if not {'version', 'manifest validate', 'runtime target run'} <= commands:
        raise ValueError('container discovery is incomplete')
    body = json.dumps({'schema_version': '2', 'project_id': 'p', 'resources': [
        {'key': 'a', 'kind': 'Agent', 'action': 'update', 'resource_id': 'a', 'spec': {'name': 'demo'}}]})
    validation = invoke(['manifest', 'validate', '--file', '-', '--project', 'p'], body)['data']
    if validation['valid'] is not True or validation['source_schema_version'] != '2':
        raise ValueError('container manifest validation failed')
    error = invoke(['manifest', 'validate', '--file', '-'], '{', code=2)
    if error['error']['exit_code'] != 2:
        raise ValueError('container lost native error exit code')
    return dict(success=True, image=image, version=version, commit=commit,
                checks=['identity', 'discovery', 'stdin', 'native-error-exit-code', 'nonroot-readonly'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--version', required=True)
    parser.add_argument('--commit', required=True)
    parser.add_argument('--report', default='dist/image-smoke.json')
    args = parser.parse_args()
    result = smoke(args.image, args.version, args.commit)
    with open(args.report, 'w') as output:
        json.dump(result, output, indent=2)
        output.write('\n')
    print(json.dumps(result))
