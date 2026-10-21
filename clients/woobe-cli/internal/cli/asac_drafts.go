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
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/spf13/cobra"
)

type asacDraftObservation struct {
	ResourceID  string `json:"resource_id"`
	ResourceUID string `json:"resource_uid"`
	DraftID     string `json:"draft_id"`
	Generation  any    `json:"generation"`
	Definition  string `json:"definition_digest"`
}
type asacPending struct {
	RecordDigest string         `json:"record_digest,omitempty"`
	OperationID  string         `json:"operation_id"`
	Method       string         `json:"method"`
	Path         string         `json:"path"`
	Body         map[string]any `json:"body"`
}

func asacPrivatePath(c *devworkspace.Config, state *devworkspace.State, uid, suffix string) string {
	scope := strings.TrimSuffix(c.StatePath(state.API, state.Workspace, state.Project), ".json")
	return filepath.Join(scope+".asac", uid+"."+suffix+".json")
}

func (a *App) asacDraftCommands() {
	for _, kind := range []string{"agent", "network"} {
		var from, version, operation string
		cmd := &cobra.Command{Use: "draft REFERENCE ACTION [NAME]", Short: "Open, inspect or save an isolated remote Draft", Args: cobra.MinimumNArgs(2), Long: "Actions: list, show, select NAME_OR_UUID, open NAME, push, checkpoint REVISION_ID, reconcile. Opening captures an exact authorized snapshot and preserves the native default Draft. Push saves a closed object into the selected isolated Draft with its expected generation. Checkpoint registers an existing immutable local revision; it never silently saves changed YAML. Semantic lifecycle qualification happens separately at stage. Select recovers an existing name or UUID through matching durable origin, without changing YAML or server resources; it does not restore native bindings or credentials. Uncertain writes must be reconciled before another write or selection.", Example: "woobe agent '@support' draft list\nwoobe agent '@support' draft select hotfix\nwoobe network '@service' draft select DRAFT_UUID --dry-run", RunE: func(cmd *cobra.Command, args []string) error {
			if args[1] != "open" && (cmd.Flags().Changed("from") || cmd.Flags().Changed("version")) {
				return output.New(2, "--from and --version apply only to draft open")
			}
			return a.runASaCDraft(cmd, kind, args, from, version, operation)
		}}
		cmd.Flags().StringVar(&from, "from", "draft", "Exact snapshot source for draft open")
		cmd.Flags().StringVar(&version, "version", "", "Required immutable version with --from release")
		cmd.Flags().StringVar(&operation, "operation", "", "Expected recorded operation to reconcile")
		a.group("develop " + kind).AddCommand(cmd)
	}
}

