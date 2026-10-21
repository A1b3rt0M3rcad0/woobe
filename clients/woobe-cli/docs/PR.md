# Built-in offline Woobe CLI skill installation

Install coding-assistant instructions directly from the CLI:
`woobe skill install --agent codex` or `--agent claude`. The reviewed portable
payload is embedded in all six binaries, so installation needs no npm, Node.js,
network, login or `.woobe-config`. The canonical `woobe skills` group provides
install/status/uninstall/agents, project/user scope, legacy `.codex` and custom
roots. `--project-dir` selects a local directory; runtime `project skill` operations
and their existing singular aliases remain separate.

The optional `woobe-cli-skill` npm package supplies the same skill independently.
Both installers recognize the same version/source/hash receipt and preserve
unmanaged/edited files and unrelated agent settings. Preflight, locks, swaps and
rollback protect managed updates/removal, including concurrent edits. Neither
installer handles credentials or executes remote operations.

A small skill router, seven offline references and two YAML templates teach real
connection, Draft YAML editing, shared dependencies, package transfer, tests,
lifecycle, economical output and uncertain-write recovery. Native and npm payloads
come from one source tree; packaging excludes implementation Go source/tests.

Distribution binds both npm tarballs to the release version/source, with immutable
checksums and manifests. Existing CLI OIDC publishing is unchanged. The separate
skill npm publisher remains opt-in until its one-time owner bootstrap; built-in
installation does not depend on that publication.

Validation includes Go native installer/CLI regression and race tests, Python
artifact/publication tests, standalone Node tests and six-host native/npm smoke.
Actual packaged binaries test embedded installation, receipt interoperability and
all 38 fenced skill CLI examples offline. Documentation and the generated command
catalog cover the new workflow. No backend code, merge or publication is performed;
merge requires owner approval after green CI.
