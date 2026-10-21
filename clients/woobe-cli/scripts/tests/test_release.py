import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import publish_release as release
import release_identity as identity


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.archive = pathlib.Path(self.directory.name) / 'woobe_0.1.0_linux_amd64.tar.gz'
        self.archive.write_bytes(b'exact validated native archive')
        self.files = {self.archive.name: self.archive}
        self.commit = 'a' * 40
        self.repo = 'owner/woobe-cli'

    def github(self, path, missing=False):
        if path == f'repos/{self.repo}':
            return {'full_name': self.repo}
        if '/releases?' in path:
            return []
        return None

    def test_native_preflight_needs_no_npm_token_or_registry(self):
        with patch.dict(os.environ, {'NODE_AUTH_TOKEN': '', 'NPM_TOKEN': ''}), \
             patch.object(release, 'github', side_effect=self.github), \
             patch.object(release, 'run') as command:
            self.assertEqual(release.preflight(self.repo, '0.1.0', self.commit, self.files), (None, set(), False))
            command.assert_not_called()

    def test_wrong_repository_identity_is_refused_before_writes(self):
        with patch.object(release, 'github', return_value={'full_name': 'other/repo'}), \
             patch.object(release, 'run') as command:
            with self.assertRaisesRegex(ValueError, 'repository identity'):
                release.publish(self.repo, '0.1.0', self.commit, self.files)
            command.assert_not_called()

    def test_unknown_http_error_is_never_absence(self):
        from urllib.error import HTTPError
        for code in [401, 403, 429, 500]:
            with self.subTest(code=code), patch.object(release.urllib.request, 'urlopen',
                    side_effect=HTTPError('https://example.com', code, 'error', {}, None)):
                with self.assertRaises(RuntimeError):
                    release.fetch('https://example.com', missing=True)

    def test_404_is_absence(self):
        from urllib.error import HTTPError
        with patch.object(release.urllib.request, 'urlopen',
                side_effect=HTTPError('https://example.com', 404, 'not found', {}, None)):
            self.assertIsNone(release.fetch('https://example.com', missing=True))

    def test_conflicting_tag_blocks_publication(self):
        def github(path, missing=False):
            if '/git/ref/' in path:
                return {'object': {'type': 'commit', 'sha': 'b' * 40}}
            return self.github(path, missing)
        with patch.object(release, 'github', side_effect=github), patch.object(release, 'run') as command:
            with self.assertRaisesRegex(ValueError, 'different commit'):
                release.publish(self.repo, '0.1.0', self.commit, self.files)
            command.assert_not_called()

    def test_asset_conflict_blocks_publication(self):
        def github(path, missing=False):
            if '/git/ref/' in path:
                return {'object': {'type': 'commit', 'sha': self.commit}}
            if '/releases/tags/' in path:
                return {'tag_name': 'v0.1.0', 'draft': True, 'prerelease': False,
                        'assets': [{'name': self.archive.name, 'size': 1}]}
            return self.github(path, missing)
        with patch.object(release, 'github', side_effect=github), patch.object(release, 'run') as command:
            with self.assertRaisesRegex(ValueError, 'asset differs'):
                release.publish(self.repo, '0.1.0', self.commit, self.files)
            command.assert_not_called()

    def test_same_size_asset_with_different_bytes_is_refused(self):
        record = {'tag_name': 'v0.1.0', 'assets': [{'name': self.archive.name, 'size': self.archive.stat().st_size}]}
        def download(*args, **kwargs):
            folder = pathlib.Path(args[args.index('--dir') + 1])
            (folder / self.archive.name).write_bytes(b'x' * self.archive.stat().st_size)
        with patch.object(release, 'run', side_effect=download):
            with self.assertRaisesRegex(ValueError, 'asset differs'):
                release.verify_assets(self.repo, record, self.files)

    def test_failed_preflight_never_writes(self):
        with patch.object(release, 'github', side_effect=RuntimeError('HTTP 403')), \
             patch.object(release, 'run') as command:
            with self.assertRaises(RuntimeError):
                release.publish(self.repo, '0.1.0', self.commit, self.files)
            command.assert_not_called()

    def test_complete_retry_does_not_recreate_tag_or_touch_assets(self):
        complete = {'tag_name': 'v0.1.0', 'draft': False, 'prerelease': False}
        state = (complete, set(self.files), True)
        with patch.object(release, 'preflight', return_value=state), \
             patch.object(release, 'verify_assets', return_value=set(self.files)), \
             patch.object(release, 'github', return_value=complete), patch.object(release, 'run') as command:
            release.publish(self.repo, '0.1.0', self.commit, self.files)
            commands = [call.args for call in command.call_args_list]
            self.assertEqual(len(commands), 1)  # published native smoke only
            self.assertIn('scripts/smoke_artifacts.py', commands[0])

    def test_resume_partial_draft_uploads_only_missing_assets(self):
        draft = {'tag_name': 'v0.1.0', 'draft': True}
        published = dict(draft, draft=False)
        with patch.object(release, 'preflight', side_effect=[(draft, set(), True), (published, set(self.files), True)]), \
             patch.object(release, 'verify_assets', return_value=set(self.files)), \
             patch.object(release, 'github', return_value=draft), \
             patch.object(release, 'published_versions', return_value=[]), patch.object(release, 'run') as command:
            release.publish(self.repo, '0.1.0', self.commit, self.files)
            commands = [call.args for call in command.call_args_list]
            self.assertTrue(any(args[:3] == ('gh', 'release', 'upload') for args in commands))
            self.assertFalse(any('--clobber' in args for args in commands))
            self.assertFalse(any(args[:2] == ('gh', 'api') for args in commands))

    def test_fresh_release_reserves_identity_before_uploading(self):
        draft = {'tag_name': 'v0.1.0', 'draft': True}
        published = dict(draft, draft=False)
        with patch.object(release, 'preflight', side_effect=[(None, set(), False), (published, set(self.files), True)]), \
             patch.object(release, 'verify_assets', return_value=set(self.files)), \
             patch.object(release, 'github', return_value=draft), \
             patch.object(release, 'published_versions', return_value=[]), \
             patch.object(release, 'run') as command, patch.object(release.pathlib.Path, 'write_text'):
            release.publish(self.repo, '0.1.0', self.commit, self.files)
            commands = [call.args for call in command.call_args_list]
            self.assertEqual(commands[0][:2], ('gh', 'api'))
            self.assertIn('ref=refs/tags/v0.1.0', commands[0])
            self.assertIn(f'sha={self.commit}', commands[0])
            create = next(args for args in commands if args[:3] == ('gh', 'release', 'create'))
            self.assertIn('--draft', create)
            self.assertIn('--verify-tag', create)
            self.assertTrue(all(args[0] != 'npm' for args in commands))

    def test_failed_postpublish_smoke_keeps_release_draft(self):
        draft = {'tag_name': 'v0.1.0', 'draft': True}
        with patch.object(release, 'preflight', return_value=(draft, set(self.files), True)), \
             patch.object(release, 'verify_assets', return_value=set(self.files)), \
             patch.object(release, 'github', return_value=draft), \
             patch.object(release, 'run', side_effect=RuntimeError('native smoke failed')) as command:
            with self.assertRaises(RuntimeError):
                release.publish(self.repo, '0.1.0', self.commit, self.files)
            self.assertEqual(command.call_count, 1)
            self.assertIn('scripts/smoke_artifacts.py', command.call_args.args)

    def test_recovery_of_old_draft_does_not_move_latest_backwards(self):
        draft = {'tag_name': 'v0.1.0', 'draft': True}
        with patch.object(release, 'preflight', side_effect=[(draft, set(self.files), True), (dict(draft, draft=False), set(self.files), True)]), \
             patch.object(release, 'verify_assets', return_value=set(self.files)), \
             patch.object(release, 'github', return_value=draft), \
             patch.object(release, 'published_versions', return_value=['0.2.0']), \
             patch.object(release, 'run') as command:
            release.publish(self.repo, '0.1.0', self.commit, self.files)
            edit = next(call.args for call in command.call_args_list if call.args[:3] == ('gh', 'release', 'edit'))
            self.assertIn('--latest=false', edit)

    def test_preflight_only_never_publishes(self):
        with patch.object(release, 'preflight', return_value=(None, set(), False)), \
             patch.object(release, 'run') as command:
            release.publish(self.repo, '0.1.0', self.commit, self.files, preflight_only=True)
            command.assert_not_called()

    def test_draft_without_tag_recovers_only_the_exact_commit(self):
        def github(path, missing=False):
            if '/releases/tags/' in path:
                return {'tag_name': 'v0.1.0', 'draft': True, 'prerelease': False,
                        'target_commitish': self.commit, 'assets': []}
            return self.github(path, missing)
        with patch.object(release, 'github', side_effect=github):
            draft, assets, reserved = release.preflight(self.repo, '0.1.0', self.commit, self.files)
            self.assertTrue(draft['draft'])
            self.assertFalse(reserved)
            with self.assertRaisesRegex(ValueError, 'exact draft revision'):
                release.preflight(self.repo, '0.1.0', 'b' * 40, self.files)

    def test_draft_hidden_by_tag_endpoint_is_found_by_id(self):
        draft = {'id': 42, 'tag_name': 'v0.1.0', 'draft': True,
                 'prerelease': False, 'target_commitish': self.commit, 'assets': []}
        def github(path, missing=False):
            if '/git/ref/' in path:
                return {'object': {'type': 'commit', 'sha': self.commit}}
            if '/releases/tags/' in path:
                return None
            if '/releases?' in path:
                return [draft]
            if path.endswith('/releases/42'):
                return draft
            return self.github(path, missing)
        with patch.object(release, 'github', side_effect=github):
            actual, assets, reserved = release.preflight(self.repo, '0.1.0', self.commit, self.files)
            self.assertEqual(actual, draft)
            self.assertEqual(assets, set())
            self.assertTrue(reserved)

    def test_new_version_must_advance_published_versions(self):
        with patch.object(release, 'github', side_effect=self.github), \
             patch.object(release, 'published_versions', return_value=['0.2.0']):
            with self.assertRaisesRegex(ValueError, 'highest published'):
                release.preflight(self.repo, '0.1.0', self.commit, self.files)

    def test_ghcr_conflict_blocks_release_writes(self):
        with patch.object(release, 'preflight', return_value=(None, set(), False)), \
             patch.object(release.registry_image, 'preflight', side_effect=ValueError('immutable registry conflict')), \
             patch.object(release, 'run') as command:
            with self.assertRaises(ValueError):
                release.publish(self.repo, '0.1.0', self.commit, self.files,
                                image={'ref': 'ghcr.io/owner/woobe-cli', 'digest': 'sha256:' + 'a' * 64})
            command.assert_not_called()


class IdentityTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        previous = pathlib.Path.cwd()
        self.addCleanup(os.chdir, previous)
        os.chdir(directory.name)
        self.git('init', '--initial-branch=master')
        self.git('config', 'user.name', 'Release fixture')
        self.git('config', 'user.email', 'fixture@example.com')
        self.git('config', 'commit.gpgsign', 'false')
        self.git('config', 'core.hooksPath', '/dev/null')
        self.floor('0.1.0')
        self.counter = 0
        self.first = self.commit('chore: initial source')

    def git(self, *args):
        return subprocess.check_output(['git', *args], text=True, stderr=subprocess.DEVNULL).strip()

    def floor(self, version):
        pathlib.Path('VERSION').write_text(version + '\n')
        package = pathlib.Path('packages/woobe-cli/package.json')
        package.parent.mkdir(parents=True, exist_ok=True)
        package.write_text(json.dumps({'version': version}))

    def commit(self, message, integrated=True):
        self.counter += 1
        pathlib.Path('note.txt').write_text(str(self.counter))
        self.git('add', '.')
        self.git('commit', '-m', message)
        sha = self.git('rev-parse', 'HEAD')
        if integrated:
            self.git('update-ref', 'refs/remotes/origin/master', sha)
        return sha

    def test_first_release_uses_source_floor(self):
        self.assertEqual(identity.select(), ('0.1.0', self.first))

    def test_default_patch_requires_no_version_edit(self):
        self.git('tag', 'v0.1.0')
        sha = self.commit('fix: improve downloads')
        self.assertEqual(identity.select(), ('0.1.1', sha))
        self.assertEqual(pathlib.Path('VERSION').read_text(), '0.1.0\n')
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(identity.resolve('0.1.1', sha), sha)

    def test_feature_bumps_minor(self):
        self.git('tag', 'v0.1.0')
        sha = self.commit('feat(cli): new command')
        self.assertEqual(identity.select(), ('0.2.0', sha))

    def test_feature_example_in_docs_commit_body_does_not_bump_minor(self):
        self.git('tag', 'v0.1.0')
        sha = self.commit('docs: show conventional commits\n\nfeat: a commit example')
        self.assertEqual(identity.select(), ('0.1.1', sha))

    def test_breaking_before_one_bumps_minor(self):
        self.git('tag', 'v0.1.0')
        sha = self.commit('fix(api)!: change command format')
        self.assertEqual(identity.select(), ('0.2.0', sha))

    def test_breaking_after_one_bumps_major(self):
        self.git('tag', 'v1.2.3')
        sha = self.commit('refactor: change format\n\nBREAKING CHANGE: old payload unsupported')
        self.assertEqual(identity.select(), ('2.0.0', sha))

    def test_reviewed_source_floor_can_raise_next_version(self):
        self.git('tag', 'v0.1.0')
        self.floor('0.5.0')
        sha = self.commit('chore: choose higher baseline')
        self.assertEqual(identity.select(), ('0.5.0', sha))

    def test_retry_of_same_source_recovers_its_reserved_version(self):
        self.git('tag', 'v0.1.0')
        sha = self.commit('fix: one')
        self.git('tag', 'v0.1.1')
        self.commit('fix: two')
        self.git('tag', 'v0.1.2')
        self.assertEqual(identity.select(revision=sha), ('0.1.1', sha))
        self.assertEqual(identity.select('0.1.1'), ('0.1.1', sha))

    def test_reserved_failed_version_is_not_reused_for_new_source(self):
        self.git('tag', 'v0.1.0')
        self.commit('fix: upload failed')
        self.git('tag', 'v0.1.1')
        sha = self.commit('fix: later source')
        self.assertEqual(identity.select(), ('0.1.2', sha))

    def test_stale_unreleased_push_is_skipped(self):
        self.git('tag', 'v0.1.0')
        stale = self.commit('fix: stale pending push')
        self.commit('fix: newer push')
        self.git('tag', 'v0.1.1')
        self.assertIsNone(identity.select(revision=stale))

    def test_revision_must_be_integrated_and_match_existing_tag(self):
        self.git('tag', 'v0.1.0')
        sha = self.commit('fix: later')
        with self.assertRaisesRegex(ValueError, 'different commit'):
            identity.select('0.1.0', sha)
        self.git('checkout', '-b', 'feature')
        unreviewed = self.commit('feat: unreviewed source', integrated=False)
        with self.assertRaisesRegex(ValueError, 'integrated in master'):
            identity.select(revision=unreviewed)

    def test_invalid_identity_and_regressing_explicit_version_are_rejected(self):
        with self.assertRaises(ValueError):
            identity.select(revision='master')
        self.git('tag', 'v0.1.0')
        self.commit('fix: later')
        with self.assertRaisesRegex(ValueError, 'highest reserved'):
            identity.select('0.0.9')

    def test_mismatched_source_version_is_rejected(self):
        pathlib.Path('packages/woobe-cli/package.json').write_text('{"version":"0.2.0"}')
        self.commit('chore: inconsistent source')
        with self.assertRaisesRegex(ValueError, 'differ'):
                identity.select()

    def test_owner_tag_can_release_without_merging_but_must_pin_exact_source(self):
        self.git('checkout', '-b', 'release-feature')
        sha = self.commit('fix: package publication', integrated=False)
        self.git('tag', 'v0.1.1')
        self.assertEqual(identity.select('0.1.1', sha, trusted_tag=True), ('0.1.1', sha))
        with self.assertRaisesRegex(ValueError, 'existing immutable source tag'):
            identity.select('0.1.2', sha, trusted_tag=True)
        with self.assertRaisesRegex(ValueError, 'integrated in master'):
            identity.select('0.1.1', sha)

    def test_prerelease_becomes_stable_without_changing_source(self):
        self.git('tag', 'v0.2.0-rc.1')
        sha = self.commit('fix: qualify stable release')
        self.assertEqual(identity.select(), ('0.2.0', sha))


if __name__ == '__main__':
    unittest.main()
