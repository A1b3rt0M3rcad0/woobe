"""Exercise recovery/intent behavior of the official deploy-only shell example."""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import textwrap
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def scripts():
    lines = (ROOT / 'docs/examples/deployment/deploy-release.yml').read_text().splitlines()
    result = {}
    name = ''
    for index, line in enumerate(lines):
        if line.startswith('      - name: '):
            name = line.split(': ', 1)[1]
        if line == '        run: |':
            block = []
            for following in lines[index + 1:]:
                if following.strip() and not following.startswith('          '):
                    break
                block.append(following)
            result[name] = textwrap.dedent('\n'.join(block))
    return result


@unittest.skipIf(os.name == 'nt', 'Bash example targets a Linux delivery runner')
class DeploymentWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = pathlib.Path(self.directory.name)
        self.state = self.root / 'woobe-delivery/900'
        self.state.mkdir(parents=True, mode=0o700)
        self.env = {**os.environ, 'RUNNER_TEMP':str(self.root), 'GH_REPO':'fixture/app',
                    'WORKFLOW_RUN':'900', 'WORKFLOW_ATTEMPT':'1',
                    'WOOBE_API_URL':'https://woobe.example',
                    'WOOBE_WORKSPACE_ID':'11111111-1111-4111-8111-111111111111',
                    'WOOBE_PROJECT_ID':'22222222-2222-4222-8222-222222222222',
                    'TARGET_KIND':'agent','TARGET_ID':'33333333-3333-4333-8333-333333333333',
                    'RELEASE_ID':'44444444-4444-4444-8444-444444444444',
                    'AUDIT_NOTES':'Approved delivery', 'CHECKPOINT_KEY':'Disposable-test-only-passphrase'}
        self.env['GNUPGHOME']=str(self.state/'gnupg')
        (self.state/'gnupg').mkdir(mode=0o700)
        fake = self.state / 'woobe'
        fake.write_text('''#!/usr/bin/env python3
import json, pathlib, sys
root=pathlib.Path(__file__).parent
(root/'argv.json').write_text(json.dumps(sys.argv[1:]))
checkpoint=sys.argv[sys.argv.index('--checkpoint')+1]
pathlib.Path(checkpoint).write_text('{"schema_version":"1.0","intent_id":"original"}')
print(json.dumps({'success':True,'data':{'intent_id':'original','release_id':'qualified','status':'completed'}}))
''')
        fake.chmod(0o700)

    def run_step(self, name):
        return subprocess.run(['bash','-c',scripts()[name]],env=self.env,capture_output=True,text=True)

    def test_every_shell_step_is_valid_bash(self):
        for name, block in scripts().items():
            with self.subTest(name=name):
                result = subprocess.run(['bash','-n'],input=block,text=True,capture_output=True)
                self.assertEqual(result.returncode,0,result.stderr)

    def test_stable_intent_and_original_resume_across_attempts(self):
        name = 'Deploy or resume exact original intention'
        self.assertEqual(self.run_step(name).returncode,0)
        initial = json.loads((self.state/'argv.json').read_text())
        original = initial[initial.index('--intent')+1]
        self.assertIn('--from',initial)
        self.env['WORKFLOW_ATTEMPT']='2'
        self.assertEqual(self.run_step(name).returncode,0)
        resumed=json.loads((self.state/'argv.json').read_text())
        self.assertEqual(resumed[resumed.index('--intent')+1],original)
        self.assertIn('resume',resumed)
        self.assertNotIn('--from',resumed)
        self.env['WOOBE_PROJECT_ID']='55555555-5555-4555-8555-555555555555'
        self.assertEqual(self.run_step(name).returncode,0)
        scoped=json.loads((self.state/'argv.json').read_text())
        self.assertNotEqual(scoped[scoped.index('--intent')+1],original)

    def test_missing_checkpoint_blocks_rerun_before_cli(self):
        self.env['WORKFLOW_ATTEMPT']='2'
        result=self.run_step('Deploy or resume exact original intention')
        self.assertEqual(result.returncode,9)
        self.assertFalse((self.state/'argv.json').exists())

    @unittest.skipUnless(shutil.which('gpg'), 'GPG is required by the delivery runner')
    def test_recovery_is_encrypted_and_public_summary_excludes_private_fields(self):
        (self.state/'intent.json').write_text('{"private":"retained-journal-test-marker"}')
        (self.state/'result.json').write_text(json.dumps({'success':False,'data':{
            'intent_id':'original','status':'outcome_unknown','local':{'credentials':'private-binding'},
            'operations':{'original':'operation'},'secret':'private-binding'}}))
        result=self.run_step('Preserve integrity-protected recovery checkpoint')
        self.assertEqual(result.returncode,0,result.stderr)
        encrypted=(self.state/'intent.gpg').read_bytes()
        self.assertNotIn(b'retained-journal-test-marker',encrypted)
        summary=json.loads((self.state/'public-receipt.json').read_text())
        self.assertFalse(summary['success'])
        self.assertNotIn('private-binding',json.dumps(summary))
        self.assertNotIn('operations',summary)
        decrypted=subprocess.run(['gpg','--batch','--pinentry-mode','loopback','--passphrase-fd','0','--decrypt',str(self.state/'intent.gpg')],
                                 input=self.env['CHECKPOINT_KEY'],capture_output=True,text=True,env=self.env)
        self.assertEqual(decrypted.returncode,0)
        self.assertIn('retained-journal-test-marker',decrypted.stdout)
