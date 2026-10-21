"""Translate the pinned PageIndex Flash outline into Woobe source-bound nodes."""

from dataclasses import replace
import hashlib
import re
import unicodedata
from uuid import NAMESPACE_URL, uuid5

from modules.artifacts.domain.models import ArtifactError, DocumentIndex, DocumentNode
PAGEINDEX_FLASH_VERSION = '0.2.10+27f2842'
PAGEINDEX_FLASH_SOURCE = '27f284291724fbbbbe6976388bd53eed4ebe7fca'
MAX_NODES = 50_000
MAX_INDEX_NODES = 110_001
MAX_DEPTH = 64
PAGEINDEX_VERSION = PAGEINDEX_FLASH_VERSION
PAGEINDEX_MAX_BYTES = 52_428_800
PAGEINDEX_MAX_PAGES = 500
PAGEINDEX_MAX_TIMEOUT_SECONDS = 120


def _identity(index_id, identity):
    return str(uuid5(NAMESPACE_URL, f'woobe:pageindex-flash:{PAGEINDEX_VERSION}:{index_id}:{identity}'))


def _title(value):
    if not isinstance(value, str):
        raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex returned an invalid section title')
    value = unicodedata.normalize('NFKC', value.encode('utf-8', 'replace').decode('utf-8'))
    value = re.sub(r'\s+', ' ', value).strip()
    if not value:
        raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex returned an empty section title')
    return value[:512]


def _merge_ranges(intervals):
    ranges = []
    for low, high in sorted(intervals):
        if ranges and low <= ranges[-1][1]:
            ranges[-1] = (ranges[-1][0], max(ranges[-1][1], high))
        else:
            ranges.append((low, high))
    if len(ranges) > 1000:
        raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PageIndex source map exceeds its interval limit')
    return tuple(ranges)


def _append_node(nodes, node):
    if len(nodes) >= MAX_INDEX_NODES:
        raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PageIndex tree exceeds the persisted node limit')
    nodes.append(node)


def _matching_heading(document, title, page_index, claimed):
    expected = ' '.join(unicodedata.normalize('NFKC', title).casefold().split())
    candidates = []
    for ordinal, block in enumerate(document.blocks):
        if block.id in claimed:
            continue
        if block.locator.page_index != page_index:
            continue
        candidate = ' '.join(unicodedata.normalize('NFKC', (block.title or block.text).split('\n', 1)[0]).casefold().split())
        if candidate == expected:
            candidates.append((ordinal, block))
    return next((item for item in candidates if item[1].kind == 'heading'), candidates[0] if candidates else None)


def _outline_pages(structure, page_count):
    if not isinstance(structure, list):
        raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex returned an invalid outline')
    flattened = []
    stack = [(item, 1, None, ()) for item in reversed(structure)]
    while stack:
        item, depth, parent_key, path = stack.pop()
        if not isinstance(item, dict) or depth >= MAX_DEPTH or len(flattened) >= MAX_NODES:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PageIndex outline exceeds its structural limits')
        start, end = item.get('start_index'), item.get('end_index')
        if (type(start) is not int or type(end) is not int or not 1 <= start <= end <= page_count
                or 'title' not in item):
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex returned an out-of-range page interval')
        identity = path + (len(flattened),)
        flattened.append({'key': identity, 'parent': parent_key, 'depth': depth,
            'title': _title(item['title']), 'start_page': start - 1, 'end_page': end - 1})
        children = item.get('nodes', [])
        if not isinstance(children, list):
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex returned invalid section children')
        for child in reversed(children):
            stack.append((child, depth + 1, identity, identity))
    by_key = {item['key']: item for item in flattened}
    for item in flattened:
        parent = item['parent']
        if parent is not None:
            ancestor = by_key[parent]
            if item['start_page'] < ancestor['start_page'] or item['end_page'] > ancestor['end_page']:
                raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex child pages escape their parent section')
    return flattened


