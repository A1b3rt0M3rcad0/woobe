# Project and assistant setup

Use this reference only when asked to prepare or update project tooling. Check
`woobe init --help` for `--agents`; older CLI releases may lack integrated setup.
Run from the actual project/registry root. Choose the requested host:

```sh
woobe init --agents codex --dry-run
woobe init --agents codex
woobe init --agents codex-legacy
woobe init --agents claude
woobe init --agents codex,claude --root .woobe
```

These are alternatives, not steps to install every host. Codex uses
`.agents/skills`, codex-legacy `.codex/skills`, Claude `.claude/skills`.
Copilot, Cursor and generic `agents` presets are also supported.

Init creates/reuses `.woobe-config`, protects the configured root's `.state/`,
creates private `.woobe-lab/` scratch space and adds Git exclusions. With
`--agents`, it installs embedded skills, adds a managed `AGENTS.md` block and,
for Claude, a `CLAUDE.md` pointer. Copilot also gets a project instruction pointer.
The skill is a router; read only task-relevant references, not the entire payload.

It is offline and requires no key. New registries use the selected saved
connection if present; otherwise connect separately using [connection](connection.md).
Existing configs keep their exact identity, resources, root and connection.
Repeating init is supported; adding a preset preserves previous presets.
Never delete `.woobe-config` or `.state/` to reinstall assistant tooling.

Keep author YAML, registry and reviewed assistant instructions versioned.
Keep `.woobe-lab/`, operational state and credentials out of Git. Ignore rules
cannot untrack already committed files. Custom rules outside managed blocks are
preserved; locally edited blocks/skills stop updates. Put custom prose outside
the markers. No remote resource is created or promoted by init.

Dry-run makes no files. Normal setup preflights conflicts but is not a single
filesystem transaction; after an I/O error, review and rerun without discarding
state. Remove a stale `.woobe-init.lock` only after confirming no init is running.
Standalone `woobe skill install --agent codex` installs only the skill; it does
not create registry, instructions or lab. Uninstall does not remove those files.
