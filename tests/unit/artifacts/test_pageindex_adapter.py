import asyncio
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from modules.artifacts.application.contracts.processing import (
    ComponentReference, ProcessingParameters, ProcessingRecipe,
)
from modules.artifacts.application.processing_registry import ComponentDescriptor, ProcessingRegistry
from modules.artifacts.domain.models import ArtifactError, ArtifactRef, CanonicalDocument, Coverage, DocumentBlock, DocumentPage, Locator
from modules.artifacts.infra.indexers.pageindex_adapter import (
    PAGEINDEX_FLASH_SOURCE, PAGEINDEX_FLASH_VERSION, build_pageindex_tree, pageindex_outline,
)
from modules.artifacts.infra.indexers.pageindex_runner import PageIndexRunner
from modules.artifacts.infra.processing.native_pdf import NativePdfProcessor
from modules.artifacts.infra.processing import native_registry
from tests.fixtures.artifacts.pdf_sources import pageindex_outline_pdf
from modules.artifacts.domain.models import Revision


def _block(identity, text, page, *, heading=False):
    return DocumentBlock(identity, 'heading' if heading else 'paragraph', text,
        Locator(block_id=identity, page_index=page, page_number=page + 1,
                char_start=0, char_end=len(text), char_space='canonical_block_text'),
        heading_level=1 if heading else None)


def _document():
    pages = tuple(DocumentPage(i, i + 1, str(i + 1), 612, 792, 100, 'text') for i in range(3))
    blocks = (_block('cover', 'Sample Technical Report', 0),
              _block('intro', '1 Introduction', 1, heading=True),
              _block('intro-body', 'The introduction describes the problem.', 1),
              _block('methods', '2 Methods', 2, heading=True),
              _block('data', '2.1 Data', 2, heading=True),
              _block('data-body', 'Measurements use a public sample.', 2))
    return CanonicalDocument(ArtifactRef('source', 'revision'), blocks, Coverage.COMPLETE,
        page_count=3, pages=pages)


def test_pageindex_outline_maps_inclusive_pages_to_canonical_blocks_and_stable_ids():
    payload = {'toc_source': 'detected', 'structure': [
        {'title': '1 Introduction', 'start_index': 2, 'end_index': 3, 'nodes': [
            {'title': '2.1 Data', 'start_index': 3, 'end_index': 3, 'nodes': []}]},
    ]}
    document = _document()
    tree = build_pageindex_tree(document, 'index-1', 'generation', payload)
    again = build_pageindex_tree(document, 'index-1', 'generation', payload)
    assert tree == again
    assert tree.engine == 'pageindex-flash' and tree.tree_kind == 'headings'
    assert tree.source_block_count == 6 and tree.coverage == Coverage.COMPLETE
    assert {block_id for node in tree.nodes for block_id in node.block_ids} == {
        block.id for block in document.blocks}
    assert len([block_id for node in tree.nodes for block_id in node.block_ids]) == len(document.blocks)
    by_title = {node.title: node for node in tree.nodes}
    assert by_title['Documento'].source_ranges == ((0, 6),)
    assert by_title['1 Introduction'].source_ranges == ((1, 6),)
    assert by_title['1 Introduction'].block_ids == ('intro',)
    assert by_title['1 Introduction'].page_index == 1
    assert by_title['2.1 Data'].source_ranges == ((4, 6),)
    assert by_title['2.1 Data'].block_ids == ('data',)
    assert by_title['2.1 Data'].page_index == 2


@pytest.mark.parametrize('start,end', [(0, 1), (2, 4), (3, 2), (True, 2)])
def test_pageindex_rejects_invalid_or_out_of_range_physical_pages(start, end):
    payload = {'toc_source': 'detected', 'structure': [{'title': 'Section', 'start_index': start, 'end_index': end}]}
    with pytest.raises(ArtifactError, match='PageIndex returned an out-of-range page interval'):
        build_pageindex_tree(_document(), 'index-1', 'generation', payload)


