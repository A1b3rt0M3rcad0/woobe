#!/usr/bin/env python3
"""Inventory UI sources and the owner's reduced, current main-page capture set."""
import hashlib
import html
import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / 'docs/screenshots'
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
    'ArtifactsPage': 'artifacts',
}
PRIMITIVE_GROUPS = {
    'brand': ['WoobeLogo'],
    'buttons': ['Button'], 'badges': ['Badge', 'Separator', 'TechnicalListItem'],
    'fields': ['Field', 'Input', 'InputGroup', 'Select', 'Textarea', 'Checkbox', 'ReadOnlyField', 'FormActions'],
    'panels': ['DotMeter', 'ContributionBars', 'SectionBlock', 'PanelHeader', 'Card', 'MetricTile', 'OperationalResourceCard', 'CreateResourceCard'],
    'tables': ['PageHeader', 'ResourcePage', 'Tabs', 'Table', 'Stepper', 'SegmentedControl'],
    'feedback': ['Alert', 'Skeleton', 'LoadingState', 'EmptyStatePanel', 'GuidedEmptyState'],
    'code': ['CodePanel', 'JsonCodeBlock', 'CopyButton', 'JsonEditor', 'MathSurface'],
    'dates': ['WoobeDatePicker', 'WoobeDateTimePicker'], 'dropdown': ['Dropdown'],
    'resource-shell': ['ScrollArea'],
}



def relative(path):
    return str(path.relative_to(ROOT))


