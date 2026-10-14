#!/usr/bin/env python3
"""Index actual browser evidence; fail when a routed surface or overlay lacks captures."""
import hashlib
import html
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / 'docs/screenshots/v2'
FRONTEND = ROOT / 'packages/woobe-frontend/src'
PAGE_FOLDERS = {
    'LoginPage': 'sign-in', 'RegisterPage': 'register', 'NotFoundPage': 'not-found',
    'DashboardPage': 'overview', 'WorkspacesPage': 'workspaces',
    'WorkspaceDetailPage': 'workspace-settings', 'WorkspaceProjectsPage': 'workspace-projects',
    'WorkspaceProjectDetailPage': 'project-settings', 'SettingsPage': 'account-settings',
    'McpConnectCallbackPage': 'mcp-callback', 'ApiKeysPage': 'api-keys',
    'ChatSurfacesPage': 'chat-surfaces', 'AgentsPage': 'agents',
    'AgentPlaygroundPage': 'playground', 'NetworksPage': 'networks',
    'NetworkWorkspaceRoute': 'network-workspace', 'KnowledgePage': 'knowledge',
    'ToolsPage': 'tools', 'ModelsPage': 'models', 'ProjectEnvironmentsPage': 'environments',
    'SkillsPage': 'skills', 'CredentialsPage': 'credentials', 'UsagePage': 'usage',
    'TracesPage': 'traces',
}
PRIMITIVE_GROUPS = {
    'buttons': ['Button'], 'badges': ['Badge', 'Separator', 'TechnicalListItem'],
    'fields': ['Field', 'Input', 'InputGroup', 'Select', 'Textarea', 'Checkbox', 'ReadOnlyField', 'FormActions'],
    'panels': ['DotMeter', 'SectionBlock', 'PanelHeader', 'Card', 'MetricTile', 'OperationalResourceCard', 'CreateResourceCard'],
    'tables': ['PageHeader', 'ResourcePage', 'Tabs', 'Table', 'Stepper', 'SegmentedControl'],
    'feedback': ['Alert', 'Skeleton', 'LoadingState', 'EmptyStatePanel', 'GuidedEmptyState'],
    'code': ['CodePanel', 'JsonCodeBlock', 'CopyButton', 'JsonEditor', 'MathSurface'],
    'dates': ['WoobeDatePicker', 'WoobeDateTimePicker'], 'dropdown': ['Dropdown'],
    'resource-shell': ['ScrollArea'],
}


def relative(path):
    return str(path.relative_to(ROOT))


def natural_key(path):
    return [int(part) if part.isdigit() else part for part in re.split(r'(\d+)', str(path).removesuffix('.png'))]


def captures_in(folder):
    return [relative(path) for path in sorted((CAPTURES / folder).glob('*.png'), key=natural_key)]


