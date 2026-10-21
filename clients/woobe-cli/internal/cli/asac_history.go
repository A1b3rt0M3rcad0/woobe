package cli

import (
	"fmt"
	"net/url"
	"os"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
)

func (a *App) asacCommands() {
	a.asacDraftCommands()
	a.asacCandidateCommands()
	a.asacEvaluationCommands()
	a.asacPublicationCommands()
	a.asacLeaseCommands()
	a.asacDeploymentCommands()
	for _, kind := range []string{"agent", "network"} {
		parent := a.group("develop " + kind)
		var environment string
		current := &cobra.Command{Use: "current REFERENCE", Short: "Observe the exact remote environment selection", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
			remote, _ := cmd.Flags().GetBool("remote")
			if !remote {
				return output.New(2, "current requires --remote; use status for offline observations")
			}
			data, err := a.asacCurrent(cmd, kind, args[0], environment)
			if err != nil {
				return err
			}
			return a.emit(data)
		}}
		current.Flags().StringVar(&environment, "env", "production", "Environment selection to observe: draft, staging or production")
		current.Flags().Bool("remote", true, "Consult the authoritative server; this command is always remote")
		parent.AddCommand(current)
		var checkoutRevision string
		checkout := &cobra.Command{Use: "checkout REFERENCE --revision REVISION_ID", Short: "Restore a sealed local revision while preserving origin", Args: cobra.ExactArgs(1), Long: "Restores retained author YAML and declared support files only after verifying executable identity. Requires a clean source checkpoint. Local edits, shared dependency edits and unregistered files are protected; --yes cannot bypass protection. Changes only local author files and working revision, never the remote Draft or an environment.", RunE: func(cmd *cobra.Command, args []string) error {
			if a.DryRun {
				return output.New(2, "checkout is a local restore; use revision diff to inspect before writing")
			}
			c, err := a.developmentConfig(true)
			if err != nil {
				return err
			}
			unlock, err := c.Lock()
			if err != nil {
				return output.New(2, err.Error())
			}
			defer unlock()
			resource, err := c.Resolve(strings.ToUpper(kind[:1])+kind[1:], args[0])
			if err != nil {
				return output.New(2, err.Error())
			}
			record, err := c.ReadRevision(*resource, checkoutRevision)
			if err != nil {
				return output.New(9, err.Error())
			}
			graph, err := devworkspace.LoadGraph(c)
			if err != nil {
				return output.New(2, err.Error())
			}
			data, err := graph.CheckoutRevision(*resource, record)
			if err != nil {
				return output.New(2, err.Error())
			}
			return a.emit(data)
		}}
		checkout.Flags().StringVar(&checkoutRevision, "revision", "", "Retained local revision ID (required)")
		_ = checkout.MarkFlagRequired("revision")
		parent.AddCommand(checkout)
		var onto, rebaseBase, rebaseMessage string
		rebase := &cobra.Command{Use: "rebase REFERENCE --onto REVISION_ID", Short: "Reconcile sealed branches into a new local revision", Args: cobra.ExactArgs(1), Long: "Three-way merge of sealed author definitions and support bytes against a known common ancestor. Requires clean checkpointed files. Arrays and support files are atomic; concurrent changes report paths without rewriting files or history. Old revisions remain immutable. The new revision has the selected onto revision as parent. No remote Draft, Release or environment changes.", RunE: func(cmd *cobra.Command, args []string) error {
			if a.DryRun {
				return output.New(2, "rebase creates a local checkpoint; use revision diff to inspect before writing")
			}
			c, err := a.developmentConfig(true)
			if err != nil {
				return err
			}
			unlock, err := c.Lock()
			if err != nil {
				return output.New(2, err.Error())
			}
			defer unlock()
			resource, err := c.Resolve(strings.ToUpper(kind[:1])+kind[1:], args[0])
			if err != nil {
				return output.New(2, err.Error())
			}
			graph, err := devworkspace.LoadGraph(c)
			if err != nil {
				return output.New(2, err.Error())
			}
			data, err := graph.RebaseRevision(*resource, onto, rebaseBase, rebaseMessage)
			if err != nil {
				if strings.HasPrefix(err.Error(), "ASAC_REBASE_CONFLICT:") {
					failure := output.New(6, err.Error())
					failure.DomainCode = "ASAC_REBASE_CONFLICT"
					failure.Outcome = "not_attempted"
					for _, issue := range data["conflicts"].([]devworkspace.Conflict) {
						failure.Diagnostics = append(failure.Diagnostics, output.DomainDiagnostic{Code: failure.DomainCode, Path: issue.Path})
					}
					return failure
				}
				return output.New(2, err.Error())
			}
			return a.emit(data)
		}}
		rebase.Flags().StringVar(&onto, "onto", "", "Sealed target revision ID (required)")
		rebase.Flags().StringVar(&rebaseBase, "base", "", "Explicit common ancestor when the DAG has multiple possible bases")
		rebase.Flags().StringVar(&rebaseMessage, "message", "", "New revision message; default identifies original and onto revisions")
		_ = rebase.MarkFlagRequired("onto")
		parent.AddCommand(rebase)

		for _, action := range []string{"history", "heads", "revision"} {
			var message string
			var parents []string
			var fetchRevisions bool
			command := &cobra.Command{Use: action + " REFERENCE [ACTION] [REVISION...]", Short: "Inspect or seal local immutable ASaC " + action, Args: cobra.MinimumNArgs(1), Long: "Local history does not claim remote freshness. Revision create freezes a closed portable package without publishing, staging or activating it. history verify checks immutable record digests, DAG and object availability. Explicit multiple parents describe resolved content; no content is merged automatically.", RunE: func(cmd *cobra.Command, args []string) error {
				if fetchRevisions && !(action == "history" && len(args) == 2 && args[1] == "fetch") {
					return output.New(2, "--revisions applies only to history fetch")
				}
				if action == "heads" && len(args) != 1 {
					return output.New(2, "heads expects only one resource reference")
				}
				if action != "revision" && (cmd.Flags().Changed("message") || cmd.Flags().Changed("parent")) {
					return output.New(2, "--message applies to create/merge; --parent applies only to create")
				}
				if action == "revision" && len(args) > 1 && args[1] != "create" && args[1] != "merge" && (cmd.Flags().Changed("message") || cmd.Flags().Changed("parent")) {
					return output.New(2, "--message applies to create/merge; --parent applies only to create")
				}
				c, err := a.developmentConfig(true)
				if err != nil {
					return err
				}
				unlock, err := c.Lock()
				if err != nil {
					return output.New(2, err.Error())
				}
				defer unlock()
				state := &devworkspace.State{API: "", Bindings: map[string]devworkspace.Binding{}, Requirements: map[string]any{}, Credentials: map[string]string{}}
				if a.ContextName == "" && os.Getenv("WOOBE_CONTEXT") == "" {
					a.ContextName = c.Context
				}
				if connection, resolveErr := a.resolve(); resolveErr == nil {
					state, err = c.ReadState(strings.TrimRight(connection.APIURL, "/"), connection.Workspace, connection.Project)
					if err != nil {
						return output.New(2, err.Error())
					}
				}
				resource, err := developmentReference(c, state, kind, args[0], "")
				if err != nil {
					return err
				}
				if action == "heads" || action == "history" && len(args) == 2 && args[1] == "verify" {
					if len(args) > 2 {
						return output.New(2, "unexpected history arguments")
					}
					data, err := c.VerifyHistory(*resource)
					if err != nil {
						return output.New(9, err.Error())
					}
					return a.emit(data)
				}
				if action == "history" {
					if len(args) == 2 && args[1] == "fetch" {
						if fetchRevisions {
							return a.asacFetchRevisions(cmd, kind, c, state, resource)
						}
						return a.asacFetch(cmd, kind, c, state, resource)
					}
					if len(args) != 1 {
						return output.New(2, "Use history, history fetch or history verify")
					}
					records, err := c.Revisions(*resource)
					if err != nil {
						return output.New(9, err.Error())
					}
					return a.emit(map[string]any{"resource_uid": resource.UID, "revisions": records, "scope": "local", "remote_status": "unverified"})
				}
				if len(args) < 2 {
					return output.New(2, "Use revision create, merge, show, diff or hydrate")
				}
				switch args[1] {
				case "create", "merge":
					if args[1] == "merge" {
						if len(args) != 4 || cmd.Flags().Changed("parent") {
							return output.New(2, "revision merge requires two sealed revision IDs and --message; --parent applies to revision create")
						}
						parents = []string{args[2], args[3]}
					} else if len(args) != 2 {
						return output.New(2, "unexpected revision create arguments")
					}
					if a.DryRun {
						return output.New(2, "revision create is a local checkpoint; use validate/diff to preview without writes")
					}
					graph, err := devworkspace.LoadGraph(c)
					if err != nil {
						return output.New(2, err.Error())
					}
					record, err := graph.CreateRevision(*resource, state, message, parents)
					if err != nil {
						return output.New(2, err.Error())
					}
					return a.emit(record)
				case "hydrate":
					if len(args) != 3 {
						return output.New(2, "revision hydrate requires one retained revision ID; use history fetch --revisions first")
					}
					record, err := c.ReadRevision(*resource, args[2])
					if err != nil {
						return output.New(9, "Retain and verify revision metadata with history fetch --revisions before hydration")
					}
					return a.asacHydrate(cmd, c, state, resource, record)
				case "show":
					if len(args) != 3 {
						return output.New(2, "revision show requires one revision ID")
					}
					record, err := c.ReadRevision(*resource, args[2])
					if err != nil {
						return output.New(9, err.Error())
					}
					return a.emit(record)
				case "diff":
					if len(args) != 4 {
						return output.New(2, "revision diff requires two revision IDs")
					}
					left, err := c.ReadRevision(*resource, args[2])
					if err != nil {
						return output.New(9, err.Error())
					}
					right, err := c.ReadRevision(*resource, args[3])
					if err != nil {
						return output.New(9, err.Error())
					}
					return a.emit(map[string]any{"from": left.ID, "to": right.ID, "definition_changed": left.DefinitionDigest != right.DefinitionDigest, "components_before": left.Components, "components_after": right.Components, "scope": "sealed_composition"})
				default:
					return output.New(2, "Use revision create, merge, show, diff or hydrate")
				}
			}}
			if action == "revision" {
				command.Long += " Revision hydrate REVISION_ID downloads verified executable objects after history fetch --revisions. When the backend retained author source, it also verifies exact YAML, support files and the recorded compiler recipe against the sealed definition before retaining source locally. It preserves author files, native bindings and the working head; checkout is a separate guarded operation. Missing source remains explicit, and hydration does not qualify runtime execution."
			}
			command.Flags().StringVar(&message, "message", "", "Checkpoint message (required for revision create or merge)")
			command.Flags().StringSliceVar(&parents, "parent", nil, "Explicit sealed parent revision IDs (repeatable); default current working revision")
			if action == "history" {
				command.Flags().BoolVar(&fetchRevisions, "revisions", false, "Fetch isolated revision metadata instead of legacy releases/deployments; never changes author files")
			}
			parent.AddCommand(command)
		}
	}
}

