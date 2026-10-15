# Woobe main pages

Updated Chromium captures of the production application, using synthetic API fixtures. Main pages are retained, with four comparable light/dark workspace captures requested for the theme refinement. Component and modal screenshots stay outside documentation.

![Project Overview](project-overview.png?v=aa9f3e03a607)

19 main pages × 3 widths + 4 theme comparisons = 61 images. Desktop 1440 × 1100, tablet 768 × 1100, mobile 390 × 1100.

| Page | Desktop | Tablet | Mobile |
| --- | --- | --- | --- |
| Sign in | [View](sign-in.png?v=fa38dc88988b) | [View](tablet/sign-in.png?v=d0b364f36dd6) | [View](mobile/sign-in.png?v=905bb2c8a867) |
| Workspaces | [View](workspaces.png?v=ddc33c63b125) | [View](tablet/workspaces.png?v=79b787a4e276) | [View](mobile/workspaces.png?v=232221f4fe8f) |
| Projects | [View](projects.png?v=b807f79ba212) | [View](tablet/projects.png?v=331d4dd64ad6) | [View](mobile/projects.png?v=301c0da5e26f) |
| Project Overview | [View](project-overview.png?v=aa9f3e03a607) | [View](tablet/project-overview.png?v=a4fb77de6103) | [View](mobile/project-overview.png?v=0677341f61f1) |
| First Agent setup | [View](first-agent-setup.png?v=069f7deee20c) | [View](tablet/first-agent-setup.png?v=35dfe8771ee2) | [View](mobile/first-agent-setup.png?v=e8dfc3d7929d) |
| Agents | [View](agents.png?v=a06dfdf7d098) | [View](tablet/agents.png?v=9b60c6a1a875) | [View](mobile/agents.png?v=862193be80cd) |
| Networks | [View](networks.png?v=d44afc6de8db) | [View](tablet/networks.png?v=af73554d015e) | [View](mobile/networks.png?v=8f04530655c4) |
| Agent playground | [View](agent-playground.png?v=c310a6314d82) | [View](tablet/agent-playground.png?v=cbd4bbdabaed) | [View](mobile/agent-playground.png?v=ff5316ba276d) |
| Network workspace | [View](network-workspace.png?v=07457ce490a4) | [View](tablet/network-workspace.png?v=e59e9174c1d4) | [View](mobile/network-workspace.png?v=d637faa67d61) |
| Knowledge | [View](knowledge.png?v=4fef7f560493) | [View](tablet/knowledge.png?v=93df4ab9d0d9) | [View](mobile/knowledge.png?v=ad2470157184) |
| Tools | [View](tools.png?v=a8a0aa6f4d96) | [View](tablet/tools.png?v=0a8b1e50c2e9) | [View](mobile/tools.png?v=2f7391777079) |
| Skills | [View](skills.png?v=113e459da459) | [View](tablet/skills.png?v=fc212db3ed89) | [View](mobile/skills.png?v=015faef38258) |
| Models | [View](models.png?v=c50b71443d07) | [View](tablet/models.png?v=be8103eb693a) | [View](mobile/models.png?v=08584b3bea21) |
| Credentials | [View](credentials.png?v=e85a354b93cb) | [View](tablet/credentials.png?v=2d79f83d0685) | [View](mobile/credentials.png?v=c3b630640057) |
| Environments | [View](environments.png?v=4777be01c846) | [View](tablet/environments.png?v=363e8cbcf394) | [View](mobile/environments.png?v=699c68274859) |
| API Keys | [View](api-keys.png?v=f6d035cde202) | [View](tablet/api-keys.png?v=2db356b411ce) | [View](mobile/api-keys.png?v=97c6cb3468a3) |
| ChatSurfaces | [View](chat-surfaces.png?v=72caea7ff66c) | [View](tablet/chat-surfaces.png?v=32af9c67fc7c) | [View](mobile/chat-surfaces.png?v=f4a34d20f553) |
| Usage | [View](usage.png?v=d2a2005516b3) | [View](tablet/usage.png?v=b06b5bce45a7) | [View](mobile/usage.png?v=1dd5be96434b) |
| Runs | [View](traces.png?v=370c7fdbdf64) | [View](tablet/traces.png?v=b40675910aaa) | [View](mobile/traces.png?v=c1983135063d) |

## Workspace theme comparisons

| Workspace | Light | Dark |
| --- | --- | --- |
| Agent Playground, expanded Run and context bars | [View](themes/agent-playground-light.png?v=c21a9c11f11d) | [View](themes/agent-playground-dark.png?v=41c5d4ea6544) |
| Network workspace | [View](themes/network-workspace-light.png?v=7f89e8cf39c4) | [View](themes/network-workspace-dark.png?v=c50982ab0869) |

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
