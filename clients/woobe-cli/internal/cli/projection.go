package cli

import (
	"context"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"strings"
)

func (a *App) exportProjection(ctx context.Context, command string, args []string, destination string) error {
	op, ok := a.operation(command)
	if !ok || op.Kind != "http" || op.Method != "GET" || !strings.HasSuffix(command, " get") {
		return output.New(2, "export requires a canonical resource get operation")
	}
	if op.Status == "proposed" {
		if e := a.requireAdvertised(ctx, op); e != nil {
			return e
		}
	}
	v, meta, e := a.readResource(ctx, op, args)
	if e != nil {
		return e
	}
	projection := map[string]any{"schema_version": "1", "kind": "ResourceProjection", "source_command": command, "resource_args": args, "workspace_id": a.Workspace, "project_id": a.Project, "complete": false, "apply_ready": false, "observation": meta, "data": output.Redact(v)}
	if destination != "" {
		b, e := json.MarshalIndent(projection, "", "  ")
		if e != nil {
			return e
		}
		if e = config.AtomicWrite(destination, b, 0600); e != nil {
			return e
		}
	}
	return a.emit(projection)
}
func (a *App) projectionCommand() {
	var command, destination string
	c := &cobra.Command{Use: "export [resource-ids...]", Short: "Export a redacted authorized resource projection; never apply-ready", Args: cobra.ArbitraryArgs, RunE: func(cmd *cobra.Command, args []string) error {
		return a.exportProjection(cmd.Context(), command, args, destination)
	}}
	c.Flags().StringVar(&command, "command", "", "Canonical resource get command")
	_ = c.MarkFlagRequired("command")
	c.Flags().StringVar(&destination, "destination", "", "Optional private destination")
	a.Root.AddCommand(c)
}