func (a *App) asacCurrent(cmd *cobra.Command, kind, reference, environment string) (map[string]any, error) {
	if environment != "draft" && environment != "staging" && environment != "production" {
		return nil, output.New(2, "Use draft, staging or production")
	}
	id, err := a.nativeReference(kind+"_id", reference)
	if err != nil {
		return nil, err
	}
	if err = resourceID(id); err != nil {
		return nil, err
	}
	control, err := a.client()
	if err != nil {
		return nil, err
	}
	if a.Project == "" {
		return nil, output.New(2, "Select a Project before querying remote history")
	}
	path := fmt.Sprintf("/projects/%s/%ss/%s/asac/current", url.PathEscape(a.Project), kind, url.PathEscape(id))
	response, _, err := control.Request(cmd.Context(), "GET", path, url.Values{"environment": {environment}}, nil)
	if err != nil {
		return nil, err
	}
	data, err := developmentResponseData(response)
	if err != nil {
		return nil, err
	}
	if data["schema_version"] != "1.0" || data["resource_id"] != id || data["environment"] != environment {
		return nil, output.New(9, "ASaC selection identity mismatch")
	}
	return data, nil
}

func (a *App) asacFetch(cmd *cobra.Command, kind string, c *devworkspace.Config, state *devworkspace.State, resource *devworkspace.Resource) error {
	control, err := a.client()
	if err != nil {
		return err
	}
	id := state.Bindings[resource.UID].ResourceID
	if id == "" {
		tracking, err := c.ReadTracking(*resource)
		if err != nil {
			return output.New(2, "History fetch needs a native binding or tracking origin")
		}
		if tracking.Origin.Target != strings.TrimRight(control.Base, "/") || tracking.Origin.Workspace != a.Workspace || tracking.Origin.Project != a.Project {
			return output.New(9, "Tracking origin belongs to another selected destination")
		}
		id = tracking.Origin.ResourceID
	}
	if err = resourceID(id); err != nil {
		return err
	}
	total := 0
	watermarks := map[string]any{}
	for _, stream := range []string{"releases", "deployments"} {
		cursor := ""
		seen := map[string]bool{}
		var watermark any
		for page := 0; page < 100; page++ {
			path := fmt.Sprintf("/projects/%s/%ss/%s/asac/history", url.PathEscape(a.Project), kind, url.PathEscape(id))
			query := url.Values{"stream": {stream}, "limit": {"100"}}
			if cursor != "" {
				query.Set("cursor", cursor)
			}
			response, _, err := control.Request(cmd.Context(), "GET", path, query, nil)
			if err != nil {
				return err
			}
			data, err := developmentResponseData(response)
			if err != nil {
				return err
			}
			if data["schema_version"] != "1.0" || data["resource_id"] != id || data["stream"] != stream {
				return output.New(9, "ASaC history scope mismatch")
			}
			if page == 0 {
				watermark = data["watermark"]
			} else if fmt.Sprint(watermark) != fmt.Sprint(data["watermark"]) {
				return output.New(9, "ASaC history watermark changed during traversal")
			}
			records, ok := data["records"].([]any)
			if !ok || len(records) > 100 {
				return output.New(9, "Invalid history page")
			}
			for _, raw := range records {
				record, ok := raw.(map[string]any)
				if !ok || record["resource_id"] != id {
					return output.New(9, "Invalid history record identity")
				}
				if !a.DryRun {
					if err = c.StoreHistoryReceipt(*resource, strings.TrimRight(control.Base, "/"), a.Workspace, a.Project, record); err != nil {
						return output.New(9, err.Error())
					}
				}
				total++
			}
			hasMore, ok := data["has_more"].(bool)
			if !ok || data["complete"] != !hasMore {
				return output.New(9, "ASaC history completeness mismatch")
			}
			if !hasMore {
				watermarks[stream] = watermark
				break
			}
			cursor, ok = data["next_cursor"].(string)
			if !ok || cursor == "" || seen[cursor] {
				return output.New(9, "ASaC history cursor missing or repeated")
			}
			seen[cursor] = true
			if page == 99 {
				return output.New(9, "ASaC history exceeds traversal bound; retained receipts do not constitute a complete fetch")
			}
		}
	}
	return a.emit(map[string]any{"resource_uid": resource.UID, "resource_id": id, "fetched": total, "watermarks": watermarks, "metadata_complete": true, "coverage": "authorized_resource_metadata", "objects_available": "not_evaluated", "author_files_changed": false, "production_changed": false, "executed": !a.DryRun, "remote_status": "observed_at_fetch"})
}

// Resolving an authenticated operation target does not recreate native author
// bindings or claim a synchronized base after a fresh clone.
func asacRegisteredResourceID(c *devworkspace.Config, state *devworkspace.State, resource *devworkspace.Resource) (string, error) {
	id := state.Bindings[resource.UID].ResourceID
	if id == "" {
		tracking, err := c.ReadTracking(*resource)
		if err != nil {
			return "", output.New(2, "Operation requires a native binding or durable tracking origin")
		}
		if tracking.Origin.Target != state.API || tracking.Origin.Workspace != state.Workspace || tracking.Origin.Project != state.Project {
			return "", output.New(9, "Tracking origin belongs to another destination")
		}
		id = tracking.Origin.ResourceID
	}
	if !uuidReference(id) {
		return "", output.New(2, "Recover the original native resource identity first")
	}
	return id, nil
}
