"""Start/stop a private, pinned real S3-compatible qualification service.

Requires the repository test dependencies. State and generated test credentials
stay outside the checkout. No external AWS credential or account is used.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import tarfile
import time
import urllib.request


VERSION = '4.48'
ARCHIVE_SHA256 = '4a7d108384d044d95212d1342cdda9533fa55842c1c9b41f606ca3c8a9561124'
DOWNLOAD = f'https://github.com/seaweedfs/seaweedfs/releases/download/{VERSION}/linux_amd64.tar.gz'
ROOT = Path(__file__).resolve().parents[2]


def owned_process(pid, binary, state):
    try:
        arguments = Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\x00')
    except FileNotFoundError:
        return False
    return (os.fsencode(binary) in arguments
            and os.fsencode(f'-dir={state / "data"}') in arguments)


def stop(state):
    pid_file = state / 'qualification.pid'
    if not pid_file.exists():
        return
    pid = int(pid_file.read_text())
    if owned_process(pid, state / 'weed', state):
        os.kill(pid, signal.SIGTERM)
        for _ in range(100):
            if not owned_process(pid, state / 'weed', state):
                break
            time.sleep(0.1)
        else:
            # The disposable fixture may stall during embedded Raft shutdown.
            # Recheck ownership immediately before terminating only our process.
            if owned_process(pid, state / 'weed', state):
                os.kill(pid, signal.SIGKILL)
            for _ in range(100):
                if not owned_process(pid, state / 'weed', state):
                    break
                time.sleep(0.05)
            else:
                raise RuntimeError('Owned S3 qualification process did not stop')
    pid_file.unlink(missing_ok=True)


def prepare_binary(state):
    archive = state / 'linux_amd64.tar.gz'
    if not archive.exists():
        temporary = state / 'release.download'
        try:
            urllib.request.urlretrieve(DOWNLOAD, temporary)
            with temporary.open('rb') as source:
                if hashlib.file_digest(source, 'sha256').hexdigest() != ARCHIVE_SHA256:
                    raise RuntimeError('Official S3 qualification release checksum mismatch')
            temporary.rename(archive)
        finally:
            temporary.unlink(missing_ok=True)
    with archive.open('rb') as source:
        if hashlib.file_digest(source, 'sha256').hexdigest() != ARCHIVE_SHA256:
            raise RuntimeError('Cached S3 qualification release checksum mismatch')
    binary = state / 'weed'
    with tarfile.open(archive) as contents:
        member = contents.getmember('weed')
        if not member.isfile():
            raise RuntimeError('Pinned release does not contain the expected regular binary')
        with contents.extractfile(member) as source:
            expected_binary = hashlib.file_digest(source, 'sha256').hexdigest()
        if binary.exists():
            with binary.open('rb') as source:
                if hashlib.file_digest(source, 'sha256').hexdigest() != expected_binary:
                    raise RuntimeError('Existing local qualification binary differs; preserve and inspect it')
        else:
            contents.extract(member, state, filter='data')
    binary.chmod(0o700)
    return binary


def client(configuration):
    import botocore.session
    from botocore.config import Config

    session = botocore.session.Session()
    session.get_component('config_store').set_config_variable('profile', None)
    session.set_credentials(configuration['access_key'], configuration['secret_key'])
    return session.create_client('s3', endpoint_url=configuration['endpoint'],
        region_name='us-east-1', config=Config(signature_version='s3v4',
            s3={'addressing_style': 'path'}, connect_timeout=1, read_timeout=1,
            retries={'max_attempts': 0}))


def start(state):
    binary = prepare_binary(state)
    configuration_file = state / 'test-credentials.json'
    if not configuration_file.exists():
        configuration_file.write_text(json.dumps({
            'access_key': secrets.token_hex(12), 'secret_key': secrets.token_urlsafe(32),
            'endpoint': 'http://127.0.0.1:8333',
        }))
    configuration_file.chmod(0o600)
    configuration = json.loads(configuration_file.read_text())
    if configuration['endpoint'] != 'http://127.0.0.1:8333':
        raise RuntimeError('Qualification credentials must target the local test service')
    server_config = state / 'qualification-config.json'
    expected_config = {'identities': [{'name': 'woobe-artifact-qualification',
        'credentials': [{'accessKey': configuration['access_key'], 'secretKey': configuration['secret_key']}],
        'actions': ['Admin', 'Read', 'Write', 'List', 'Tagging']}]}
    if server_config.exists() and json.loads(server_config.read_text()) != expected_config:
        raise RuntimeError('Existing qualification configuration differs; preserve and inspect it')
    if not server_config.exists():
        server_config.write_text(json.dumps(expected_config))
    server_config.chmod(0o600)
    pid_file = state / 'qualification.pid'
    if not pid_file.exists() or not owned_process(int(pid_file.read_text()), binary, state):
        (state / 'data').mkdir(exist_ok=True)
        arguments = [str(binary), 'server', f'-dir={state / "data"}', '-ip=127.0.0.1',
            '-ip.bind=127.0.0.1', '-master.port=9333', '-master.volumeSizeLimitMB=128',
            '-volume.port=8082', '-volume.max=32', '-volume.preStopSeconds=0', '-filer',
            '-filer.port=8888', '-s3', '-s3.port=8333', '-s3.port.iceberg=0',
            '-s3.port.lance=0', f'-s3.config={server_config}']
        with (state / 'qualification.log').open('ab') as log:
            process = subprocess.Popen(arguments, cwd=state, stdout=log,
                                       stderr=subprocess.STDOUT, start_new_session=True)
        pid_file.write_text(str(process.pid))
    connection = client(configuration)
    try:
        # A restart may wait for the embedded single-node Raft election timeout.
        for _ in range(360):
            if not owned_process(int(pid_file.read_text()), binary, state):
                raise RuntimeError('Local S3 process exited; inspect the private qualification log')
            try:
                connection.list_buckets()
                print(f'SeaweedFS {VERSION}: verified release; authenticated local S3 readiness passed')
                print(f'WOOBE_ARTIFACT_TEST_S3_CONFIG_FILE={configuration_file}')
                return
            except Exception:
                time.sleep(0.25)
        raise RuntimeError('Local authenticated S3 readiness timed out')
    finally:
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state-dir', type=Path, default=Path('/tmp/woobe-artifact-s3'))
    parser.add_argument('--stop', action='store_true')
    args = parser.parse_args()
    state = args.state_dir.resolve()
    if state.is_relative_to(ROOT):
        raise RuntimeError('Private S3 qualification state must stay outside the checkout')
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    previous_umask = os.umask(0o077)
    try:
        stop(state) if args.stop else start(state)
    finally:
        os.umask(previous_umask)


if __name__ == '__main__':
    main()
