package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
)

func (a *App) manifestExportCommand(g *cobra.Command) {
	var resource, id, destination string
	c := &cobra.Command{Use: "export", Short: "Export a partial resource projection, not an apply document", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		commands := map[string]string{"agent": "project agent get", "network": "project network get", "skill-version": "project skill version get", "knowledge": "project knowledge collection get", "surface": "project surface get"}
		command, ok := commands[resource]
		if !ok {
			return output.New(2, "unsupported resource; use export --command for other readers")
		}
		return a.exportProjection(cmd.Context(), command, []string{id}, destination)
	}}
	c.Flags().StringVar(&resource, "resource", "", "agent, network, skill-version, knowledge or surface")
	c.Flags().StringVar(&id, "id", "", "Explicit resource ID")
	c.Flags().StringVar(&destination, "destination", "", "Optional private destination")
	_ = c.MarkFlagRequired("resource")
	_ = c.MarkFlagRequired("id")
	g.AddCommand(c)
}
