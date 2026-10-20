package cli

import (
	"github.com/spf13/cobra"
	"github.com/spf13/pflag"
	"strings"
)

func (a *App) aliasCommands() {
	for name, target := range map[string][]string{"agent": {"project", "agent"}, "network": {"project", "network"}, "provider": {"project", "provider-credential"}, "model": {"project", "provider-model"}, "tool": {"project", "tool"}, "skill": {"project", "skill"}, "knowledge": {"project", "knowledge"}, "surface": {"project", "surface"}, "control-key": {"workspace", "control-key"}} {
		name, target := name, target
		description := "Use agent/network REFERENCE pull|push|diff|status|validate for managed YAML development. REFERENCE accepts a native UUID, exact remote name for pull, registered @alias or local path. Quote @aliases in PowerShell. sync aliases pull and update aliases push when following a reference. Raw list/create/get/update/delete and release commands remain available. Run woobe help develop agent pull for focused discovery."
		if name == "skill" {
			description = "Install coding-assistant instructions offline with woobe skill install --agent codex or claude. Use status, uninstall or agents for local setup; use --project-dir for a local folder. Runtime Skills remain woobe skill list/create/get/update/delete (project skill operations). No npm, Node.js, connection or login is required for assistant setup."
		}
		a.Root.AddCommand(&cobra.Command{Use: name, Short: "Canonical operations and reference-first YAML development", Long: description, DisableFlagParsing: true, RunE: func(cmd *cobra.Command, args []string) error {
			if name == "skill" && (len(args) == 0 || len(args) == 1 && (args[0] == "--help" || args[0] == "-h")) {
				return cmd.Help()
			}
			child := New(a.In, a.Out, a.Err)
			// Persistent flags supplied before an alias belong to its parent.
			// Forward them so presentation and connection flags have one meaning.
			forwarded := []string{}
			a.Root.PersistentFlags().Visit(func(flag *pflag.Flag) {
				if flag.Name == "query" {
					for _, value := range a.Query {
						forwarded = append(forwarded, "--query", value)
					}
				} else if flag.Name == "fields" {
					forwarded = append(forwarded, "--fields="+strings.Join(a.OutputFields, ","))
				} else {
					forwarded = append(forwarded, "--"+flag.Name+"="+flag.Value.String())
				}
			})
			// Cobra passes leading persistent options through when an alias
			// disables flag parsing. Keep them before the routed command.
			prefix := 0
			for prefix < len(args) && strings.HasPrefix(args[prefix], "--") {
				name, value, equals := strings.Cut(strings.TrimPrefix(args[prefix], "--"), "=")
				flag := a.Root.PersistentFlags().Lookup(name)
				if flag == nil {
					break
				}
				_ = value
				prefix++
				if !equals && flag.NoOptDefVal == "" && prefix < len(args) {
					prefix++
				}
			}
			forwarded = append(forwarded, args[:prefix]...)
			args = args[prefix:]
			routed := append(append(forwarded, target...), args...)
			if name == "skill" && len(args) > 0 {
				switch args[0] {
				case "install", "status", "uninstall", "agents":
					routed = append(append(forwarded, "skills"), args...)
				}
			}
			if name == "agent" || name == "network" || name == "surface" {
				actions := map[string]string{"bindings": "bindings", "pull": "pull", "sync": "pull", "push": "push", "update": "push", "diff": "diff", "validate": "validate", "status": "status", "create": "create", "reconcile": "reconcile", "history": "history", "heads": "heads", "current": "current", "revision": "revision", "draft": "draft", "checkout": "checkout", "rebase": "rebase"}
				for _, action := range []string{"stage", "publish", "activate", "rollback"} {
					if name != "surface" {
						actions[action] = action
					}
					if name != "surface" {
						actions["candidate"] = "candidate"
						actions["evaluation"] = "evaluation"
						actions["publication"] = "publication"
						actions["receipt"] = "receipt"
						actions["git-proof"] = "git-proof"
						actions["git-attest"] = "git-attest"
						actions["lease"] = "lease"
						actions["deployment"] = "deployment"
						actions["deploy"] = "deploy"
						actions["test"] = "test"
					}
				}
				if name == "agent" {
					for _, action := range []string{"archive", "delete", "test"} {
						actions[action] = action
					}
				}
				if name == "surface" {
					delete(actions, "reconcile")
				}
				reserved := map[string]bool{"list": true, "get": true, "create": true, "update": true, "prompt": true, "contract": true, "model-config": true, "release": true, "environment": true, "draft": true, "promotion": true, "version": true, "management": true, "activation": true, "rollback": true, "session": true}
				if len(args) > 1 && actions[args[1]] != "" && !strings.HasPrefix(args[0], "-") && !reserved[args[0]] {
					routed = append(append(forwarded, "develop", name, actions[args[1]], args[0]), args[2:]...)
				} else if len(args) > 0 && actions[args[0]] != "" && args[0] != "update" && args[0] != "create" && !(name == "network" && args[0] == "rollback") {
					routed = append(append(forwarded, "develop", name, actions[args[0]]), args[1:]...)
				}
			}
			// Ref-first canonical reads and lifecycle commands retain all
			// remaining IDs/flags; raw command-first forms remain unchanged.
			if len(args) > 1 && !strings.HasPrefix(args[0], "-") && (strings.HasPrefix(args[0], "@") || strings.ContainsAny(args[0], "/\\") || uuidReference(args[0])) {
				if args[1] == "get" || args[1] == "usage" || (args[1] == "archive" && name != "agent") || args[1] == "disable" {
					routed = append(append(forwarded, target...), append([]string{args[1], args[0]}, args[2:]...)...)
				} else if len(args) > 2 && (args[1] == "release" || args[1] == "version" || args[1] == "environment" || args[1] == "activation" || args[1] == "prompt" || args[1] == "contract") {
					routed = append(append(forwarded, target...), append([]string{args[1], args[2], args[0]}, args[3:]...)...)
				}
			}
			child.Root.SetArgs(routed)
			err := child.Root.ExecuteContext(cmd.Context())
			a.Mode, a.OutputFields, a.OutputWide = child.Mode, child.OutputFields, child.OutputWide
			a.Workspace, a.Project, a.outputCommand = child.Workspace, child.Project, child.outputCommand
			return err
		}})
	}
}

func uuidReference(value string) bool {
	return len(value) == 36 && value[8] == '-' && value[13] == '-' && value[18] == '-' && value[23] == '-'
}
