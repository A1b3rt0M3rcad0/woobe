package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
)

func (a *App) checkpointCommand(g *cobra.Command) {
	var path string
	c := &cobra.Command{Use: "status", Short: "Inspect a local checkpoint without remote calls or mutations", Args: cobra.NoArgs, RunE: func(*cobra.Command, []string) error {
		b, e := readCheckpoint(path)
		if e != nil {
			return output.New(2, "checkpoint unavailable")
		}
		cp, e := parseCheckpoint(b)
		if e != nil {
			return output.New(2, "invalid checkpoint")
		}
		counts := map[string]int{}
		for _, s := range cp.Steps {
			counts[s]++
		}
		return a.emit(map[string]any{"checkpoint": cp, "counts": counts, "resume_requires_reconciliation": counts["unknown"]+counts["in_flight"] > 0})
	}}
	c.Flags().StringVar(&path, "checkpoint", "", "Checkpoint file")
	_ = c.MarkFlagRequired("checkpoint")
	g.AddCommand(c)
}
