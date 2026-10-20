from dataclasses import replace
import hashlib

import pytest

from modules.artifacts.application.services.structural_index import build_structural_index, validate_source_membership
from modules.artifacts.domain.models import ArtifactRef, CanonicalDocument, Coverage, DocumentBlock, DocumentIndex, DocumentPage, Locator


def block(identity, text, *, heading=None, page=None, parent=None):
    coordinates = {'block_id': identity, 'char_start': 0, 'char_end': len(text), 'char_space': 'canonical_block_text'}
    if page is not None:
        coordinates.update(page_index=page, page_number=page + 1)
    return DocumentBlock(identity, 'heading' if heading else 'paragraph', text, Locator(**coordinates),
                         heading_level=heading, parent_id=parent)


def document(blocks, **kwargs):
    return CanonicalDocument(ArtifactRef('source', 'revision'), tuple(blocks),
        coverage=kwargs.pop('coverage', Coverage.COMPLETE), **kwargs)


def test_headings_repeated_titles_missing_levels_and_non_latin_have_stable_distinct_sources():
    source = document([block('intro', 'Prólogo.'), block('h1', '章一 😀', heading=1),
        block('body', 'Texto com ação.'), block('h3', 'Repetido', heading=3),
        block('long', '漢字 ação 😀\n' * 100_000), block('same', 'Repetido', heading=3),
        block('h2', 'Outra seção', heading=2)])
    tree = build_structural_index(source, 'index-1', 'generation')
    assert tree == build_structural_index(source, 'index-1', 'generation')
    assert tree.tree_kind == 'headings' and len(tree.nodes) == len(source.blocks) + 1
    by_block = {node.block_ids[0]: node for node in tree.nodes if node.block_ids}
    assert by_block['h3'].parent_id == by_block['h1'].id
    assert by_block['same'].parent_id == by_block['h1'].id
    assert by_block['same'].id != by_block['h3'].id
    assert by_block['long'].parent_id == by_block['h3'].id
    assert by_block['long'].source_ranges == ((4, 5),)
    assert by_block['long'].block_sha256 == hashlib.sha256(source.blocks[4].text.encode()).hexdigest()
    assert all(len(node.title) <= 512 for node in tree.nodes)
    assert by_block['h2'].parent_id == by_block['h1'].id
    assert by_block['h1'].source_ranges == ((1, 7),)
    assert all(not hasattr(node, 'text') for node in tree.nodes)
    newer = build_structural_index(source, 'index-2', 'generation')
    assert not ({node.id for node in tree.nodes} & {node.id for node in newer.nodes})
    validate_source_membership(tree, source)


def test_page_and_block_fallbacks_are_explicit_and_keep_discontinuous_source_ranges_exact():
    pages = tuple(DocumentPage(i, i + 1, str(i + 1), 600, 800, 3, 'text') for i in range(2))
    source = document([block('a', 'Um', page=0), block('b', 'Dois', page=1), block('c', 'Três', page=0)],
                      page_count=2, pages=pages)
    tree = build_structural_index(source, 'pages', 'generation')
    assert tree.tree_kind == 'pages'
    containers = {node.page_index: node for node in tree.nodes if node.kind == 'page'}
    assert containers[0].source_ranges == ((0, 1), (2, 3))
    assert containers[1].source_ranges == ((1, 2),)
    assert tree.nodes[0].source_ranges == ((0, 3),)
    plain = build_structural_index(document([block('p', 'Sem capítulos.')]), 'blocks', 'generation')
    assert plain.tree_kind == 'blocks' and len(plain.nodes) == 2
    assert plain.nodes[1].parent_id == plain.nodes[0].id


def test_canonical_forward_parents_are_preserved_without_inventing_fallback_cycles():
    source = document([block('child', 'Filha', heading=2, parent='later'), block('later', 'Mãe', heading=1)])
    tree = build_structural_index(source, 'canonical', 'generation')
    assert tree.tree_kind == 'canonical'
    child, parent = [node for node in tree.nodes if node.block_ids]
    assert child.parent_id == parent.id and parent.parent_id == tree.nodes[0].id
    assert parent.source_ranges == ((0, 2),)


def test_index_validation_rejects_cycles_ranges_wrong_checksums_and_unrepresented_blocks():
    source = document([block('a', 'A', heading=1), block('b', 'B')])
    tree = build_structural_index(source, 'index', 'generation')
    root, first, second = tree.nodes
    for nodes in [
        (root, replace(first, parent_id=second.id), replace(second, parent_id=first.id)),
        (root, replace(first, source_ranges=((0, 4),)), second),
        (root, first, replace(second, parent_id='foreign-index-node')),
    ]:
        with pytest.raises(ValueError):
            replace(tree, nodes=nodes)
    wrong = replace(tree, nodes=(root, first, replace(second, block_sha256='0' * 64)))
    with pytest.raises(ValueError, match='checksum'):
        validate_source_membership(wrong, source)
    with pytest.raises(ValueError, match='unrepresented'):
        validate_source_membership(replace(tree, nodes=(root, first)), source)
    with pytest.raises(ValueError):
        DocumentIndex('index', 'generation', 'structural', '1', (), coverage=Coverage.COMPLETE)


def test_empty_partial_tree_preserves_explicit_coverage_and_depth_is_bounded():
    source = document([], coverage=Coverage.NEEDS_OCR)
    tree = build_structural_index(source, 'empty', 'generation')
    assert tree.tree_kind == 'empty' and tree.coverage == Coverage.NEEDS_OCR
    assert len(tree.nodes) == 1 and tree.nodes[0].source_ranges == ()
    with pytest.raises(ValueError):
        replace(tree, coverage=Coverage.COMPLETE)
    blocks = [block('rootblock', 'A')]
    blocks.extend(block(f'b{i}', 'B', parent='rootblock' if i == 0 else f'b{i-1}') for i in range(65))
    from modules.artifacts.domain.models import ArtifactError
    with pytest.raises(ArtifactError, match='depth limit'):
        build_structural_index(document(blocks), 'too-deep', 'generation')


def test_empty_scanned_pdf_keeps_physical_page_navigation_without_invented_text():
    pages = tuple(DocumentPage(i, i + 1, label, 600, 800, 0, 'needs_ocr') for i, label in enumerate(('i', 'ii')))
    tree = build_structural_index(document([], coverage=Coverage.NEEDS_OCR, page_count=2, pages=pages), 'scan', 'generation')
    assert tree.tree_kind == 'pages' and len(tree.nodes) == 3
    assert tree.coverage == Coverage.NEEDS_OCR
    assert [node.page_index for node in tree.nodes if node.kind == 'page'] == [0, 1]
    assert all(not node.block_ids and not node.source_ranges for node in tree.nodes)