def main():
    missing = []

    def require(folder, names):
        for name in names:
            if not (CAPTURES / folder / name).is_file():
                missing.append(f'{folder}/{name}')

    routes = []
    for path, component in re.findall(r'<Route path="([^"]+)" element=\{<(\w+)', (FRONTEND / 'app/router.tsx').read_text()):
        folder = PAGE_FOLDERS.get(component)
        if component == 'FirstRunSetupPage':
            folder = 'project-setup' if ':projectId' in path else 'workspace-setup'
        redirect = component.endswith('Redirect') or component == 'Navigate'
        if not folder and not redirect:
            raise SystemExit(f'Unclassified route: {path} ({component})')
        entry = {'path': path, 'component': component, 'kind': 'redirect' if redirect else 'rendered-page'}
        if folder:
            names = ['desktop.png', 'mobile.png'] if folder in ['sign-in', 'register', 'not-found'] else [f'{width}px.png' for width in [1440, 768, 390]]
            require(f'pages/{folder}', names)
            entry.update(folder=folder, screenshots=captures_in(f'pages/{folder}'))
        else:
            entry['verification'] = 'tests/e2e/tests/surface-coverage.spec.ts: compatibility routes'
        routes.append(entry)

    registry = (ROOT / 'tests/e2e/review/registry.tsx').read_text()
    overlays = json.loads((ROOT / 'tests/e2e/review/overlay-cases.json').read_text())
    hosts = [{'id': name, 'source': source} for name, source in re.findall(r"id:'(host-[^']+)',source:'([^']+)'", registry)]
    secondary = ['McpInputBindings', 'CollectionDeleteDocument', 'ConfigurationApproveUse', 'ConfigurationRevokeUse', 'OverviewRuntimeCostCoverage', 'SkillVersionReview', 'SkillChooseAgent', 'ConfigurationDiscardValue', 'ConfigurationDiscardBatch', 'AsacDiscardLocalEdits']
    for item in overlays + hosts:
        require(f'overlays/{item["id"]}', [f'{width}px.png' for width in [1440, 768, 390]])
        item['screenshots'] = captures_in(f'overlays/{item["id"]}')
    for name in secondary:
        require(f'overlays/{name}', [f'{width}px.png' for width in [1440, 768, 390]])

    page_owned = {
        'packages/woobe-frontend/src/features/asac/AsacWorkbench.tsx': captures_in('overlays/AsacDiscardLocalEdits'),
        'packages/woobe-frontend/src/layouts/DashboardLayout.tsx': ['docs/screenshots/v2/flows/project-switcher.png', 'docs/screenshots/v2/flows/mobile-navigation.png'],
        'packages/woobe-frontend/src/pages/ApiKeysPage.tsx': ['docs/screenshots/v2/flows/runtime-key-management.png', 'docs/screenshots/v2/flows/runtime-key-revoke.png', 'docs/screenshots/v2/flows/runtime-key-synthetic-secret.png'],
        'packages/woobe-frontend/src/pages/ChatSurfacesPage.tsx': ['docs/screenshots/v2/flows/create-chat-surface-1440.png', 'docs/screenshots/v2/flows/create-chat-surface-390.png'],
        'packages/woobe-frontend/src/pages/CredentialsPage.tsx': ['docs/screenshots/v2/flows/credential-details-1440.png', 'docs/screenshots/v2/flows/credential-revoke-1440.png', 'docs/screenshots/v2/flows/credential-archive-1440.png'],
        'packages/woobe-frontend/src/pages/NetworksPage.tsx': ['docs/screenshots/v2/flows/create-network-1440.png', 'docs/screenshots/v2/flows/create-network-390.png'],
        'packages/woobe-frontend/src/pages/SkillsPage.tsx': captures_in('overlays/SkillChooseAgent'),
        'packages/woobe-frontend/src/pages/DashboardPage.tsx': captures_in('overlays/OverviewRuntimeCostCoverage'),
    }
    covered_sources = {item['source'] for item in overlays + hosts} | set(page_owned)
    overlay_sources = []
    for path in sorted(FRONTEND.rglob('*.tsx')):
        if '.test.' in path.name:
            continue
        if re.search(r'<(Dialog|Drawer|DangerConfirmDialog|Dropdown)[^a-zA-Z]', path.read_text()):
            overlay_sources.append(relative(path))
            if relative(path) not in covered_sources:
                missing.append(f'Unclassified overlay source: {relative(path)}')
    for evidence in page_owned.values():
        for path in evidence:
            if not (ROOT / path).is_file():
                missing.append(path)

    primitives = []
    for path in sorted((ROOT / 'packages/woobe-ui/src/components').glob('*.tsx')):
        groups = [group for group, names in PRIMITIVE_GROUPS.items() if path.stem in names]
        evidence = [f'docs/screenshots/v2/components/{group}.png' for group in groups]
        if path.stem in ['Dialog', 'Drawer', 'DangerConfirmDialog']:
            evidence += captures_in(f'overlays/{path.stem}')
        if not evidence:
            missing.append(f'Primitive evidence: {relative(path)}')
        for group in groups:
            require('components', [f'{group}.png'])
        primitives.append({'source': relative(path), 'screenshots': evidence})

    sources = []
    for package in ['woobe-frontend', 'woobe-ui', 'woobe-embed']:
        sources += [relative(path) for path in sorted((ROOT / f'packages/{package}/src').rglob('*.tsx')) if '.test.' not in path.name]
    imported_pages = set(re.findall(r"from '@/pages/(\w+)'", (FRONTEND / 'app/router.tsx').read_text()))
    compatibility = [relative(path) for path in sorted((FRONTEND / 'pages').glob('*.tsx')) if '.test.' not in path.name and path.stem not in imported_pages and path.stem not in ['NetworkPage', 'ToolsCreateDialog']]

    images = []
    for path in sorted(CAPTURES.rglob('*.png'), key=natural_key):
        raw = path.read_bytes()
        width, height = struct.unpack('>II', raw[16:24])
        images.append({'path': relative(path), 'width': width, 'height': height, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    inventory = {
        'specification': 'guild-inspired-enterprise-ui v2.0; operational / comfortable',
        'evidence_note': 'Source inventory is exhaustive for TSX files; file reachability is not individual visual approval. Screenshots and browser tests use synthetic API data, not a live backend.',
        'routes': routes, 'shared_components': primitives, 'direct_overlays': overlays,
        'inline_overlay_hosts': hosts, 'secondary_overlays': secondary,
        'overlay_source_inventory': overlay_sources, 'page_owned_overlay_evidence': page_owned,
        'unrouted_page_modules': compatibility,
        'indirect_page_modules': {'packages/woobe-frontend/src/pages/NetworkPage.tsx': 'NetworkWorkspaceRoute', 'packages/woobe-frontend/src/pages/ToolsCreateDialog.tsx': 'ToolsPage / CreateToolModal'}, 'tsx_source_inventory': sources, 'screenshots': images,
    }
    (ROOT / 'docs/design/coverage.json').write_text(json.dumps(inventory, indent=2) + '\n')
    lines = ['# Guild v2 rendered evidence', '',
             'These are real Chromium captures of production components with synthetic API data. See [method and commands](../README.md), [visual contract](../../design/README.md) and [review results](../../design/REVIEW.md).', '',
             f'{len(images)} PNG captures. Desktop: 1440px; tablet: 768px; mobile: 390px. Public pages also include their full mobile document. Scroll sequences preserve the real viewport and scrolling behavior; read each folder in order. Section captures expose internal navigation; pan captures continue horizontal navigation.', '',
             'Open [the searchable gallery](index.html) through a static HTTP server for thumbnails, or follow the links below.', '',
             '## Pages', '', '| Route | Component | Evidence |', '| --- | --- | --- |']
    for route in routes:
        if 'folder' in route:
            lines.append(f'| `{route["path"]}` | {route["component"]} | [{route["folder"]}](pages/{route["folder"]}/) |')
    lines += ['', '## Shared component groups', '']
    lines += [f'- [{group}](components/{group}.png): {", ".join(names)}.' for group, names in PRIMITIVE_GROUPS.items()]
    lines += ['', 'Font probes: [capture](components/fonts.png), [actual rendered families and glyphs](fonts.json).', '',
              '## Open overlays', '', '| Production component / host | Evidence |', '| --- | --- |']
    lines += [f'| {item["id"]} | [{len(item["screenshots"])} captures](overlays/{item["id"]}/) |' for item in overlays + hosts]
    lines += [f'| {name} | [desktop, tablet, mobile](overlays/{name}/) |' for name in secondary]
    lines += ['', 'Additional flows: [creation and confirmations](flows/), [interactive and loading/error states](states/), [expanded JSON](overlays/JsonCodeBlock/), [open dropdown](overlays/Dropdown/).', '',
              'Unrouted compatibility modules are listed separately in [coverage.json](../../design/coverage.json); they are not counted as additional pages. Browser-native title hints retain native rendering. No custom tooltip implementation exists to capture independently.', '']
    (CAPTURES / 'README.md').write_text('\n'.join(lines))

    cards = []
    for item in images:
        src = item['path'].removeprefix('docs/screenshots/v2/')
        label = html.escape(src)
        cards.append(f'<article data-name="{label.lower()}"><a href="{label}"><img loading="lazy" src="{label}" alt="{label}"><span>{label}</span></a></article>')
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Woobe · Guild v2 evidence</title>
<style>body{margin:24px;background:#f8f7f5;color:#242321;font:14px/1.5 ui-monospace,monospace}header{max-width:900px}input{font:inherit;padding:12px;border:1px solid #8c867d;border-radius:6px;width:min(80%,600px)}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px;margin-top:24px}article{border:1px solid #e3e1dd;border-radius:10px;background:#fffefd;overflow:hidden}a{color:inherit}img{width:100%;height:220px;object-fit:contain;display:block}span{display:block;padding:12px;overflow-wrap:anywhere}article[hidden]{display:none}</style>
<header><h1>Woobe · Guild v2 evidence</h1><p>Actual browser captures, synthetic API fixtures. Click a thumbnail for the original image. Long overlays retain real scrolling: inspect initial, section and scroll captures together.</p><p><a href="README.md">Inventory</a> · <a href="../../design/REVIEW.md">Review and limitations</a></p><label for="query">Filter by page, component, state or width</label><br><input id="query" type="search" placeholder="e.g. 390px, StageDraft, credentials"><p id="count" role="status"></p></header><main>'''
    document += '\n'.join(cards) + '''</main><script>const input=document.querySelector('input'),cards=[...document.querySelectorAll('article')];function filter(){let count=0;for(const card of cards){card.hidden=!card.dataset.name.includes(input.value.toLowerCase());if(!card.hidden)count++}document.querySelector('#count').textContent=`${count} / ${cards.length} captures`}input.addEventListener('input',filter);filter()</script></html>'''
    (CAPTURES / 'index.html').write_text(document)
    print(f'{len(routes)} route declarations; {len(primitives)} shared modules; {len(overlays)} direct overlays; {len(hosts)} inline hosts; {len(images)} images')
    if missing:
        raise SystemExit('Missing evidence:\n' + '\n'.join(missing))


if __name__ == '__main__':
    main()