def main():
    pages = json.loads((ROOT / 'tests/e2e/fixtures/main-pages.json').read_text())
    main_pages = {page['surface']: page for page in pages}
    widths = {'desktop': 1440, 'tablet': 768, 'mobile': 390}
    expected = {f"{'' if view == 'desktop' else view + '/'}{page['slug']}.png": width
                for page in pages for view, width in widths.items()}
    expected.update({f'themes/{surface}-{theme}.png': 1440
                     for surface in ['agent-playground', 'network-workspace'] for theme in ['light', 'dark']})
    found = {str(path.relative_to(CAPTURES)): path for path in CAPTURES.rglob('*.png')}
    missing = sorted(set(expected) - set(found))
    extra = sorted(set(found) - set(expected))
    if missing or extra:
        raise SystemExit(f'Missing current main-page captures: {missing}\nUnexpected screenshots outside the selected main pages: {extra}')
    images = []
    for name, path in sorted(found.items()):
        raw = path.read_bytes()
        width, height = struct.unpack('>II', raw[16:24])
        if width != expected[name] or height != 1100:
            raise SystemExit(f'Unexpected viewport: {name}: {width}x{height}')
        images.append({'path': relative(path), 'width': width, 'height': height,
                       'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})

    routes = []
    for path, component in re.findall(r'<Route path="([^"]+)" element=\{<(\w+)', (FRONTEND / 'app/router.tsx').read_text()):
        surface = PAGE_FOLDERS.get(component)
        if component == 'FirstRunSetupPage':
            surface = 'project-setup' if ':projectId' in path else 'workspace-setup'
        redirect = component.endswith('Redirect') or component == 'Navigate'
        if not surface and not redirect:
            raise SystemExit(f'Unclassified route: {path} ({component})')
        entry = {'path': path, 'component': component, 'kind': 'redirect' if redirect else 'rendered-page',
                 'browser_test': 'tests/e2e/tests/surface-coverage.spec.ts'}
        if surface in main_pages:
            slug = main_pages[surface]['slug']
            entry['screenshots'] = [f"docs/screenshots/{'' if view == 'desktop' else view + '/'}{slug}.png" for view in widths]
        else:
            entry['screenshot_scope'] = 'Not selected: documentation intentionally retains only main pages.'
        routes.append(entry)

    registry = (ROOT / 'tests/e2e/review/registry.tsx').read_text()
    overlays = json.loads((ROOT / 'tests/e2e/review/overlay-cases.json').read_text())
    hosts = [{'id': name, 'source': source} for name, source in re.findall(r"id:'(host-[^']+)',source:'([^']+)'", registry)]
    page_owned = ['features/asac/AsacWorkbench.tsx', 'layouts/DashboardLayout.tsx',
                  *[f'pages/{name}.tsx' for name in ['ApiKeysPage', 'ChatSurfacesPage', 'CredentialsPage', 'NetworksPage', 'SkillsPage', 'DashboardPage']]]
    covered = {item['source'] for item in overlays + hosts} | {relative(FRONTEND / source) for source in page_owned}
    overlay_sources = []
    for path in sorted(FRONTEND.rglob('*.tsx')):
        if '.test.' not in path.name and re.search(r'<(Dialog|Drawer|DangerConfirmDialog|Dropdown)[^a-zA-Z]', path.read_text()):
            overlay_sources.append(relative(path))
            if relative(path) not in covered:
                raise SystemExit(f'Unclassified overlay source: {relative(path)}')
    primitives = []
    for path in sorted((ROOT / 'packages/woobe-ui/src/components').glob('*.tsx')):
        groups = [group for group, names in PRIMITIVE_GROUPS.items() if path.stem in names]
        if not groups and path.stem not in ['Dialog', 'Drawer', 'DangerConfirmDialog']:
            raise SystemExit(f'Unclassified primitive: {relative(path)}')
        primitives.append({'source': relative(path), 'review_groups': groups,
                           'browser_test': 'tests/e2e/review/gallery.spec.ts',
                           'screenshot_scope': 'Tested without committed component/overlay screenshots.'})
    sources = [path for package in ['woobe-frontend', 'woobe-ui', 'woobe-embed']
               for path in sorted((ROOT / f'packages/{package}/src').rglob('*.tsx')) if '.test.' not in path.name]
    typography = [{'source': relative(path), **{f'explicit_{family}_uses': path.read_text().count(f'font-{family}')
                   for family in ['sans', 'mono', 'serif']}} for path in sources]
    imported = set(re.findall(r"from '@/pages/(\w+)'", (FRONTEND / 'app/router.tsx').read_text()))
    compatibility = [relative(path) for path in sorted((FRONTEND / 'pages').glob('*.tsx'))
                     if '.test.' not in path.name and path.stem not in imported and path.stem not in ['NetworkPage', 'ToolsCreateDialog']]
    inventory = {
        'specification': 'guild-inspired-enterprise-ui v2.0 with owner-required editorial / interface / technical typography',
        'evidence_note': 'Only current main-page screenshots are committed, as requested. Source inventory, browser tests and visual review are distinct; fixtures are synthetic.',
        'main_pages': pages, 'routes': routes, 'shared_components': primitives,
        'direct_overlays': overlays, 'inline_overlay_hosts': hosts, 'overlay_source_inventory': overlay_sources,
        'page_owned_overlays': [relative(FRONTEND / source) for source in page_owned],
        'overlay_browser_tests': ['tests/e2e/review/gallery.spec.ts', 'tests/e2e/review/inline-overlays.spec.ts', 'tests/e2e/review/page-overlays.spec.ts', 'tests/e2e/tests/overlay-flows.spec.ts'],
        'unrouted_page_modules': compatibility, 'tsx_source_inventory': [relative(path) for path in sources],
        'typography_source_inventory': typography, 'screenshots': images,
    }
    (ROOT / 'docs/design/coverage.json').write_text(json.dumps(inventory, indent=2) + '\n')
    hashes = {item['path'].removeprefix('docs/screenshots/'): item['sha256'][:12] for item in images}
    def image_url(name):
        return f'{name}?v={hashes[name]}'
    lines = ['# Woobe main pages', '',
             'Updated Chromium captures of the production application, using synthetic API fixtures. Main pages are retained, with four comparable light/dark workspace captures requested for the theme refinement. Component and modal screenshots stay outside documentation.', '',
             f"![Project Overview]({image_url('project-overview.png')})", '',
             f"{len(pages)} main pages × 3 widths + 4 theme comparisons = {len(images)} images. Desktop 1440 × 1100, tablet 768 × 1100, mobile 390 × 1100.", '',
             '| Page | Desktop | Tablet | Mobile |', '| --- | --- | --- | --- |']
    for page in pages:
        slug = page['slug']
        lines.append(f"| {page['title']} | [View]({image_url(slug + '.png')}) | [View]({image_url('tablet/' + slug + '.png')}) | [View]({image_url('mobile/' + slug + '.png')}) |")
    lines += ['', '## Workspace theme comparisons', '',
              '| Workspace | Light | Dark |', '| --- | --- | --- |',
              f"| Agent Playground, expanded Run and context bars | [View]({image_url('themes/agent-playground-light.png')}) | [View]({image_url('themes/agent-playground-dark.png')}) |",
              f"| Network workspace | [View]({image_url('themes/network-workspace-light.png')}) | [View]({image_url('themes/network-workspace-dark.png')}) |",
              '', '## Reproduce', '',
              'Install the locked dependencies in `packages/woobe-frontend`, `packages/woobe-embed` and `tests/e2e`. Install Playwright Chromium and the local Georgia family as described in [font provenance](../design/FONTS.md). From `tests/e2e`:', '',
              '```sh', 'WOOBE_CAPTURE_DOCS=1 WOOBE_REQUIRE_GEORGIA=1 npx playwright test --config playwright.config.ts tests/surface-coverage.spec.ts tests/typography.spec.ts', 'WOOBE_CAPTURE_REFINEMENT=1 npx playwright test --config playwright.config.ts tests/workspace-refinement.spec.ts', 'cd ../..', 'python3 scripts/frontend_visual_inventory.py', '```', '',
              'In this cloud environment, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium` and `PLAYWRIGHT_BROWSERS_PATH=/workspace/.playwright`. The suite builds the real frontend and independent embed before capture. Public and product pages use their actual routers. Images show the initial viewport; long operational content remains scrollable in the application.', '',
              'The [gallery](index.html) provides thumbnails. [Source inventory and image hashes](../design/coverage.json), [rendered font evidence](../design/fonts/) and [review results](../design/REVIEW.md) record separate checks. Fixtures do not prove live backend or provider integration. Georgia is installed locally for these captures; other clients follow the declared serif fallback stack.', '',
              'Component/overlay browser tests remain enabled. Optional auxiliary captures use `WOOBE_CAPTURE_AUXILIARY=1` and stay in ignored test output, outside this documentation.', '']
    (CAPTURES / 'README.md').write_text('\n'.join(lines))
    cards = []
    for item in images:
        name = item['path'].removeprefix('docs/screenshots/')
        src = html.escape(image_url(name))
        label = html.escape(name)
        cards.append(f'<article data-name="{label}"><a href="{src}"><img loading="lazy" src="{src}" alt="{label}"><span>{label}</span></a></article>')
    document = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Woobe main pages</title>
<style>body{margin:24px;background:#f8f7f5;color:#242321;font:14px/1.5 system-ui,sans-serif}input{font:inherit;padding:10px;border:1px solid #8c867d;border-radius:6px}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px;margin-top:24px}article{border:1px solid #e3e1dd;border-radius:10px;background:#fffefd;overflow:hidden}a{color:inherit}img{width:100%;height:220px;object-fit:contain;display:block}span{display:block;padding:12px}article[hidden]{display:none}h1{font:400 36px/1.1 Georgia,serif}</style>
<header><h1>Woobe main pages</h1><p>Current production-browser captures with synthetic fixtures. <a href="README.md">Method and index</a></p><label for="query">Filter pages or viewport</label><br><input id="query" type="search" placeholder="e.g. overview, mobile"><p id="count" role="status"></p></header><main>'''
    document += '\n'.join(cards) + '''</main><script>const input=document.querySelector('input'),cards=[...document.querySelectorAll('article')];function filter(){let count=0;for(const card of cards){card.hidden=!card.dataset.name.includes(input.value.toLowerCase());if(!card.hidden)count++}document.querySelector('#count').textContent=`${count} / ${cards.length} captures`}input.addEventListener('input',filter);filter()</script></html>'''
    (CAPTURES / 'index.html').write_text(document)
    print(f'{len(routes)} route declarations; {len(primitives)} shared modules; {len(overlay_sources)} classified overlay sources; {len(pages)} main pages; {len(images)} current images')


if __name__ == '__main__':
    main()