def test_pageindex_rejects_child_interval_outside_its_parent_and_empty_outline():
    source = _document()
    outside = {'toc_source': 'detected', 'structure': [
        {'title': 'Parent', 'start_index': 2, 'end_index': 2, 'nodes': [
            {'title': 'Child', 'start_index': 3, 'end_index': 3}]},
    ]}
    with pytest.raises(ArtifactError, match='escape their parent section'):
        build_pageindex_tree(source, 'index-1', 'generation', outside)
    empty = {'toc_source': 'unreadable', 'structure': []}
    with pytest.raises(ArtifactError, match='did not produce a navigable outline'):
        build_pageindex_tree(source, 'index-1', 'generation', empty)


def test_pageindex_page_only_tree_is_identified_and_preserves_physical_pages():
    payload = {'toc_source': 'pages', 'structure': [
        {'title': 'Page 1', 'start_index': 1, 'end_index': 1},
        {'title': 'Page 2', 'start_index': 2, 'end_index': 2},
        {'title': 'Page 3', 'start_index': 3, 'end_index': 3},
    ]}
    tree = build_pageindex_tree(_document(), 'index-1', 'generation', payload)
    assert tree.tree_kind == 'pages'
    pages = [node for node in tree.nodes if node.kind == 'page']
    assert [(node.page_index, node.source_ranges) for node in pages] == [
        (0, ((0, 1),)), (1, ((1, 3),)), (2, ((3, 6),))]


def test_vendored_pageindex_subset_matches_its_pinned_source_manifest():
    root = Path(__file__).resolve().parents[3]
    vendor = root / 'packages' / 'woobe-core' / 'src' / 'shared' / 'infra' / 'vendor' / 'pageindex_flash'
    manifest = json.loads((vendor / 'vendor-manifest.json').read_text(encoding='utf-8'))
    assert manifest['commit'] == PAGEINDEX_FLASH_SOURCE
    assert PAGEINDEX_FLASH_VERSION == manifest['version'] + '+' + manifest['commit'][:7]
    for item in manifest['files']:
        path = Path(item['path'])
        assert not path.is_absolute() and '..' not in path.parts
        data = (vendor / path).read_bytes()
        assert len(data) == item['size']
        assert hashlib.sha256(data).hexdigest() == item['sha256']
    assert (vendor / 'LICENSE').is_file() and (vendor / 'UPSTREAM.md').is_file()


def test_pinned_pageindex_flash_algorithm_builds_a_real_pdf_outline_without_sdk_clients(tmp_path):
    pdf = tmp_path / 'outline.pdf'
    pdf.write_bytes(pageindex_outline_pdf())
    result = pageindex_outline(pdf, max_pages=10)
    assert result['toc_source'] == 'detected'
    assert [(node['title'], node['start_index']) for node in result['structure']] == [
        ('1 Introduction', 2), ('2 Methods', 3)]
    methods = result['structure'][1]
    assert [node['title'] for node in methods['nodes']] == ['2.1 Data', '2.2 Review']


@pytest.mark.asyncio
async def test_pageindex_worker_runs_the_pinned_algorithm_in_an_owned_child(tmp_path):
    content = pageindex_outline_pdf()
    revision = Revision('revision', 'source', 'original.pdf', 'application/pdf', len(content),
        hashlib.sha256(content).hexdigest(), 'upload')
    recipe = ProcessingRecipe(mode='extract_index',
        processor=ComponentReference(name='native-pdf', version='1'),
        indexer=ComponentReference(name='pageindex-flash', version='0.2.10+27f2842'))

    async def stream():
        for offset in range(0, len(content), 1024):
            yield content[offset:offset + 1024]

    document_recipe = ProcessingRecipe(mode='extract', processor=recipe.processor)
    document = await NativePdfProcessor().process(revision, stream(), document_recipe)
    tree = await PageIndexRunner().index(document, index_id='index-child',
        representation_set_id='generation-child', profile=recipe, revision=revision, content=stream())
    assert tree.engine == 'pageindex-flash' and tree.tree_kind == 'headings'
    assert [(node.title, node.page_index) for node in tree.nodes if node.kind == 'section'] == [
        ('1 Introduction', 1), ('2 Methods', 2), ('2.1 Data', 2), ('2.2 Review', 2)]