def build_pageindex_tree(document, index_id, representation_set_id, payload):
    """Map a bounded upstream outline onto the exact canonical revision."""
    if not isinstance(payload, dict) or payload.get('toc_source') not in {'detected', 'pages', 'unreadable'}:
        raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex returned an unsupported outline source')
    page_count = document.page_count if document.page_count is not None else len(document.pages)
    if type(page_count) is not int or page_count < 0:
        raise ArtifactError('PROCESSOR_UNAVAILABLE', 'Canonical document has no valid page count')
    root_id = _identity(index_id, 'root')
    total_blocks = len(document.blocks)
    root = DocumentNode(root_id, 'Documento', (), kind='root')
    nodes = [root]
    structure = payload.get('structure', [])
    if payload.get('toc_source') == 'unreadable' or not structure:
        raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex did not produce a navigable outline')
    node_ids = {(): root_id}
    node_depths = {root_id: 0}
    ranges = {root_id: []}
    section_specs = []
    if payload.get('toc_source') == 'pages':
        if (not document.pages or len(structure) != page_count or len(structure) > MAX_NODES):
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex page output differs from canonical physical pages')
        page_indexes = set()
        for ordinal, item in enumerate(structure):
            if not isinstance(item, dict):
                raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex returned an invalid page node')
            start, end = item.get('start_index'), item.get('end_index')
            if type(start) is not int or type(end) is not int or start != end or not 1 <= start <= page_count:
                raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex returned an out-of-range page node')
            page_index = start - 1
            if page_index in page_indexes:
                raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex repeated a physical page')
            page_indexes.add(page_index)
            identity = _identity(index_id, f'page:{page_index}')
            node_ids[(ordinal,)] = identity
            node_depths[identity] = 1
            _append_node(nodes, DocumentNode(identity, _title(item.get('title', f'Page {start}')), (), root_id,
                kind='page', ordinal=ordinal + 1, page_index=page_index, depth=1))
            ranges[identity] = []
            ranges[root_id].append((identity, None))
        if page_indexes != set(range(page_count)):
            raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex page output omitted a physical page')
        tree_kind = 'pages'
    else:
        flattened = _outline_pages(structure, page_count)
        tree_kind = 'headings'
        claimed = set()
        owner_by_block = {}
        heading_ordinals = {}
        for ordinal, item in enumerate(flattened, 1):
            parent_key = item['parent']
            parent_id = node_ids[parent_key] if parent_key is not None else root_id
            identity = item['key']
            node_id = _identity(index_id, 'section:' + '/'.join(map(str, identity)))
            node_ids[identity] = node_id
            node_depths[node_id] = item['depth']
            heading = _matching_heading(document, item['title'], item['start_page'], claimed)
            heading_id, block_hash = (), None
            if heading is not None:
                heading_ordinal, heading_block = heading
                claimed.add(heading_block.id)
                owner_by_block[heading_ordinal] = node_id
                heading_ordinals[node_id] = heading_ordinal
                heading_id = (heading_block.id,)
                block_hash = hashlib.sha256(heading_block.text.encode('utf-8')).hexdigest()
            _append_node(nodes, DocumentNode(node_id, item['title'], heading_id, parent_id,
                kind='section', ordinal=ordinal, block_sha256=block_hash,
                page_index=item['start_page'], depth=item['depth']))
            ranges[node_id] = []
            ranges.setdefault(parent_id, []).append((node_id, None))
            section_specs.append({**item, 'id': node_id})

        def parent_for_block(ordinal, page_index):
            if page_index is None:
                return root_id
            exact = owner_by_block.get(ordinal)
            if exact is not None:
                return exact
            candidates = [item for item in section_specs
                if item['start_page'] <= page_index <= item['end_page']]
            same_page = [item for item in candidates if item['start_page'] == page_index
                and item['id'] in heading_ordinals and heading_ordinals[item['id']] < ordinal]
            if same_page:
                return max(same_page, key=lambda item: (heading_ordinals[item['id']], item['depth']))['id']
            active = [item for item in candidates if item['start_page'] < page_index
                and item['id'] in heading_ordinals and heading_ordinals[item['id']] < ordinal]
            if active:
                return max(active, key=lambda item: (item['start_page'], item['depth'],
                    heading_ordinals[item['id']]))['id']
            unanchored = [item for item in candidates if item['id'] not in heading_ordinals]
            if unanchored:
                return max(unanchored, key=lambda item: (item['depth'], item['start_page']))['id']
            return root_id

        next_ordinal = len(section_specs) + 1
        for block_ordinal, block in enumerate(document.blocks):
            if block.id in claimed:
                ranges[owner_by_block[block_ordinal]].append((block_ordinal, block_ordinal + 1))
                continue
            parent_id = parent_for_block(block_ordinal, block.locator.page_index)
            identity = _identity(index_id, 'block:' + block.id)
            title = block.title or block.text.split('\n', 1)[0]
            title = _title(title) if title.strip() else f'Bloco {block_ordinal + 1}'
            depth = node_depths[parent_id] + 1
            if depth > MAX_DEPTH:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PageIndex source tree exceeds its depth limit')
            _append_node(nodes, DocumentNode(identity, title, (block.id,), parent_id, kind='block',
                ordinal=next_ordinal, source_ranges=((block_ordinal, block_ordinal + 1),),
                block_sha256=hashlib.sha256(block.text.encode('utf-8')).hexdigest(),
                page_index=block.locator.page_index, depth=depth))
            next_ordinal += 1
            ranges[identity] = [(block_ordinal, block_ordinal + 1)]
            ranges.setdefault(parent_id, []).append((identity, None))
    if tree_kind == 'pages':
        pages = {node.page_index: node.id for node in nodes if node.kind == 'page'}
        next_ordinal = len(pages) + 1
        for block_ordinal, block in enumerate(document.blocks):
            parent_id = pages.get(block.locator.page_index, root_id)
            identity = _identity(index_id, 'block:' + block.id)
            title = block.title or block.text.split('\n', 1)[0]
            title = _title(title) if title.strip() else f'Bloco {block_ordinal + 1}'
            _append_node(nodes, DocumentNode(identity, title, (block.id,), parent_id, kind='block',
                ordinal=next_ordinal, source_ranges=((block_ordinal, block_ordinal + 1),),
                block_sha256=hashlib.sha256(block.text.encode('utf-8')).hexdigest(),
                page_index=block.locator.page_index, depth=node_depths[parent_id] + 1))
            next_ordinal += 1
            ranges[identity] = [(block_ordinal, block_ordinal + 1)]
            ranges.setdefault(parent_id, []).append((identity, None))
    children = {node.id: [] for node in nodes}
    for node in nodes:
        if node.parent_id is not None:
            children[node.parent_id].append(node.id)
    computed = {}
    for node in sorted(nodes, key=lambda value: value.depth, reverse=True):
        intervals = [item for item in ranges.get(node.id, ()) if len(item) == 2 and all(type(i) is int for i in item)]
        for child_id in children[node.id]:
            intervals.extend(computed[child_id])
        computed[node.id] = _merge_ranges(intervals)
    expected_root = ((0, total_blocks),) if total_blocks else ()
    if computed[root_id] != expected_root:
        raise ArtifactError('PROCESSOR_UNAVAILABLE', 'PageIndex tree did not preserve every canonical source block')
    nodes = tuple(replace(node, source_ranges=computed[node.id]) for node in sorted(nodes, key=lambda value: value.ordinal))
    return DocumentIndex(index_id, representation_set_id, 'pageindex-flash', PAGEINDEX_VERSION,
        nodes, tree_kind=tree_kind, source_block_count=total_blocks, coverage=document.coverage)


def pageindex_outline(source_path, *, max_pages):
    """Run the attributed upstream layout algorithm; this function is child-only."""
    from shared.infra.vendor.pageindex_flash.main import extract_toc
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(str(source_path))
    try:
        if not 1 <= len(pdf) <= max_pages:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'PDF exceeds the selected PageIndex page limit')
    finally:
        pdf.close()
    return extract_toc(source_path, workers=1, use_embedded_toc=False)
