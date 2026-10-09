#!/usr/bin/env python3
"""Offline instance trust provisioning. Prints only public fingerprints/paths."""
import argparse
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import stat
import sys
from uuid import UUID

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packages'/'woobe-core'/'src'))
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from modules.core.infra.receipts.asac_signer import (
    ASaCReceiptSigner, create_trust_manifest, decode, encode, fingerprint, timestamp,
)
from shared.contracts.asac import asac_digest


def private_seed(path):
    file=Path(path)
    if file.is_symlink() or not file.is_file():
        raise ValueError('Root key must be a regular private file')
    info=file.stat()
    if os.name!='nt' and (stat.S_IMODE(info.st_mode)&0o077 or info.st_uid!=os.getuid()):
        raise ValueError('Root key must be owned by the operator and mode 0600')
    if info.st_size>128:
        raise ValueError('Invalid root key size')
    return decode(file.read_text().strip(),32)


def create_file(path,value,mode):
    descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,mode)
    with os.fdopen(descriptor,'w') as file:
        file.write(value+'\n');file.flush();os.fsync(file.fileno())


def provision(*,directory,instance_id,expires_at,key_until,root_seed=None,previous=None,revoke=(),now=None):
    now=now or datetime.now(UTC)
    if now.tzinfo is None or timestamp(expires_at)<=now or timestamp(key_until)<=now:
        raise ValueError('Trust and key expiry must be in the future')
    root=Ed25519PrivateKey.from_private_bytes(root_seed) if root_seed is not None else Ed25519PrivateKey.generate()
    online=Ed25519PrivateKey.generate();epoch=1;keys=[]
    if previous is not None:
        instance_id=previous['instance_id']
        if type(previous['epoch']) is not int or previous['epoch']<1:
            raise ValueError('Invalid previous trust epoch')
        unsigned={key:value for key,value in previous.items() if key not in {'record_digest','signature'}}
        expected=asac_digest('trust-manifest',unsigned)
        if expected!=previous['record_digest'] or previous['root_public_key']!=encode(root.public_key().public_bytes_raw()):
            raise ValueError('Previous manifest differs from the offline root')
        root.public_key().verify(decode(previous['signature'],64),expected.encode('ascii'))
        epoch=previous['epoch']+1
        known={key['key_id'] for key in previous['keys']}
        if not set(revoke)<=known:
            raise ValueError('Only known key identities can be revoked')
        for old in previous['keys']:
            key={field:old[field] for field in ('public_key','status','not_before','not_after')}
            if old['key_id'] in revoke:
                key['status']='revoked'
            elif key['status']=='active':
                key['status']='retired'
                key['not_after']=min(timestamp(key['not_after']),now).isoformat()
            keys.append(key)
    elif revoke:
        raise ValueError('Revocation requires a previous root-signed manifest')
    keys.append({'public_key':encode(online.public_key().public_bytes_raw()),'status':'active',
                 'not_before':now.isoformat(),'not_after':key_until})
    manifest=create_trust_manifest(instance_id=str(UUID(instance_id)),root_private_key=encode(root.private_bytes_raw()),
        epoch=epoch,expires_at=expires_at,keys=keys)
    signer=ASaCReceiptSigner(trust_manifest=manifest,receipt_private_key=encode(online.private_bytes_raw()),clock=lambda:now)
    signer.attest(category='history',project_id=UUID(int=1),resource_id=UUID(int=2),kind='Agent',receipt={})
    destination=Path(directory)
    # Never overwrite an operator's root, online key or previous manifest.
    destination.mkdir(mode=0o700)
    if previous is None:
        create_file(destination/'root.seed',encode(root.private_bytes_raw()),0o600)
    create_file(destination/'receipt.seed',encode(online.private_bytes_raw()),0o600)
    create_file(destination/'trust.json',json.dumps(manifest,indent=2),0o644)
    # This deployable file has the online seed only, never the offline root.
    deploy='WOOBE_ASAC_SIGNING_RECEIPT_PRIVATE_KEY='+encode(online.private_bytes_raw())+'\n'
    deploy+="WOOBE_ASAC_SIGNING_TRUST_MANIFEST='"+json.dumps(manifest,separators=(',',':'))+"'"
    create_file(destination/'online.env',deploy,0o600)
    return {'directory':str(destination),'instance_id':manifest['instance_id'],
            'root_fingerprint':manifest['root_fingerprint'],'trust_epoch':epoch,
            'online_key_id':fingerprint(online.public_key().public_bytes_raw()),
            'trust_expires_at':expires_at}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('init','rotate'))
    parser.add_argument('--directory',required=True,help='New private directory; never overwritten')
    parser.add_argument('--instance',help='Stable instance UUID, required for init')
    parser.add_argument('--expires-at',required=True,help='Root manifest expiry with timezone')
    parser.add_argument('--key-until',required=True,help='Online receipt key expiry with timezone')
    parser.add_argument('--root-key',help='Offline root.seed; rotate only')
    parser.add_argument('--manifest',help='Previous root-signed trust.json; rotate only')
    parser.add_argument('--revoke',action='append',default=[],help='Previous key fingerprint to revoke; repeatable')
    args=parser.parse_args()
    try:
        previous=None;seed=None
        if args.action=='init':
            if not args.instance or args.root_key or args.manifest or args.revoke:
                raise ValueError('init requires only a stable instance UUID and new validity dates')
        else:
            if not args.root_key or not args.manifest or args.instance:
                raise ValueError('rotate requires the offline root key and previous manifest')
            seed=private_seed(args.root_key)
            file=Path(args.manifest)
            if not file.is_file() or file.stat().st_size>65536:
                raise ValueError('Previous manifest must be a bounded regular JSON file')
            previous=json.loads(file.read_text())
        print(json.dumps(provision(directory=args.directory,instance_id=args.instance,
            expires_at=args.expires_at,key_until=args.key_until,root_seed=seed,previous=previous,revoke=args.revoke)))
    except Exception:
        # Parsing/crypto failures must never print seed values, env contents or
        # traceback locals. Inspect public manifest and private file permissions.
        parser.exit(2,'Trust provisioning failed; check private file permissions, manifest/root identity, new directory and validity dates.\n')


if __name__=='__main__': main()
