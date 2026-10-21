import hashlib
import io
import json
import pathlib
import os
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import verify_skill
import publish_release


class SkillArtifactTests(unittest.TestCase):
    def fixture(self, root, mutate=None):
        source = pathlib.Path('packages/woobe-cli-skill')
        data = json.loads((source / 'package.json').read_text())
        data.pop('private')
        data['version'] = '0.0.0-ci.1'
        data['woobeSkill']['sourceCommit'] = 'a' * 40
        files = {file.relative_to(source).as_posix(): file.read_bytes() for file in source.rglob('*')
                 if file.is_file() and file.name != 'README.md' and file.suffix != '.go'}
        files['package.json'] = json.dumps(data).encode()
        files['README.md'] = pathlib.Path('docs/AGENT_SKILL.md').read_bytes()
        if mutate:
            mutate(files)
        artifact = root / 'woobe-cli-skill-0.0.0-ci.1.tgz'
        with tarfile.open(artifact, 'w:gz') as archive:
            for name, content in files.items():
                entry = tarfile.TarInfo('package/' + name)
                entry.size = len(content)
                entry.mode = 0o755 if name.startswith('bin/') else 0o644
                archive.addfile(entry, io.BytesIO(content))
        return dict(name=artifact.name, bytes=artifact.stat().st_size,
                    sha256=hashlib.sha256(artifact.read_bytes()).hexdigest())

    def test_exact_portable_skill_source_and_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            report = verify_skill.verify(root, self.fixture(root), '0.0.0-ci.1', 'a' * 40)
            self.assertTrue(report['success'])

    def test_tampered_skill_or_missing_reference_rejected_even_with_new_checksum(self):
        for mutate in [lambda files: files.update({'skills/woobe-cli/SKILL.md': b'changed'}),
                       lambda files: files.pop('skills/woobe-cli/references/recovery.md'),
                       lambda files: files.update({'unexpected.txt': b'extra'})]:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                root = pathlib.Path(directory)
                with self.assertRaises(AssertionError):
                    verify_skill.verify(root, self.fixture(root, mutate), '0.0.0-ci.1', 'a' * 40)

    def test_commit_version_and_hash_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            record = self.fixture(root)
            for version, commit, sha in [('0.0.0-ci.2', 'a' * 40, record['sha256']),
                                         ('0.0.0-ci.1', 'b' * 40, record['sha256']),
                                         ('0.0.0-ci.1', 'a' * 40, '0' * 64)]:
                with self.subTest(version=version, commit=commit, sha=sha), self.assertRaises(AssertionError):
                    verify_skill.verify(root, dict(record, sha256=sha), version, commit)

    def test_publishing_gate_preserves_existing_cli_oidc_job(self):
        workflow = pathlib.Path('.github/workflows/release.yml').read_text()
        cli, skill = workflow.split('  npm-skill:\n')
        self.assertNotIn('WOOBE_SKILL_NPM_PUBLISH', cli)
        self.assertIn("vars.WOOBE_SKILL_NPM_PUBLISH == 'true'", skill)
        self.assertIn('--package woobe-cli-skill', skill)
        self.assertIn('id-token: write', skill)
        self.assertNotIn('secrets.NPM_TOKEN', skill)
        self.assertIn("NODE_AUTH_TOKEN: ''", skill)

    def test_permanent_release_manifest_includes_skill_and_recovers_old_candidates(self):
        previous = pathlib.Path.cwd()
        with tempfile.TemporaryDirectory() as directory:
            try:
                os.chdir(directory)
                pathlib.Path('dist').mkdir()
                for include_skill in (False, True):
                    manifest = dict(version='1.2.3', commit='a' * 40, compiler='go version go1.27.1',
                                    artifacts=[dict(name='native.tar.gz')], npm=dict(name='woobe-cli-1.2.3.tgz'))
                    if include_skill:
                        manifest['skill_npm'] = dict(name='woobe-cli-skill-1.2.3.tgz', sha256='b' * 64)
                    document = pathlib.Path('dist/artifacts.json')
                    document.write_text(json.dumps(manifest))
                    digest = hashlib.sha256(document.read_bytes()).hexdigest()
                    with patch.object(publish_release, 'run', return_value='a' * 40), patch.object(publish_release, 'resolve'):
                        files = publish_release.candidate('1.2.3', 'a' * 40, digest)
                    record = json.loads(pathlib.Path('dist/release-manifest.json').read_text())
                    self.assertEqual('skill_npm' in record, include_skill)
                    self.assertEqual('woobe-cli-skill-1.2.3.tgz' in files, include_skill)
                    if include_skill:
                        self.assertEqual(record['skill_npm'], manifest['skill_npm'])
            finally:
                os.chdir(previous)
