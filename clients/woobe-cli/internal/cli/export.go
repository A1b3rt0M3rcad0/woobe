package cli

import (
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"net/url"
)

func (a *App) exportCommands() {
	var destination string
	c := &cobra.Command{Use: "export <agent-id>", Short: "Export an authorized projection; never an apply-ready destructive patch", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
		client, e := a.client()
		if e != nil {
			return e
		}
		v, _, e := client.Request(cmd.Context(), "GET", "/ai/agents/"+url.PathEscape(args[0]), nil, nil)
		if e != nil {
			return e
		}
		projection := map[string]any{"schema_version": "1", "kind": "AgentProjection", "resource_id": args[0], "complete": false, "apply_ready": false, "data": output.Redact(v)}
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
	}}
	c.Flags().StringVar(&destination, "destination", "", "Optional export file")
	a.group("project agent").AddCommand(c)
}
