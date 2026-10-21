# Connection and authority

```sh
woobe context create local --api-url http://localhost:8000
woobe context use local
woobe auth login --cli-key
woobe auth status --output compact
woobe context show --output compact
```

The user enters the CLI Key at the masked login prompt. Every connection stores
its own API URL/key/Project selection. The key discovers its Workspace and
eligible Projects; one eligible Project is selected automatically. With several,
select the intended Project interactively or with `woobe context project select`.
Do not require Workspace/Project UUID environment variables for normal setup.

Multiple Woobes use different named contexts. Explicit `--context NAME` overrides
the connection pinned in `.woobe-config`. A resource from one API/Workspace/Project
is not a binding in another. Changing an API requires authentication again.
Administrative CLI Keys and runtime credentials are separate. Keep protected
credentials in the CLI's private store, never in project YAML or skill files.

Use `woobe package doctor --output compact` for package compatibility evidence.
It is read-only. An authority/schema mismatch requires compatible backend/client
versions; reinstalling the CLI cannot fix an old server catalog.
