package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"github.com/spf13/cobra"
)

func (a *App) manifestCompileCommands(g *cobra.Command) {
	g.AddCommand(&cobra.Command{Use: "kinds", Short: "Discover supported resource kinds and canonical configuration actions", Args: cobra.NoArgs, RunE: func(*cobra.Command, []string) error { return a.emit(manifest.Kinds()) }})
	g.AddCommand(&cobra.Command{Use: "compile", Short: "Compile resource intents to explicit steps without network calls", Args: cobra.NoArgs, RunE: func(*cobra.Command, []string) error {
		d, e := a.readManifest()
		if e != nil {
			return e
		}
		if e = a.validateManifest(d); e != nil {
			return e
		}
		return a.emitManifestPlan(map[string]any{"document": d, "manifest_hash": d.Hash(), "source_schema_version": d.Version(), "authorization": "not_evaluated", "executed": false})
	}})
}
