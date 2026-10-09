"""Offline root rotation keeps private root material out of API deployment."""
import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('asac_trust_tool',Path(__file__).parents[3]/'scripts'/'asac_trust.py')
tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)


def test_offline_init_rotate_revoke_and_exclusive_private_output(tmp_path):
    now=datetime(2026,10,9,tzinfo=UTC)
    options={'expires_at':(now+timedelta(days=30)).isoformat(),
             'key_until':(now+timedelta(days=31)).isoformat(),'now':now}
    first=tmp_path/'first'
    result=tool.provision(directory=first,instance_id='00000000-0000-4000-8000-000000000001',**options)
    root=(first/'root.seed').read_text().strip()
    assert root not in (first/'online.env').read_text()
    assert root not in json.dumps(result)
    assert (first/'trust.json').read_text().find(root)==-1
    if os.name!='nt':
        for filename in ('root.seed','receipt.seed','online.env'):
            assert (first/filename).stat().st_mode&0o777==0o600
    previous=json.loads((first/'trust.json').read_text())
    second=tmp_path/'second'
    rotated=tool.provision(directory=second,instance_id=None,root_seed=tool.private_seed(first/'root.seed'),
        previous=previous,revoke=[result['online_key_id']],**{**options,'now':now+timedelta(hours=1)})
    assert rotated['root_fingerprint']==result['root_fingerprint'] and rotated['trust_epoch']==2
    manifest=json.loads((second/'trust.json').read_text())
    assert next(key for key in manifest['keys'] if key['key_id']==result['online_key_id'])['status']=='revoked'
    assert not (second/'root.seed').exists()
    with pytest.raises(FileExistsError):
        tool.provision(directory=first,instance_id='00000000-0000-4000-8000-000000000001',**options)


def test_manifest_tamper_or_unknown_revocation_does_not_create_outputs(tmp_path):
    now=datetime(2026,10,9,tzinfo=UTC)
    options={'expires_at':(now+timedelta(days=30)).isoformat(),'key_until':(now+timedelta(days=31)).isoformat(),'now':now}
    first=tmp_path/'first'
    tool.provision(directory=first,instance_id='00000000-0000-4000-8000-000000000001',**options)
    previous=json.loads((first/'trust.json').read_text());previous['epoch']=20
    with pytest.raises(ValueError):
        tool.provision(directory=tmp_path/'invalid',instance_id=None,root_seed=tool.private_seed(first/'root.seed'),previous=previous,**options)
    assert not (tmp_path/'invalid').exists()
    previous=json.loads((first/'trust.json').read_text())
    with pytest.raises(ValueError,match='known key'):
        tool.provision(directory=tmp_path/'unknown',instance_id=None,
            root_seed=tool.private_seed(first/'root.seed'),previous=previous,
            revoke=['sha256:'+'0'*64],**options)
    assert not (tmp_path/'unknown').exists()


def test_rotation_retires_old_key_without_rewriting_its_original_start(tmp_path):
    now=datetime(2026,10,9,tzinfo=UTC)
    options={'expires_at':(now+timedelta(days=30)).isoformat(),'key_until':(now+timedelta(days=31)).isoformat(),'now':now}
    first=tmp_path/'first'
    initial=tool.provision(directory=first,instance_id='00000000-0000-4000-8000-000000000001',**options)
    previous=json.loads((first/'trust.json').read_text())
    later=now+timedelta(hours=1)
    tool.provision(directory=tmp_path/'next',instance_id=None,
        root_seed=tool.private_seed(first/'root.seed'),previous=previous,**{**options,'now':later})
    manifest=json.loads((tmp_path/'next'/'trust.json').read_text())
    retired=next(key for key in manifest['keys'] if key['key_id']==initial['online_key_id'])
    assert retired['status']=='retired' and retired['not_after']==later.isoformat()
    assert retired['not_before']==previous['keys'][0]['not_before']
    assert previous==json.loads((first/'trust.json').read_text())


@pytest.mark.skipif(os.name=='nt',reason='POSIX owner/mode checks')
def test_offline_root_rejects_world_readable_or_symlink_input(tmp_path):
    seed=tmp_path/'root.seed';seed.write_text(tool.encode(bytes(range(32))));seed.chmod(0o644)
    with pytest.raises(ValueError,match='0600'):
        tool.private_seed(seed)
    seed.chmod(0o600)
    link=tmp_path/'link.seed';link.symlink_to(seed)
    with pytest.raises(ValueError,match='regular'):
        tool.private_seed(link)