@pytest.mark.asyncio
async def test_concurrent_pageindex_jobs_keep_scratch_and_index_identity_separate():
    content = pageindex_outline_pdf()
    revision = Revision('revision', 'source', 'original.pdf', 'application/pdf', len(content),
        hashlib.sha256(content).hexdigest(), 'upload')
    processor = NativePdfProcessor()
    document = await processor.process(revision, _content_stream(content),
        ProcessingRecipe(mode='extract', processor=ComponentReference(name='native-pdf', version='1')))
    recipe = ProcessingRecipe(mode='extract_index',
        processor=ComponentReference(name='native-pdf', version='1'),
        indexer=ComponentReference(name='pageindex-flash', version='0.2.10+27f2842'))
    runner = PageIndexRunner()
    left, right = await asyncio.gather(
        runner.index(document, index_id='concurrent-index-left', representation_set_id='generation',
            profile=recipe, revision=revision, content=_content_stream(content)),
        runner.index(document, index_id='concurrent-index-right', representation_set_id='generation',
            profile=recipe, revision=revision, content=_content_stream(content)))
    assert left.id != right.id
    assert [(node.title, node.page_index) for node in left.nodes if node.kind == 'section'] == [
        (node.title, node.page_index) for node in right.nodes if node.kind == 'section']


@pytest.mark.asyncio
async def test_cancelling_pageindex_kills_its_owned_child_process_group(tmp_path, monkeypatch):
    runner = PageIndexRunner()
    spawn = asyncio.create_subprocess_exec
    started = asyncio.Event()
    child = {}

    async def sleeper(*_args, **kwargs):
        child['process'] = await spawn(sys.executable, '-c', 'import time; time.sleep(30)', **kwargs)
        started.set()
        return child['process']

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', sleeper)
    operation = asyncio.create_task(runner._run_child(tmp_path, 30, 10))
    await asyncio.wait_for(started.wait(), timeout=5)
    operation.cancel()
    with pytest.raises(asyncio.CancelledError):
        await operation
    assert child['process'].returncode is not None


def test_pageindex_remains_optional_and_structural_fallback_is_explicit(monkeypatch):
    def missing(_name):
        from importlib.metadata import PackageNotFoundError
        raise PackageNotFoundError

    monkeypatch.setattr(native_registry, 'version', missing)
    descriptor = native_registry.pageindex_flash_descriptor()
    assert not descriptor.available and descriptor.diagnostic == 'pageindex_local_extra_not_installed'
    processor = ComponentDescriptor('native-pdf', '1', 'processor', 'original', 'canonical',
        frozenset({'application/pdf'}), available=True, diagnostic='')
    registry = ProcessingRegistry((processor, descriptor, native_registry.structural_index_descriptor()))
    recipe = ProcessingRecipe(mode='extract_index',
        processor=ComponentReference(name='native-pdf', version='1'),
        indexer=ComponentReference(name='pageindex-flash', version='0.2.10+27f2842'),
        parameters=ProcessingParameters(indexer_fallback='structural'))
    readiness = registry.readiness(recipe, content_type='application/pdf')
    assert readiness['ready']
    assert 'indexer:pageindex-flash:pageindex_local_extra_not_installed:structural_fallback' in readiness['diagnostics']


def test_core_startup_does_not_import_optional_pageindex_components(tmp_path):
    root = Path(__file__).resolve().parents[3]
    source = root / 'packages' / 'woobe-core' / 'src'
    guard = tmp_path / 'sitecustomize.py'
    guard.write_text("""import builtins
original = builtins.__import__
blocked = {'PyPDF2', 'regex', 'sortedcontainers'}
def guarded(name, *args, **kwargs):
    if name.split('.', 1)[0] in blocked or name.startswith('shared.infra.vendor.pageindex_flash'):
        raise ModuleNotFoundError('optional PageIndex package is absent')
    return original(name, *args, **kwargs)
builtins.__import__ = guarded
""", encoding='utf-8')
    program = ('import sys; import modules.artifacts.entrypoint; '
        "assert not any(name.startswith('shared.infra.vendor.pageindex_flash') for name in sys.modules)")
    result = subprocess.run([sys.executable, '-c', program], cwd=root,
        env={**os.environ, 'PYTHONPATH': os.pathsep.join((str(tmp_path), str(source)))},
        capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr


async def _content_stream(content):
    for offset in range(0, len(content), 1024):
        yield content[offset:offset + 1024]
