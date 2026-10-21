package cli

import (
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/spf13/cobra"
)

var surfaceFields = []string{"allowed_origins", "appearance_config", "requests_per_minute", "max_concurrent_runs", "session_token_ttl_seconds"}

func surfaceAuthor(native map[string]any, key, target string) map[string]any {
	spec := map[string]any{"target_ref": target}
	for _, field := range surfaceFields {
		spec[field] = native[field]
	}
	return map[string]any{"format": "woobe-package", "schema_version": "1.0", "kind": "Surface", "metadata": map[string]any{"key": key, "name": native["name"], "description": native["description"]}, "spec": spec}
}
func surfaceBody(document map[string]any) (map[string]any, error) {
	spec := packagefmt.Object(document["spec"])
	meta := packagefmt.Object(document["metadata"])
	allowed := map[string]bool{"target_ref": true}
	body := map[string]any{"name": meta["name"], "description": meta["description"]}
	for _, field := range surfaceFields {
		allowed[field] = true
		if value, ok := spec[field]; ok {
			body[field] = value
		}
	}
	for field := range spec {
		if !allowed[field] {
			return nil, output.New(2, "Surface author spec contains unsupported field: "+field)
		}
	}
	if packagefmt.Text(spec["target_ref"]) == "" {
		return nil, output.New(2, "Surface requires target_ref to a registered Agent or Network")
	}
	return body, nil
}
func (a *App) developmentSurfaceCommands() {
	for _, action := range []string{"pull", "push", "create", "diff", "status", "validate"} {
		var alias, path string
		command := &cobra.Command{Use: action + " [REFERENCE]", Args: cobra.MaximumNArgs(1), Short: action + " a registered Surface author YAML", Long: "Surface author files reference one registered Agent or Network. Pull the target first. Surface create resolves its current Production Release; push updates native configuration with optimistic concurrency and does not refresh or activate a Release. Native Surface settings can affect an active Surface; use disable before changes that must stay offline. Raw lifecycle commands remain available.", RunE: func(cmd *cobra.Command, args []string) error {
			c, err := a.developmentConfig(true)
			if err != nil {
				return err
			}
			unlock, err := c.Lock()
			if err != nil {
				return output.New(2, err.Error())
			}
			defer unlock()
			c, err = devworkspace.Load(c.File)
			if err != nil {
				return output.New(2, err.Error())
			}
			if a.ContextName == "" && os.Getenv("WOOBE_CONTEXT") == "" {
				a.ContextName = c.Context
			}
			connection, err := a.resolve()
			if err != nil {
				return err
			}
			state, err := c.ReadState(strings.TrimRight(connection.APIURL, "/"), connection.Workspace, connection.Project)
			if err != nil {
				return output.New(2, err.Error())
			}
			graph, err := devworkspace.LoadGraph(c)
			if err != nil {
				return output.New(2, err.Error())
			}
			reference := ""
			if len(args) > 0 {
				reference = args[0]
			}
			resource, resolveErr := developmentReference(c, state, "Surface", reference, path)
			if action == "pull" && resolveErr != nil && alias != "" {
				if registered, lookupErr := c.Resolve("Surface", "@"+alias); lookupErr == nil && state.Pending[registered.UID] == "surface-create-outcome-unknown" {
					resource, resolveErr = registered, nil
				}
			}
			if action != "pull" && resolveErr != nil {
				return resolveErr
			}
			if action != "pull" && (alias != "" || path != "") {
				return output.New(2, "--alias and --path apply only to pull; resolve the registered artifact by alias or path")
			}
			if resolveErr != nil && (reference == "" || alias == "") {
				return output.New(2, "First Surface pull requires native UUID and --alias; pull its target Agent/Network first")
			}
			var node *devworkspace.Node
			var binding devworkspace.Binding
			if resource != nil {
				node = graph.Nodes[resource.Key]
				binding = state.Bindings[resource.UID]
			}
			if action == "validate" || action == "diff" || action == "status" {
				_, err = surfaceBody(node.Document)
				if err != nil {
					return err
				}
				changes := devworkspace.Diff(binding.Base, node.Document)
				return a.emit(map[string]any{"action": action, "alias": resource.Alias, "valid": true, "bound": binding.ResourceID != "", "changes": changes, "changed": len(changes) > 0, "scope": "local", "executed": false})
			}
			client, err := a.client()
			if err != nil {
				return err
			}
			if action == "pull" {
				id := reference
				if resource != nil && binding.ResourceID != "" {
					id = binding.ResourceID
				}
				if err = resourceID(id); err != nil {
					return err
				}
				response, _, err := client.Request(cmd.Context(), "GET", "/chat-surfaces/"+url.PathEscape(id), nil, nil)
				if err != nil {
					return err
				}
				remote, err := developmentResponseData(response)
				if err != nil {
					return err
				}
				if remote["project_id"] != connection.Project {
					return output.New(6, "Surface belongs to another Project")
				}
				target := ""
				for _, r := range c.Resources {
					if strings.EqualFold(r.Kind, packagefmt.Text(remote["target_type"])) && state.Bindings[r.UID].ResourceID == remote["target_id"] {
						target = r.Key
						break
					}
				}
				if target == "" {
					return output.New(6, "Pull the target first: woobe "+packagefmt.Text(remote["target_type"])+" "+packagefmt.Text(remote["target_id"])+" pull --env production --alias TARGET")
				}
				key := alias
				if resource != nil {
					key = resource.Key
				}
				document := surfaceAuthor(remote, key, target)
				if _, err = surfaceBody(document); err != nil {
					return err
				}
				base := document
				if resource != nil && binding.Base != nil {
					var conflicts []devworkspace.Conflict
					document, conflicts = devworkspace.Merge(binding.Base, node.Document, document)
					if len(conflicts) > 0 {
						return output.New(6, "Surface has conflicting local and remote changes; review both versions before pull")
					}
				}
				if a.DryRun {
					return a.emit(map[string]any{"action": "pull", "executed": false, "resource_id": id})
				}
				if resource == nil {
					for uid, existing := range state.Bindings {
						if existing.ResourceID == id && uid != "" {
							return output.New(6, "Native Surface already has a local binding; use its existing alias")
						}
					}
					created, err := c.Add("Surface", alias, path, document, nil, false)
					if err != nil {
						return output.New(2, err.Error())
					}
					resource = &created
				} else {
					data, err := devworkspace.Encode(document)
					if err != nil {
						return err
					}
					folder, err := c.ResourcePath(*resource)
					if err != nil {
						return err
					}
					file := folder
					if !strings.HasSuffix(file, ".yaml") && !strings.HasSuffix(file, ".yml") && !strings.HasSuffix(file, ".json") {
						file = filepath.Join(file, "surface.yaml")
					}
					if err = c.Commit(map[string][]byte{file: data}); err != nil {
						return output.New(2, err.Error())
					}
				}
				state.Bindings[resource.UID] = devworkspace.Binding{ResourceID: id, Revision: remote["updated_at"], Base: base}
				delete(state.Pending, resource.UID)
				if err = c.WriteState(state); err != nil {
					return output.New(10, "Surface files saved but baseline persistence failed; run pull to reconcile")
				}
				return a.emit(map[string]any{"action": "pull", "pulled": true, "alias": resource.Alias, "resource_id": id})
			}
			body, err := surfaceBody(node.Document)
			if err != nil {
				return err
			}
			if state.Pending[resource.UID] != "" {
				return output.New(10, "An earlier Surface create has an unknown outcome; inspect surface list and pull its UUID with --alias "+resource.Alias+" before retrying")
			}
			if action == "create" && binding.ResourceID != "" {
				return output.New(6, "Surface is already bound; use push")
			}
			if action == "push" && binding.ResourceID == "" {
				return output.New(2, "Unbound Surface requires explicit create")
			}
			target := graph.Nodes[packagefmt.Text(packagefmt.Object(node.Document["spec"])["target_ref"])]
			if target == nil {
				return output.New(2, "Surface target is not registered")
			}
			targetID := state.Bindings[target.Resource.UID].ResourceID
			if targetID == "" {
				return output.New(2, "Create/push and publish the target before creating a Surface")
			}
			method, endpoint := "PATCH", "/chat-surfaces/"+url.PathEscape(binding.ResourceID)
			if action == "create" {
				method, endpoint = "POST", "/chat-surfaces/projects/"+url.PathEscape(connection.Project)
				body["target_type"] = strings.ToLower(target.Resource.Kind)
				body["target_id"] = targetID
			} else {
				if packagefmt.Object(binding.Base["spec"])["target_ref"] != packagefmt.Object(node.Document["spec"])["target_ref"] {
					return output.New(6, "A Surface target is immutable; clone/create a new Surface")
				}
				response, _, err := client.Request(cmd.Context(), "GET", endpoint, nil, nil)
				if err != nil {
					return err
				}
				remote, err := developmentResponseData(response)
				if err != nil {
					return err
				}
				if remote["project_id"] != connection.Project || fmt.Sprint(remote["updated_at"]) != fmt.Sprint(binding.Revision) || remote["target_id"] != targetID {
					return output.New(6, "Surface changed remotely; pull and reconcile before push")
				}
				if binding.Revision == nil {
					return output.New(6, "Pull the Surface to capture its current revision")
				}
				client.Headers.Set("If-Match", fmt.Sprintf("\"%v\"", binding.Revision))
			}
			if a.DryRun {
				return a.emit(map[string]any{"action": action, "executed": false, "validation": "local_and_remote_identity", "server_validation": "performed_on_apply", "request": body})
			}
			if !a.Yes {
				return output.New(2, "Surface mutation requires --yes")
			}
			data, err := json.Marshal(body)
			if err != nil {
				return err
			}
			if action == "create" {
				if state.Pending == nil {
					state.Pending = map[string]string{}
				}
				state.Pending[resource.UID] = "surface-create-outcome-unknown"
				if err = c.WriteState(state); err != nil {
					return output.New(2, "Cannot persist Surface create intent")
				}
			}
			response, _, err := client.Request(cmd.Context(), method, endpoint, nil, data)
			if err != nil {
				failure := output.Normalize(err)
				if action == "create" && failure.Outcome == "rejected" {
					switch failure.Status {
					case 400, 401, 403, 404, 405, 409, 412, 422:
						delete(state.Pending, resource.UID)
						if saveErr := c.WriteState(state); saveErr != nil {
							return output.New(10, "Create was rejected but intent cleanup failed; reconcile private state before retrying")
						}
					}
				}
				return err
			}
			remote, err := developmentResponseData(response)
			if err != nil {
				return err
			}
			state.Bindings[resource.UID] = devworkspace.Binding{ResourceID: packagefmt.Text(remote["id"]), Revision: remote["updated_at"], Base: node.Document}
			delete(state.Pending, resource.UID)
			if err = c.WriteState(state); err != nil {
				return output.New(10, "Surface updated but local baseline failed; pull to reconcile; do not retry create")
			}
			return a.emit(map[string]any{"action": action, "executed": true, "alias": resource.Alias, "resource_id": remote["id"], "release_refreshed": false})
		}}
		command.Flags().StringVar(&alias, "alias", "", "Local alias for first pull")
		command.Flags().StringVar(&path, "path", "", "Local Surface path relative to configured artifact root")
		a.group("develop surface").AddCommand(command)
	}
}
