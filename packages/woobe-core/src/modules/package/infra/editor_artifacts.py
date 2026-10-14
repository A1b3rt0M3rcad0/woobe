"""Bounded text editing of a retained closure, through the Package codec."""
import io
import os

from modules.package.domain.errors import PackageError
from modules.package.domain.configuration import package_requirements
from modules.package.infra.bundles import confined_reader, snapshot_directory

MAX_EDITOR_FILE = 1 << 20
MAX_EDITOR_TOTAL = 4 << 20


def editor_files(bundle):
    files=[];total=0
    for item in bundle.inventory:
        path=item['path'];content=None;reason=None
        if path=='woobe.yaml':
            reason='package_manifest'
        elif item['size_bytes']>MAX_EDITOR_FILE or total+item['size_bytes']>MAX_EDITOR_TOTAL:
            reason='editor_size_limit'
        else:
            with confined_reader(bundle.root,path) as stream:
                raw=stream.read(MAX_EDITOR_FILE+1)
            try:
                content=raw.decode('utf-8')
                if '\x00' in content:
                    raise UnicodeError
                total+=len(raw)
            except UnicodeError:
                reason='binary_file';content=None
        files.append({**item,'content':content,'editable':content is not None,'readonly_reason':reason})
    entry=bundle.graph.manifest['spec']['entrypoint']
    return {'entrypoint_path':bundle.graph.paths[entry['ref']],'files':files,
            'requirements':package_requirements(bundle.graph.manifest),
            'component_digests_status':'validated_closed_object','complete':True}


def editor_binding_document(manifest, credentials):
    """Retained Web edits reuse exact captured identities, never create values."""
    version = manifest.get('schema_version', '1.0')
    requirements = package_requirements(manifest)
    spec = {}
    groups = ('credentials', 'project_environment', 'knowledge') if version == '2.0' else ('credentials', 'project_environment', 'secrets', 'knowledge')
    for group in groups:
        values = {}
        for item in requirements.get(group, []):
            alias = item.get('key') if group == 'project_environment' else item.get('ref')
            if group == 'credentials':
                if alias not in credentials:
                    raise PackageError('ASAC_EDITOR_BINDING_UNAVAILABLE', 'An explicit Provider binding is required')
                values[alias] = {'credential_id': credentials[alias]}
            elif group == 'knowledge':
                raise PackageError('ASAC_EDITOR_BINDING_UNAVAILABLE', 'Open a portable Knowledge closure before Web Stage')
            else:
                values[alias] = {'existing_key': alias}
        spec[group] = values
    return {'format': 'woobe-package', 'schema_version': version,
            'kind': 'ImportBindings', 'metadata': {'name': 'Web Candidate'}, 'spec': spec}


def edited_archive(bundle,replacements):
    with bundle:
        available={item['path']:item for item in editor_files(bundle)['files']}
        total=0;seen=set()
        for item in replacements:
            path,content=item['path'],item['content']
            if path in seen or path not in available or not available[path]['editable']:
                raise PackageError('ASAC_EDITOR_PATH_INVALID','Only distinct editable files in this closed object may be changed')
            seen.add(path)
            encoded=content.encode('utf-8');total+=len(encoded)
            if len(encoded)>MAX_EDITOR_FILE or total>MAX_EDITOR_TOTAL or '\x00' in content:
                raise PackageError('ASAC_EDITOR_LIMIT','Edited text exceeds the bounded editor limits')
            descriptor=os.open(bundle.root/path,os.O_WRONLY|os.O_TRUNC|os.O_NOFOLLOW)
            with os.fdopen(descriptor,'wb') as file:
                file.write(encoded)
        # Rebuild graph, schema, references and inventory with the canonical
        # Package codec. No original storage object or native Draft is modified.
        with snapshot_directory(bundle.root) as rebuilt:
            stream=io.BytesIO();rebuilt.archive(stream,include_lock=True);stream.seek(0)
            return stream
