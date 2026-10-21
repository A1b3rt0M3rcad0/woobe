package cli

import (
	"bytes"
	"encoding/json"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"github.com/spf13/pflag"
)

type developmentBatchFailure struct {
	Data  any
	Cause *output.Error
}

func (f *developmentBatchFailure) Error() string { return f.Cause.Error() }

func (a *App) developmentBulkCommands() {
	for _, action := range []string{"validate", "diff", "push"} {
		var kind string
		command := &cobra.Command{Use: action, Args: cobra.NoArgs, Short: action + " explicitly registered Agent, Network and Surface roots", Long: "Operate only on the registered dependency graph. Shared dependencies are compiled through their registered UIDs; frozen Network constituents are not independent roots. push requires already bound roots and stops at the first error. --dry-run validates exact Agent/Network server plans and Surface destination/CAS identity without applying changes. Surface settings follow their native lifecycle and may affect active Surfaces; disable first when changes must stay offline.", RunE: func(cmd *cobra.Command, _ []string) error {
			c, err := a.developmentConfig(true)
			if err != nil {
				return err
			}
			graph, err := devworkspace.LoadGraph(c)
			if err != nil {
				return output.New(2, err.Error())
			}
			if kind != "" && kind != "agent" && kind != "network" && kind != "surface" {
				return output.New(2, "--kind must be agent, network or surface")
			}
			// Provider, Model, Tool, Skill and Knowledge dependencies are included
			// by closure. They never become accidental top-level create operations.
			roots := []devworkspace.Resource{}
			seen := map[string]bool{}
			var visit func(string) error
			visit = func(key string) error {
				if seen[key] {
					return nil
				}
				seen[key] = true
				node := graph.Nodes[key]
				for _, dependency := range node.Dependencies {
					if err := visit(dependency); err != nil {
						return err
					}
				}
				if !node.Resource.Frozen && (node.Resource.Kind == "Agent" || node.Resource.Kind == "Network" || node.Resource.Kind == "Surface") && (kind == "" || strings.EqualFold(kind, node.Resource.Kind)) {
					roots = append(roots, node.Resource)
				}
				return nil
			}
			for _, resource := range c.Resources {
				if err := visit(resource.Key); err != nil {
					return err
				}
			}
			flags := []string{}
			cmd.Flags().Visit(func(flag *pflag.Flag) {
				if a.Root.PersistentFlags().Lookup(flag.Name) == nil {
					return
				}
				if flag.Name == "output" || flag.Name == "project-config" || flag.Name == "fields" || flag.Name == "wide" {
					return
				}
				if flag.Name == "query" {
					for _, value := range a.Query {
						flags = append(flags, "--query", value)
					}
					return
				}
				flags = append(flags, "--"+flag.Name+"="+flag.Value.String())
			})
			results := []any{}
			for _, resource := range roots {
				var stdout, stderr bytes.Buffer
				child := New(a.In, &stdout, &stderr)
				args := append(append([]string{}, flags...), "--project-config", c.File, "--output", "json", "develop", strings.ToLower(resource.Kind), action, "@"+resource.Alias)
				code := child.Execute(cmd.Context(), args)
				var record map[string]any
				if json.Unmarshal(stdout.Bytes(), &record) != nil {
					return output.New(9, "Bulk child returned incomplete evidence; reconcile retained checkpoints before another push")
				}
				results = append(results, map[string]any{"kind": resource.Kind, "alias": resource.Alias, "uid": resource.UID, "result": record})
				if code != 0 {
					return &developmentBatchFailure{Data: map[string]any{"results": results, "complete": false, "remaining_roots": len(roots) - len(results), "executed": action == "push" && !a.DryRun}, Cause: output.New(code, "Bulk stopped at the first failed root; completed writes remain checkpointed")}
				}
			}
			return a.emit(map[string]any{"results": results, "complete": true, "roots": len(roots), "executed": action == "push" && !a.DryRun, "registered_only": true})
		}}
		command.Flags().StringVar(&kind, "kind", "", "Restrict registered roots to agent, network or surface")
		a.group("resources").AddCommand(command)
	}
}
