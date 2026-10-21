# Prepare a project for Woobe and coding assistants

From the project root, choose the host you use:

```sh
woobe init --agents codex
woobe init --agents codex-legacy
woobe init --agents claude
```

Each command initializes local YAML development, installs the embedded skill and
adds concise assistant instructions. Run only the command for your host, or
select several with `woobe init --agents codex,claude`. Repeated `--agents` flags
also work. This feature requires a CLI whose `woobe init --help` lists `--agents`;
PR artifacts do not mean it is already published in npm `latest`.

No backend, login, Node.js or additional package is needed. This prepares local
files; it does not create a remote Woobe instance, Project or Agent. If a saved
connection is current, a new registry records it. Otherwise it starts without a
connection. Remote operations still require a configured connection and CLI Key;
see [installation and authentication](INSTALLATION.md).

## Files created and maintained

With `--agents codex,claude` and the default artifact root:

```text
my-project/
├── .woobe-config                    # versioned registry identity and resources
├── .gitignore                       # managed private-state/lab exclusions
├── AGENTS.md                        # compact router and development rules
├── CLAUDE.md                        # pointer to AGENTS.md and Claude skill
├── .agents/skills/woobe-cli/         # Codex skill and offline references
├── .claude/skills/woobe-cli/         # Claude skill and offline references
├── .woobe/
│   ├── .gitignore                   # private .state exclusion
│   └── .state/                      # private local operational state
└── .woobe-lab/                      # private, ignored scratch directory
```

Artifact folders such as `agents/`, `networks/`, `providers/` and `models/` are
created by development operations, not populated with placeholder resources by
`init`. Author YAML and `.woobe-config` stay available for version control.
Review and commit the assistant instructions and skills as project tooling.
Existing broader user ignore rules remain in force. Adding ignore rules does
not untrack files already committed to Git; review those separately.

| Preset | Skill location | Instruction entry point |
| --- | --- | --- |
| `codex`, `agents` | `.agents/skills/woobe-cli` | `AGENTS.md` |
| `codex-legacy` | `.codex/skills/woobe-cli` | `AGENTS.md` |
| `claude` | `.claude/skills/woobe-cli` | `CLAUDE.md` → `AGENTS.md` |
| `copilot` | `.github/skills/woobe-cli` | `.github/copilot-instructions.md` → `AGENTS.md` |
| `cursor` | `.cursor/skills/woobe-cli` | `AGENTS.md` |

The instruction block points to the canonical installed skill and asks the
assistant to read only the reference relevant to its task. It covers connection
inspection, shared resource identity, YAML editing, Draft synchronization,
compact output and recovery. It grants no deployment/publication authorization.
Reload the assistant if it has already indexed project instructions.

## Preview, customize and repeat

```sh
woobe init --agents codex,claude --dry-run
woobe init --agents codex --root ./definitions --context local
woobe init --agents claude
```

`local` must already be a saved connection when explicitly selected. `--dry-run`
checks paths, existing instructions and skills without creating files, directories
or a lock; `--output json` includes planned file actions. Normal output displays
the registry path, root, assistants, instruction files and lab directory.

Repeating `init` preserves existing registry bytes, UUID, resource mappings,
context, author files and private state. `--root` defaults to the existing root
when omitted. Explicitly changing an existing root or context is rejected;
`init` is not a migration command. Run it at the registry root, not inside a
nested resource folder. A configured external artifact root retains its own
`.gitignore` excluding `.state/`; the lab and instructions stay at project root.

Assistant choices are additive: adding Claude after Codex keeps both skills and
links. With `--agents`, previously recorded presets are also checked and updated
from the running binary. Without `--agents`, `init` maintains registry/ignore/lab
setup without changing assistant instructions or installing skills.

Managed blocks have integrity markers. Custom prose before/after them is
preserved, including existing CRLF line endings. Put your own instructions
outside the markers. Modified managed blocks or skills cause an explanatory
error instead of being overwritten. Back up edits and deliberately restore the
managed content before retrying. Linked destinations, invalid files and known
conflicts are rejected during preflight. Skills installed by the optional npm
installer remain interoperable with the native installer.

Setup uses an exclusive `.woobe-init.lock` and checks file drift before writes.
It is not one filesystem transaction: an I/O failure can leave completed parts
in place. Review the error and rerun the same command after fixing the cause;
do not delete the registry or `.state/`. If the process was killed, remove a
stale lock only after confirming no other initialization is running.

For skill-only installation, custom destinations, user scope or uninstall,
continue using `woobe skill install/status/uninstall` or the optional npm
installer; see [assistant skills](AGENT_SKILL.md). Those standalone commands do
not manage project instructions, registry or lab. Uninstalling a skill also does
not remove its project instruction links: review/remove the corresponding managed
instruction blocks deliberately if retiring this integration.
