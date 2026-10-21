"""Deterministic first-party structural trees over canonical source identities."""
from dataclasses import replace
import hashlib
from uuid import NAMESPACE_URL, uuid5

from modules.artifacts.domain.models import ArtifactError, DocumentIndex, DocumentNode


ENGINE, ENGINE_VERSION = 'structural', '1'
MAX_NODES, MAX_DEPTH, MAX_INTERVALS = 110_001, 64, 1000


def node_identity(index_id, source):
    return str(uuid5(NAMESPACE_URL, f'woobe:structural:{ENGINE_VERSION}:{index_id}:{source}'))


def merge_ranges(intervals):
    merged = []
    for low, high in sorted(intervals):
        if merged and low <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], high))
        else:
            merged.append((low, high))
    if len(merged) > MAX_INTERVALS:
        raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Structural node exceeds its source interval limit')
    return tuple(merged)


def build_structural_index(document, index_id, representation_set_id):
    blocks = {block.id: block for block in document.blocks}
    positions = {block.id: ordinal for ordinal, block in enumerate(document.blocks)}
    headings = any(block.kind == 'heading' for block in document.blocks)
    explicit = any(block.parent_id is not None for block in document.blocks)
    tree_kind = 'canonical' if explicit else 'headings' if headings else 'pages' if document.pages else 'blocks'
    if not document.blocks:
        tree_kind = 'pages' if document.pages else 'empty'
    root_id = node_identity(index_id, 'root')
    nodes = [DocumentNode(root_id, 'Documento', (), kind='root')]
    page_nodes = {}
    if tree_kind == 'pages':
        for page in document.pages:
            identity = node_identity(index_id, f'page:{page.page_index}')
            page_nodes[page.page_index] = identity
            nodes.append(DocumentNode(identity, f'Página física {page.page_number} ({page.label})'[:512], (), root_id,
                kind='page', ordinal=len(blocks) + page.page_index + 1, page_index=page.page_index))
    stack = []
    for ordinal, block in enumerate(document.blocks):
        identity = node_identity(index_id, 'block:' + block.id)
        if block.parent_id is not None:
            parent = node_identity(index_id, 'block:' + block.parent_id)
        elif explicit:
            parent = root_id
        elif block.kind == 'heading':
            level = block.heading_level or 1
            while stack and stack[-1][0] >= level:
                stack.pop()
            parent = stack[-1][1] if stack else root_id
        elif tree_kind == 'pages' and block.locator.page_index is not None:
            parent = page_nodes[block.locator.page_index]
        else:
            parent = stack[-1][1] if stack else root_id
        if block.kind == 'heading':
            # Explicit hierarchy still determines parentage; this stack supplies
            # only the fallback for canonical blocks without a parent.
            level = block.heading_level or 1
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, identity))
        title = (block.title or block.text[:512].split('\n', 1)[0])[:512].strip()
        if not title:
            title = {'figure': 'Figura', 'table': 'Tabela'}.get(block.kind, 'Bloco') + f' {ordinal + 1}'
        nodes.append(DocumentNode(identity, title, (block.id,), parent,
            kind='section' if block.kind == 'heading' else 'block', ordinal=ordinal + 1,
            source_ranges=((ordinal, ordinal + 1),),
            block_sha256=hashlib.sha256(block.text.encode('utf-8')).hexdigest(), page_index=block.locator.page_index))
    if len(nodes) > MAX_NODES:
        raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Structural tree exceeds its node limit')
    by_id = {node.id: node for node in nodes}
    depths = {root_id: 0}
    for node in nodes:
        current, path, seen = node.id, [], set()
        while current not in depths:
            if current is None or current not in by_id or current in seen:
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Canonical hierarchy cannot form a valid structural tree')
            seen.add(current)
            path.append(current)
            current = by_id[current].parent_id
            if len(path) > MAX_DEPTH:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Structural tree exceeds its depth limit')
        depth = depths[current]
        for member in reversed(path):
            depth += 1
            if depth > MAX_DEPTH:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Structural tree exceeds its depth limit')
            depths[member] = depth
    ranges = {node.id: list(node.source_ranges) for node in nodes}
    for node in sorted(nodes, key=lambda value: depths[value.id], reverse=True):
        ranges[node.id] = list(merge_ranges(ranges[node.id]))
        if node.parent_id is not None:
            ranges[node.parent_id].extend(ranges[node.id])
    nodes = tuple(replace(node, depth=depths[node.id], source_ranges=tuple(ranges[node.id]))
                  for node in sorted(nodes, key=lambda value: value.ordinal))
    result = DocumentIndex(index_id, representation_set_id, ENGINE, ENGINE_VERSION, nodes,
                           tree_kind, len(blocks), document.coverage)
    validate_source_membership(result, document, positions)
    return result


def validate_source_membership(index, document, positions=None):
    positions = positions or {block.id: ordinal for ordinal, block in enumerate(document.blocks)}
    by_id = {block.id: block for block in document.blocks}
    owners = set()
    for node in index.nodes:
        for identity in node.block_ids:
            if identity not in positions or identity in owners:
                raise ValueError('Structural nodes must own each exact canonical block once')
            owners.add(identity)
            ordinal = positions[identity]
            if not any(low <= ordinal < high for low, high in node.source_ranges):
                raise ValueError('Structural block lies outside its source ranges')
            if node.block_sha256 != hashlib.sha256(by_id[identity].text.encode('utf-8')).hexdigest():
                raise ValueError('Structural node text checksum does not match canonical source')
    if owners != set(by_id):
        raise ValueError('Structural tree has unrepresented canonical blocks')
