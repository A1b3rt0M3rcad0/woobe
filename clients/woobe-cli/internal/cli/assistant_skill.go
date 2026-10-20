package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	assistantskill "github.com/A1b3rt0M3rcad0/woobe-cli/packages/woobe-cli-skill"
	"github.com/spf13/cobra"
)

func (a *App) assistantSkillCommands() {
	group := &cobra.Command{Use: "skills", Short: "Install the embedded Woobe CLI skill for coding assistants", Long: "Install portable assistant instructions locally, offline. No Node.js, npm, login or backend connection is required. Runtime Skills use project skill operations. Edited/unmanaged skills and agent settings are preserved."}
	a.Root.AddCommand(group)
	group.AddCommand(&cobra.Command{Use: "agents", Short: "List supported assistant skill destinations", Args: cobra.NoArgs, RunE: func(_ *cobra.Command, _ []string) error {
		rows := []map[string]string{}
		for _, name := range []string{"codex", "codex-legacy", "claude", "copilot", "cursor", "agents"} {
			layout := assistantskill.Presets[name]
			rows = append(rows, map[string]string{"agent": name, "project_root": layout.Project, "user_root": "~/" + layout.User})
		}
		return a.emit(rows)
	}})
	for _, action := range []string{"install", "status", "uninstall"} {
		o := assistantskill.Options{}
		command := &cobra.Command{Use: action, Short: action + " the local coding-assistant skill", Args: cobra.NoArgs, Example: "woobe skill " + action + " --agent codex,claude\nwoobe skills " + action + " --agent codex-legacy --scope user\nwoobe skills " + action + " --path ./custom/skills", RunE: func(cmd *cobra.Command, _ []string) error {
			if cmd.Flags().Changed("project") || cmd.Flags().Changed("project-config") || cmd.Flags().Changed("no-project-config") {
				return output.New(2, "assistant skill installation does not use Project IDs or .woobe-config; use --project-dir for a local project")
			}
			o.Version = Version
			o.Commit = Commit
			o.DryRun = a.DryRun
			result, err := assistantskill.Run(action, o)
			if err != nil {
				return output.New(2, err.Error())
			}
			return a.emit(result)
		}}
		command.Flags().StringSliceVar(&o.Agents, "agent", nil, "Assistant presets, comma-separated or repeatable (default codex)")
		command.Flags().StringVar(&o.Scope, "scope", "", "project or user (default project)")
		command.Flags().StringVar(&o.ProjectDir, "project-dir", "", "Existing local project directory (default current directory)")
		command.Flags().StringVar(&o.Path, "path", "", "Custom skills root; appends woobe-cli")
		group.AddCommand(command)
	}
}
