import importlib.util
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('cli_version', pathlib.Path(__file__).resolve().parents[1] / 'version.py')
version = importlib.util.module_from_spec(spec)
spec.loader.exec_module(version)


class VersionTests(unittest.TestCase):
    def test_semver_accepts_stable_and_prerelease_versions(self):
        for value in ['0.1.0', '10.2.30', '0.1.0-rc.1', '0.0.0-ci.123.2', '1.2.3-beta-1']:
            self.assertEqual(version.validate(value), value)

    def test_rejects_ambiguous_or_noncanonical_versions(self):
        for value in ['v0.1.0', '1.2', '01.2.3', '1.02.3', '1.2.3-01', '1.2.3+',
                      '1.2.3+build.1', '1.2.3-', '1.2.3-a..b', '1.2.3\n', '1.2.3/../x']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                version.validate(value)

    def test_mismatched_npm_version_blocks_distribution(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            canonical = root / 'VERSION'
            package = root / 'package.json'
            canonical.write_text('0.1.0\n')
            skill = root / 'skill.json'
            skill.write_text(json.dumps({'version': '0.1.0'}))
            package.write_text(json.dumps({'version': '0.2.0'}))
            with patch.object(version, 'VERSION_FILE', canonical), patch.object(version, 'PACKAGE_FILE', package), patch.object(version, 'SKILL_PACKAGE_FILE', skill):
                with self.assertRaisesRegex(ValueError, 'differs'):
                    version.check()
                package.write_text(json.dumps({'version': '0.1.0'}))
                self.assertEqual(version.check(), '0.1.0')
                skill.write_text(json.dumps({'version': '0.3.0'}))
                with self.assertRaisesRegex(ValueError, 'skill npm package'):
                    version.check()

    def test_set_updates_both_files_and_rejects_invalid_input_without_writes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = pathlib.Path(directory)
            (root / 'scripts').mkdir()
            (root / 'packages/woobe-cli').mkdir(parents=True)
            (root / 'packages/woobe-cli-skill').mkdir(parents=True)
            skill = root / 'packages/woobe-cli-skill/package.json'
            skill.write_text(json.dumps({'name': 'woobe-cli-skill', 'version': '0.1.0'}))
            script = root / 'scripts/version.py'
            shutil.copy2(spec.origin, script)
            canonical = root / 'VERSION'
            package = root / 'packages/woobe-cli/package.json'
            canonical.write_text('0.1.0\n')
            package.write_text(json.dumps({'name': 'woobe-cli', 'version': '0.1.0'}))
            result = subprocess.run([sys.executable, str(script), '--set', '0.2.0-rc.1'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(canonical.read_text(), '0.2.0-rc.1\n')
            self.assertEqual(json.loads(package.read_text())['version'], '0.2.0-rc.1')
            self.assertEqual(json.loads(skill.read_text())['version'], '0.2.0-rc.1')
            previous = (canonical.read_bytes(), package.read_bytes(), skill.read_bytes())
            result = subprocess.run([sys.executable, str(script), '--set', 'v1.0.0'],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertEqual((canonical.read_bytes(), package.read_bytes(), skill.read_bytes()), previous)


if __name__ == '__main__':
    unittest.main()
