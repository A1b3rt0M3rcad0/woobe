package cli

import (
	"os"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
)

func (a *App) developmentConfig(required bool) (*devworkspace.Config, error) {
	cwd, err := os.Getwd()
	if err != nil {
		return nil, err
	}
	path, err := devworkspace.Discover(cwd, a.ProjectConfig, a.NoProjectConfig)
	if err != nil {
		return nil, output.New(2, err.Error())
	}
	if path == "" {
		if required {
			return nil, output.New(2, "No development registry found; run woobe init for managed YAML development, or use standalone package export/import")
		}
		return nil, nil
	}
	c, err := devworkspace.Load(path)
	if err != nil {
		return nil, output.New(2, "Invalid development config: "+err.Error())
	}
	return c, nil
}

func (a *App) developmentConfigCommands() {
	a.developmentManageCommands()
	a.developmentBindCommand()
	a.developmentSurfaceCommands()
	a.developmentBulkCommands()
	a.Root.AddCommand(a.projectInitCommand())
	group := a.group("config")
	for _, action := range []string{"show", "check"} {
		action := action
		group.AddCommand(&cobra.Command{Use: action, Short: action + " the optional development configuration", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
			c, err := a.developmentConfig(true)
			if err != nil {
				return err
			}
			if action == "show" {
				return a.emit(map[string]any{"config": c, "file": c.File, "root": c.RootPath(), "scope": "development_only"})
			}
			graph, err := devworkspace.LoadGraph(c)
			if err != nil {
				return output.New(2, err.Error())
			}
			return a.emit(map[string]any{"valid": true, "file": c.File, "root": c.RootPath(), "resources": len(graph.Nodes), "authorization": "not_evaluated", "executed": false})
		}})
	}
	resources := a.group("resources")
	resources.AddCommand(&cobra.Command{Use: "list", Short: "List registered local development resources", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		c, err := a.developmentConfig(true)
		if err != nil {
			return err
		}
		return a.emit(map[string]any{"resources": c.Resources, "root": c.RootPath()})
	}})
	resources.AddCommand(&cobra.Command{Use: "used-by KIND REFERENCE", Short: "Inspect direct and indirect local consumers", Args: cobra.ExactArgs(2), Example: "woobe resources used-by provider \"@openai-main\"", RunE: func(cmd *cobra.Command, args []string) error {
		c, err := a.developmentConfig(true)
		if err != nil {
			return err
		}
		resource, err := c.Resolve(args[0], args[1])
		if err != nil {
			return output.New(2, err.Error())
		}
		graph, err := devworkspace.LoadGraph(c)
		if err != nil {
			return output.New(2, err.Error())
		}
		return a.emit(map[string]any{"resource": resource, "consumers": graph.UsedBy(resource.Key), "scope": "local", "remote_impact": "server_required"})
	}})
}
