# Woobe main pages

Updated Chromium captures of the production application, using synthetic API fixtures. Main pages are retained, with four comparable light/dark workspace captures requested for the theme refinement. Component and modal screenshots stay outside documentation.

![Project Overview](project-overview.png?v=9e4f9e58d47f)

18 main pages × 3 widths + 4 theme comparisons = 58 images. Desktop 1440 × 1100, tablet 768 × 1100, mobile 390 × 1100.

| Page | Desktop | Tablet | Mobile |
| --- | --- | --- | --- |
| Sign in | [View](sign-in.png?v=ed8a2faf0768) | [View](tablet/sign-in.png?v=20ee1767acec) | [View](mobile/sign-in.png?v=643d373d59de) |
| Workspaces | [View](workspaces.png?v=30f4c22f6b31) | [View](tablet/workspaces.png?v=f169b046b0c8) | [View](mobile/workspaces.png?v=5f08dcc071a4) |
| Projects | [View](projects.png?v=b80a0a64d4a3) | [View](tablet/projects.png?v=89200bae6f12) | [View](mobile/projects.png?v=fb0016cd25e2) |
| Project Overview | [View](project-overview.png?v=9e4f9e58d47f) | [View](tablet/project-overview.png?v=43c8ff56241c) | [View](mobile/project-overview.png?v=8032a4cd9389) |
| Agents | [View](agents.png?v=39f0170ad388) | [View](tablet/agents.png?v=4f6d5ff1cd91) | [View](mobile/agents.png?v=ea1e87fb55a5) |
| Networks | [View](networks.png?v=b9ffa3504ce3) | [View](tablet/networks.png?v=161e1cd1c1c4) | [View](mobile/networks.png?v=5dd8355e061d) |
| Agent playground | [View](agent-playground.png?v=d7d26b50ddb2) | [View](tablet/agent-playground.png?v=d7e97abe0ae1) | [View](mobile/agent-playground.png?v=4bd03c9c9c0b) |
| Network workspace | [View](network-workspace.png?v=b8d2eed6c980) | [View](tablet/network-workspace.png?v=c6dbf5d623fb) | [View](mobile/network-workspace.png?v=f5b4c067f97e) |
| Knowledge | [View](knowledge.png?v=daba3aaf12f4) | [View](tablet/knowledge.png?v=36cc258e0eed) | [View](mobile/knowledge.png?v=f5c4c866d09e) |
| Tools | [View](tools.png?v=6c0b4b3d4b0f) | [View](tablet/tools.png?v=eab115083330) | [View](mobile/tools.png?v=a3d4bbeae415) |
| Skills | [View](skills.png?v=450d8c8b6dd8) | [View](tablet/skills.png?v=6b9c045ed565) | [View](mobile/skills.png?v=b02a69f4813c) |
| Models | [View](models.png?v=1ad415b9db6f) | [View](tablet/models.png?v=610fc887f272) | [View](mobile/models.png?v=48d8a127aa09) |
| Credentials | [View](credentials.png?v=7b781a206e61) | [View](tablet/credentials.png?v=d6506ce26f2b) | [View](mobile/credentials.png?v=ff3b5a0fa467) |
| Environments | [View](environments.png?v=874c54d11424) | [View](tablet/environments.png?v=4e920c87f7f9) | [View](mobile/environments.png?v=a7b426cd850a) |
| API Keys | [View](api-keys.png?v=2c28589d5bb1) | [View](tablet/api-keys.png?v=0d12cdf86792) | [View](mobile/api-keys.png?v=1b7e3b291b04) |
| ChatSurfaces | [View](chat-surfaces.png?v=439e056cfb20) | [View](tablet/chat-surfaces.png?v=7384ac2ef77e) | [View](mobile/chat-surfaces.png?v=4f3ec855df81) |
| Usage | [View](usage.png?v=0544a37b7f00) | [View](tablet/usage.png?v=b23fccf06c10) | [View](mobile/usage.png?v=5206976520dd) |
| Runs | [View](traces.png?v=25b1f8f15abd) | [View](tablet/traces.png?v=e616e80e8475) | [View](mobile/traces.png?v=179bc96eb0bf) |

## Workspace theme comparisons

| Workspace | Light | Dark |
| --- | --- | --- |
| Agent Playground, expanded Run and context bars | [View](themes/agent-playground-light.png?v=4f6dc18701c2) | [View](themes/agent-playground-dark.png?v=1b2ee224d79d) |
| Network workspace | [View](themes/network-workspace-light.png?v=d5a9bc56906b) | [View](themes/network-workspace-dark.png?v=8f2cd80ad99c) |

## Reproduce

Install the locked dependencies in `packages/woobe-frontend`, `packages/woobe-embed` and `tests/e2e`. Install Playwright Chromium and the local Georgia family as described in [font provenance](../design/FONTS.md). From `tests/e2e`:

```sh
WOOBE_CAPTURE_DOCS=1 WOOBE_REQUIRE_GEORGIA=1 npx playwright test --config playwright.config.ts tests/surface-coverage.spec.ts tests/typography.spec.ts
WOOBE_CAPTURE_REFINEMENT=1 npx playwright test --config playwright.config.ts tests/workspace-refinement.spec.ts
cd ../..
python3 scripts/frontend_visual_inventory.py
```

In this cloud environment, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE=/usr/bin/chromium` and `PLAYWRIGHT_BROWSERS_PATH=/workspace/.playwright`. The suite builds the real frontend and independent embed before capture. Public and product pages use their actual routers. Images show the initial viewport; long operational content remains scrollable in the application.

The [gallery](index.html) provides thumbnails. [Source inventory and image hashes](../design/coverage.json), [rendered font evidence](../design/fonts/) and [review results](../design/REVIEW.md) record separate checks. Fixtures do not prove live backend or provider integration. Georgia is installed locally for these captures; other clients follow the declared serif fallback stack.

Component/overlay browser tests remain enabled. Optional auxiliary captures use `WOOBE_CAPTURE_AUXILIARY=1` and stay in ignored test output, outside this documentation.
