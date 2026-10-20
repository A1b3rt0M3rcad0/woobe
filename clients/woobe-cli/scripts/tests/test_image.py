import hashlib
import io
import json
import os
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import prepare_image
import registry_image


class ImageContextTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        previous = pathlib.Path.cwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(temporary.name)
        root = pathlib.Path('dist'); root.mkdir()
        self.commit = 'a' * 40
        self.version = '0.1.0'
        artifacts = []
        self.binary = {}
        for system in ['linux', 'darwin', 'windows']:
            for arch in ['amd64', 'arm64']:
                executable = 'woobe.exe' if system == 'windows' else 'woobe'
                binary = (system + '-' + arch).encode()
                self.binary[system, arch] = binary
                files = {executable: binary, 'README.md': b'readme', 'USAGE.md': b'usage',
                         'THIRD_PARTY_NOTICES.txt': b'license notices',
                         'manifest.schema.json': b'{"$id":"urn:woobe:manifest:steps:1"}',
                         'resources.schema.json': b'{"$id":"urn:woobe:manifest:resources:2"}'}
                suffix = 'zip' if system == 'windows' else 'tar.gz'
                path = root / f'woobe_{self.version}_{system}_{arch}.{suffix}'
                if system == 'windows':
                    with zipfile.ZipFile(path, 'w') as archive:
                        for name, payload in files.items(): archive.writestr(name, payload)
                else:
                    with tarfile.open(path, 'w:gz') as archive:
                        for name, payload in files.items():
                            info = tarfile.TarInfo(name); info.size = len(payload)
                            info.mode = 0o755 if name == executable else 0o644
                            archive.addfile(info, io.BytesIO(payload))
                artifacts.append(dict(name=path.name, os=system, arch=arch, bytes=path.stat().st_size,
                                      sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        metadata = root / 'artifacts.json'
        metadata.write_text(json.dumps(dict(version=self.version, commit=self.commit, artifacts=artifacts)))
        self.digest = hashlib.sha256(metadata.read_bytes()).hexdigest()
        (root / 'SHA256SUMS').write_text(''.join(f'{a["sha256"]}  {a["name"]}\n' for a in artifacts))

    def test_context_uses_exact_linux_bytes_and_reproducible_timestamps(self):
        root = prepare_image.prepare(self.commit, self.version, self.digest, epoch=123456789)
        for arch in ['amd64', 'arm64']:
            binary = root / arch / 'woobe'
            self.assertEqual(binary.read_bytes(), self.binary['linux', arch])
            self.assertTrue(binary.stat().st_mode & 0o111)
            self.assertEqual(int(binary.stat().st_mtime), 123456789)

    def test_wrong_manifest_digest_is_rejected_before_extraction(self):
        with self.assertRaisesRegex(ValueError, 'manifest digest'):
            prepare_image.prepare(self.commit, self.version, 'b' * 64)
        self.assertFalse(pathlib.Path('dist/oci').exists())

    def test_wrong_source_or_version_is_rejected(self):
        for commit, version in [('b' * 40, self.version), (self.commit, '0.1.1')]:
            with self.assertRaises(ValueError):
                prepare_image.prepare(commit, version, self.digest)


class RegistryTests(unittest.TestCase):
    def test_auth_failure_is_not_missing_image(self):
        result = subprocess.CompletedProcess([], 1, '', 'unauthorized: authentication required')
        with patch.object(registry_image.subprocess, 'run', return_value=result):
            with self.assertRaises(RuntimeError): registry_image.inspect('ghcr.io/owner/woobe-cli:1.0.0', missing=True)

    def test_missing_manifest_is_distinct(self):
        result = subprocess.CompletedProcess([], 1, '', 'ERROR: ghcr.io/owner/woobe-cli:1.0.0: not found')
        with patch.object(registry_image.subprocess, 'run', return_value=result):
            self.assertIsNone(registry_image.inspect('ghcr.io/owner/woobe-cli:1.0.0', missing=True))

    def test_conflicting_registry_version_is_immutable(self):
        digest = 'sha256:' + 'a' * 64
        manifest = json.dumps({'manifests': [{'platform': {'os': 'linux', 'architecture': arch}} for arch in ['amd64', 'arm64']]})
        with patch.object(registry_image, 'inspect', side_effect=[digest, 'sha256:' + 'b' * 64]), \
             patch.object(registry_image.subprocess, 'check_output', return_value=manifest):
            with self.assertRaisesRegex(ValueError, 'different digest'):
                registry_image.preflight('ghcr.io/owner/woobe-cli', '1.0.0', digest)


if __name__ == '__main__': unittest.main()