// runASaCDraft is shared by the command adapter and the durable deploy pipeline.
func (a *App) runASaCDraft(cmd *cobra.Command, kind string, args []string, from, version, operation string) error {
	action := args[1]
	switch action {
	case "list", "show", "select", "open", "push", "checkpoint", "reconcile":
	default:
		return output.New(2, "Use draft list, show, select, open, push, checkpoint or reconcile")
	}
	if (action == "open" || action == "checkpoint" || action == "select") && len(args) != 3 || action != "open" && action != "checkpoint" && action != "select" && len(args) != 2 {
		return output.New(2, "Unexpected Draft arguments")
	}
	if a.DryRun && action != "list" && action != "show" && action != "reconcile" && action != "select" {
		return output.New(2, "Draft writes require explicit execution; use validate/diff to inspect local content")
	}
	if action != "reconcile" && operation != "" {
		return output.New(2, "--operation applies only to reconcile")
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
	if a.ContextName == "" && os.Getenv("WOOBE_CONTEXT") == "" {
		a.ContextName = c.Context
	}
	control, err := a.client()
	if err != nil {
		return err
	}
	client, err := packageapi.New(control, a.Project)
	if err != nil {
		return err
	}
	state, err := c.ReadState(strings.TrimRight(control.Base, "/"), a.Workspace, a.Project)
	if err != nil {
		return output.New(2, err.Error())
	}
	resource, err := developmentReference(c, state, kind, args[0], "")
	if err != nil {
		return err
	}
	id := state.Bindings[resource.UID].ResourceID
	if id == "" {
		tracking, err := c.ReadTracking(*resource)
		if err != nil {
			return output.New(2, "Draft operations need a native binding or durable tracking origin")
		}
		if tracking.Origin.Target != state.API || tracking.Origin.Project != state.Project || tracking.Origin.Workspace != state.Workspace {
			return output.New(9, "Tracking origin belongs to another destination")
		}
		id = tracking.Origin.ResourceID
	}
	if err = resourceID(id); err != nil {
		return err
	}
	base := fmt.Sprintf("/projects/%s/%ss/%s/asac", url.PathEscape(a.Project), kind, url.PathEscape(id))
	observedPath := asacPrivatePath(c, state, resource.UID, "draft")
	pendingPath := asacPrivatePath(c, state, resource.UID, "pending")
	request := func(method, path string, body any) (map[string]any, error) {
		var raw []byte
		if body != nil {
			raw, err = json.Marshal(body)
			if err != nil {
				return nil, err
			}
		}
		response, _, err := control.Request(cmd.Context(), method, path, nil, raw)
		if err != nil {
			return nil, err
		}
		return developmentResponseData(response)
	}
	saveObservation := func(data map[string]any) error {
		if data["resource_id"] != id || data["resource_uid"] != resource.UID || !uuidReference(packagefmt.Text(data["draft_id"])) || data["generation"] == nil {
			return output.New(9, "Remote Draft identity or generation mismatch")
		}
		encoded, _ := json.Marshal(asacDraftObservation{ResourceID: id, ResourceUID: resource.UID, DraftID: packagefmt.Text(data["draft_id"]), Generation: data["generation"], Definition: packagefmt.Text(data["definition_digest"])})
		return c.WriteOperationalFile(observedPath, encoded)
	}
	if action == "list" {
		data, err := request("GET", base+"/drafts", nil)
		if err != nil {
			return err
		}
		return a.emit(data)
	}

	if action == "select" {
		if raw, readErr := c.ReadOperationalFile(pendingPath, 16<<20); readErr == nil {
			if !clearedASaCPending(raw) {
				return output.New(9, "A Draft write is unresolved; reconcile its original operation before changing selection")
			}
		} else if !os.IsNotExist(readErr) {
			return output.New(2, readErr.Error())
		}
		listing, err := request("GET", base+"/drafts", nil)
		if err != nil {
			return err
		}
		lines, ok := listing["drafts"].([]any)
		if !ok || len(lines) > 200 || listing["complete"] != true {
			return output.New(9, "Draft listing is incomplete or incompatible")
		}
		var selected map[string]any
		for _, raw := range lines {
			line := packagefmt.Object(raw)
			if line["name"] == args[2] || line["draft_id"] == args[2] {
				if selected != nil {
					return output.New(9, "Draft selector is ambiguous")
				}
				selected = line
			}
		}
		if selected == nil {
			return output.New(2, "Draft not found; use draft list to select an existing name or UUID")
		}
		if selected["resource_id"] != id || selected["resource_uid"] != resource.UID || !uuidReference(packagefmt.Text(selected["draft_id"])) {
			return output.New(9, "Draft belongs to another logical or native resource")
		}
		exact, err := request("GET", base+"/drafts/"+url.PathEscape(packagefmt.Text(selected["draft_id"])), nil)
		if err != nil {
			return err
		}
		if exact["draft_id"] != selected["draft_id"] || exact["resource_id"] != id || exact["resource_uid"] != resource.UID || exact["generation"] == nil {
			return output.New(9, "Draft identity changed during selection")
		}
		if a.DryRun {
			return a.emit(map[string]any{"draft": exact, "selected": false, "executed": false, "remote_changed": false, "local_files_changed": false})
		}
		if err = saveObservation(exact); err != nil {
			return err
		}
		return a.emit(map[string]any{"draft": exact, "selected": true, "remote_changed": false, "local_files_changed": false})
	}
	if action == "reconcile" {
		raw, err := c.ReadOperationalFile(pendingPath, 16<<20)
		if err != nil {
			if os.IsNotExist(err) && operation == "" {
				return a.emit(map[string]any{"pending": false, "resource_id": id})
			}
			return output.New(2, "No recorded Draft operation to reconcile")
		}
		if clearedASaCPending(raw) && operation == "" {
			return a.emit(map[string]any{"pending": false, "resource_id": id})
		}
		var pending asacPending
		if decodeASaCPending(raw, &pending) != nil || !uuidReference(pending.OperationID) || pending.Body == nil || pending.Body["operation_id"] != pending.OperationID || !strings.HasPrefix(pending.Path, base+"/") || (pending.Method != "POST" && pending.Method != "PUT") {
			return output.New(9, "Invalid Draft operation checkpoint")
		}
		if operation != "" && operation != pending.OperationID {
			return output.New(9, "Operation differs from the recorded uncertain write")
		}
		data, err := request("GET", base+"/operations/"+url.PathEscape(pending.OperationID), nil)
		if err != nil {
			return err
		}
		if data["operation_id"] != pending.OperationID {
			return output.New(9, "Operation receipt belongs to another write")
		}
		if data["state"] == "committed" {
			result := packagefmt.Object(data["result"])
			if result["operation_id"] != pending.OperationID || result["write_outcome"] != "committed" {
				return output.New(9, "Original write is not proven committed")
			}
			if pending.Path == base+"/revisions" {
				record := packagefmt.Object(result["record"])
				expected := packagefmt.Object(pending.Body["record"])
				if record["record_digest"] != expected["record_digest"] || record["resource_uid"] != resource.UID || result["draft_id"] != pending.Body["draft_id"] {
					return output.New(9, "Revision receipt differs from the recorded write")
				}
			}
			if pending.Path == base+"/candidates" {
				if err = validateCandidateAcceptance(result, pending.OperationID, id, resource.UID, packagefmt.Text(pending.Body["revision_id"]), packagefmt.Text(pending.Body["draft_id"]), pending.RecordDigest); err != nil {
					return err
				}
				raw, _ := json.Marshal(result)
				if err = c.WriteOperationalFile(asacPrivatePath(c, state, resource.UID, "candidate"), raw); err != nil {
					return output.New(10, "Candidate accepted; its local receipt could not be saved")
				}
			}
			isEvaluation := pending.Path == base+"/candidates/"+url.PathEscape(packagefmt.Text(pending.Body["candidate_id"]))+"/evaluations"
			if isEvaluation {
				if err = validateEvaluationAcceptance(result, pending.OperationID, id, packagefmt.Text(pending.Body["candidate_id"]), pending.RecordDigest, packagefmt.Text(pending.Body["runtime_digest"])); err != nil {
					return err
				}
				raw, _ := json.Marshal(result)
				if err = c.WriteOperationalFile(asacPrivatePath(c, state, resource.UID, "evaluation"), raw); err != nil {
					return output.New(10, "Evaluation accepted; its local receipt could not be saved")
				}
			}
			isDeployment := pending.Path == base+"/deployment-plans" || pending.Path == base+"/deployments"
			if isDeployment {
				isPlan := pending.Path == base+"/deployment-plans"
				if err = validateDeploymentAcceptance(result, a.Project, id, pending.OperationID, packagefmt.Text(pending.Body["environment"]), pending.Body, isPlan); err != nil {
					return err
				}
				if err = c.StoreDeploymentReceipt(*resource, strings.TrimRight(control.Base, "/"), a.Workspace, a.Project, result, isPlan); err != nil {
					return output.New(10, "Deployment accepted; documentary receipt remains pending")
				}
			}
			isPublication := pending.Path == base+"/publications"
			isLease := strings.HasPrefix(pending.Path, base+"/leases/")
			if isLease {
				scope, scopeErr := asacLeaseScope(packagefmt.Text(pending.Body["scope"]), packagefmt.Text(pending.Body["draft_id"]))
				if scopeErr != nil {
					return scopeErr
				}
				if err = validateLeaseReceipt(result, a.Project, id, pending.OperationID, scope, pending.Body); err != nil {
					return err
				}
				if err = validateLeaseAction(result, strings.TrimPrefix(pending.Path, base+"/leases/")); err != nil {
					return err
				}
				if err = storeLeaseObservation(c, state, resource.UID, id, result); err != nil {
					return output.New(10, "Lease accepted; its private workflow proof remains pending")
				}
			}
			if isPublication {
				result, err = resolvePublicationAcceptance(request, base, result, pending.OperationID, id, resource.UID, packagefmt.Text(pending.Body["candidate_id"]), packagefmt.Text(pending.Body["evaluation_id"]), pending.RecordDigest, packagefmt.Text(pending.Body["runtime_digest"]), a.Project, resource.Kind)
				if err != nil {
					return err
				}
				if result["state"] == "cancelled" {
					err = c.StorePublicationCancellation(*resource, strings.TrimRight(control.Base, "/"), a.Workspace, a.Project, result)
				} else {
					err = c.StorePublicationReceipt(*resource, strings.TrimRight(control.Base, "/"), a.Workspace, a.Project, result)
				}
				if err != nil {
					return output.New(10, "Terminal publication documentary receipt is still pending: "+err.Error())
				}
				data["result"] = result
			}
			if pending.Path != base+"/candidates" && !isEvaluation && !isPublication && result["draft_id"] != nil && result["resource_id"] != nil {
				if err = saveObservation(result); err != nil {
					return err
				}
			}
			if err = c.WriteOperationalFile(pendingPath, []byte("{}")); err != nil {
				return err
			}
		}
		return a.emit(data)
	}
	var observed asacDraftObservation
	if action != "open" {
		raw, err := c.ReadOperationalFile(observedPath, 1<<20)
		if err != nil {
			return output.New(2, "Select a Draft with draft select NAME_OR_UUID or draft open first")
		}
		if json.Unmarshal(raw, &observed) != nil || observed.ResourceUID != resource.UID || observed.ResourceID != id || !uuidReference(observed.DraftID) {
			return output.New(9, "Draft observation belongs to another identity")
		}
		if action == "show" {
			data, err := request("GET", base+"/drafts/"+observed.DraftID, nil)
			if err != nil {
				return err
			}
			if err = saveObservation(data); err != nil {
				return err
			}
			return a.emit(data)
		}
	}
	if raw, err := c.ReadOperationalFile(pendingPath, 16<<20); err == nil {
		if !clearedASaCPending(raw) {
			return output.New(9, "A Draft write is unresolved; run draft reconcile before another write")
		}
	} else if !os.IsNotExist(err) {
		return output.New(2, err.Error())
	}
	capability, err := request("GET", fmt.Sprintf("/projects/%s/packages/capabilities", url.PathEscape(a.Project)), nil)
	if err != nil {
		return err
	}
	supported := packagefmt.Object(capability["asac"])
	if supported["schema_version"] != "1.0" || supported["isolated_drafts"] != true || supported["definition_digest_scope"] != devworkspace.PortableDefinitionScope {
		return output.New(9, "Server does not advertise compatible isolated Draft support")
	}
	op, err := a.nextASaCOperation()
	if err != nil {
		return err
	}
	payload := map[string]any{"operation_id": op}
	method, path := "POST", base+"/drafts"
	switch action {
	case "open":
		name := args[2]
		if from != "draft" && from != "staging" && from != "production" && from != "release" || from == "release" && version == "" || from != "release" && version != "" {
			return output.New(2, "Use draft/staging/production, or release with --version")
		}
		export := a.asacSourceExport
		if export == "" {
			captured, bundle, err := developmentCapture(cmd.Context(), client, kind, id, from, version)
			if err != nil {
				return err
			}
			bundle.Close()
			export = captured.ExportID
		}
		payload["resource_uid"], payload["name"], payload["source_export_id"] = resource.UID, name, export
	case "push":
		graph, err := devworkspace.LoadGraph(c)
		if err != nil {
			return output.New(2, err.Error())
		}
		requirements := state.Requirements
		if len(requirements) == 0 {
			tracking, err := c.ReadTracking(*resource)
			if err != nil {
				return output.New(2, err.Error())
			}
			requirements = tracking.Requirements
		}
		bundle, _, err := graph.Compile(resource.Key, requirements, state.Credentials)
		if err != nil {
			return output.New(2, err.Error())
		}
		defer bundle.Close()
		if a.asacArtifactDigest != "" && "sha256:"+bundle.ArtifactDigest != a.asacArtifactDigest {
			return output.New(6, "Author closure changed after deploy checkpoint; no Draft push attempted")
		}
		uploaded, err := client.Upload(cmd.Context(), bundle, false)
		if err != nil {
			return err
		}
		method, path = "PUT", base+"/drafts/"+observed.DraftID
		payload["expected_generation"], payload["upload_id"], payload["artifact_digest"] = observed.Generation, uploaded.UploadID, "sha256:"+bundle.ArtifactDigest
	case "checkpoint":
		record, err := c.ReadRevision(*resource, args[2])
		if err != nil {
			return output.New(9, err.Error())
		}
		if record.AuthorDigest != "" && supported["author_digest_declarations"] != true {
			return output.New(9, "Server does not support declared author digests; update the backend before registering this revision")
		}
		if !asacSupportsDefinition(supported, record.DefinitionScope) || record.DefinitionDigest != observed.Definition {
			return output.New(9, "Revision differs from the saved isolated Draft; push its exact content first")
		}
		graph, err := devworkspace.LoadGraph(c)
		if err != nil {
			return output.New(2, err.Error())
		}
		tracking, err := c.ReadTracking(*resource)
		if err != nil {
			return output.New(2, err.Error())
		}
		bundle, _, err := graph.Compile(resource.Key, tracking.Requirements, state.Credentials)
		if err != nil {
			return output.New(2, err.Error())
		}
		defer bundle.Close()
		definition, components, err := devworkspace.PortableDefinition(bundle)
		if err != nil {
			return output.New(2, err.Error())
		}
		if definition != record.DefinitionDigest || "sha256:"+bundle.ArtifactDigest != record.ArtifactDigest {
			return output.New(9, "YAML differs from the sealed revision; restore its exact object or create a new checkpoint")
		}
		uids := map[string]string{}
		for key := range components {
			node := graph.Nodes[key]
			if node == nil || record.Components[node.Resource.UID] != components[key] {
				return output.New(9, "Revision component identity differs from the local graph")
			}
			uids[key] = node.Resource.UID
		}
		providerUIDs := map[string]string{}
		providers, err := devworkspace.PortableProviderDigests(bundle)
		if err != nil {
			return err
		}
		for key, digest := range providers {
			if node := graph.Nodes[key]; node != nil && node.Resource.Kind == "Provider" {
				if record.Components[node.Resource.UID] != digest {
					return output.New(9, "Revision provider differs from captured intent")
				}
				providerUIDs[key] = node.Resource.UID
			}
		}
		if record.AuthorDigest != "" && supported["author_source_retention"] == true {
			source, err := c.ReadAuthorObject(*resource, record)
			if err != nil {
				return output.New(9, err.Error())
			}
			raw, err := json.Marshal(source)
			if err != nil {
				return err
			}
			authorUpload, err := client.UploadAuthor(cmd.Context(), raw, record.AuthorDigest, resource.UID)
			if err != nil {
				return err
			}
			payload["author_upload_id"] = authorUpload
		}
		path = base + "/revisions"
		payload["draft_id"], payload["expected_generation"], payload["record"], payload["component_uids"], payload["provider_uids"] = observed.DraftID, observed.Generation, record, uids, providerUIDs
	}
	proofDraft := observed.DraftID
	if action == "open" {
		proofDraft = ""
	}
	proofs, err := authoringLeaseProofs(c, state, resource.UID, id, proofDraft)
	if err != nil {
		return err
	}
	if len(proofs) > 0 {
		payload["leases"] = proofs
	}
	pending := asacPending{OperationID: op, Method: method, Path: path, Body: payload}
	raw, _ := json.Marshal(pending)
	if err = c.WriteOperationalFile(pendingPath, raw); err != nil {
		return output.New(10, "Cannot persist operation identity before write")
	}
	data, err := request(method, path, payload)
	if err != nil {
		normalized := output.Normalize(err)
		if normalized.Outcome == "rejected" || normalized.Outcome == "not_attempted" {
			if clearErr := c.WriteOperationalFile(pendingPath, []byte("{}")); clearErr != nil {
				return output.New(10, "Draft write was rejected; cannot clear its local observation")
			}
		}
		return err
	}
	if data["operation_id"] != op || data["write_outcome"] != "committed" {
		return output.New(9, "Draft write result is uncertain; run draft reconcile")
	}
	if action != "checkpoint" {
		if err = saveObservation(data); err != nil {
			return err
		}
	}
	if err = c.WriteOperationalFile(pendingPath, []byte("{}")); err != nil {
		return output.New(10, "Draft committed; run draft reconcile to repair its local receipt")
	}
	return a.emit(data)
}

func asacSupportsDefinition(capabilities map[string]any, scope string) bool {
	if !devworkspace.SupportedDefinitionScope(scope) {
		return false
	}
	if capabilities["definition_digest_scope"] == scope {
		return true
	}
	for _, item := range packagefmt.List(capabilities["definition_digest_scopes"]) {
		if item == scope {
			return true
		}
	}
	return false
}
