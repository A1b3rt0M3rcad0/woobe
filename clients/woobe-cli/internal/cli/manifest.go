package cli

import (
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
)

func (a *App) readManifest() (manifest.Document, error) {
	b, e := a.body(true)
	if e != nil {
		return manifest.Document{}, e
	}
	d, e := manifest.Parse(b)
	if e != nil {
		return d, output.New(2, e.Error())
	}
	return d, nil
}
func (a *App) validateManifest(d manifest.Document) error {
	for _, s := range d.Steps {
		if len(stepSecretNames(s)) > 0 && !secretConfigurationCommand(s.Command) {
			return output.New(2, "protected references are supported only for Tool and provider credential configuration")
		}
		var found *Operation
		for _, op := range a.Registry {
			if op.Command == s.Command {
				v := op
				found = &v
				break
			}
		}
		if found == nil || found.Kind != "http" {
			return output.New(2, "unknown manifest operation: "+s.Command)
		}
		category := found.Command == "workspace authority category create" || found.Command == "workspace authority category update"
		if category {
			if d.Workspace == "" {
				return output.New(2, "category manifest requires workspace_id")
			}
			if found.Method == "PATCH" && s.IfMatch == "" {
				return output.New(2, "category update requires explicit if_match")
			}
		}
		if found.Status == "proposed" && !category {
			return output.New(9, "manifest uses absent server extension")
		}
		if found.Method == "GET" || found.Method == "HEAD" {
			return output.New(2, "manifest steps must mutate configuration; use explicit reads for inspection")
		}
		if found.Secret || found.Effect == "publication" || found.Effect == "execution" || found.Method == "DELETE" {
			return output.New(2, "manifest permits configuration operations only; issuance publication execution and deletion must be explicit commands")
		}
		if len(s.Args) != len(found.Params) {
			return output.New(2, "wrong manifest resource arguments")
		}
		if len(s.Body) > 0 {
			var obj map[string]any
			if json.Unmarshal(s.Body, &obj) != nil || obj == nil {
				return output.New(2, "manifest configuration body must be an object")
			}
		}
		if category && len(s.Body) > 0 {
			var spec map[string]any
			if e := json.Unmarshal(s.Body, &spec); e != nil {
				return output.New(2, "invalid category definition")
			}
			if e := manifest.ValidateCategorySpec(spec, found.Method == "POST"); e != nil {
				return output.New(2, e.Error())
			}
		}
		if found.Body && len(s.Body) == 0 {
			return output.New(2, "manifest operation requires body")
		}
	}
	return nil
}
func (a *App) manifestCommands() {
	g := a.group("manifest")
	g.AddCommand(&cobra.Command{Use: "validate", Args: cobra.NoArgs, RunE: func(*cobra.Command, []string) error {
		d, e := a.readManifest()
		if e != nil {
			return e
		}
		if e = a.validateManifest(d); e != nil {
			return e
		}
		return a.emit(map[string]any{"source_schema_version": d.Version(), "valid": true, "manifest_hash": d.Hash(), "authorization": "not_evaluated"})
	}})
	a.manifestPreflightCommand(g)
	a.manifestCompileCommands(g)
	a.manifestPlanCommands(g)
	a.checkpointCommand(g)
	a.manifestExportCommand(g)
	a.manifestCaptureCommand(g)
}
