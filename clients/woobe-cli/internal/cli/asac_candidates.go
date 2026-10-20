package cli

import (
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/spf13/cobra"
)

func candidateBindings(requirements map[string]any, credentials map[string]string) (map[string]any, error) {
	spec := map[string]any{}
	for _, group := range []string{"credentials", "project_environment", "secrets", "knowledge"} {
		values := map[string]any{}
		for _, raw := range packagefmt.List(requirements[group]) {
			item := packagefmt.Object(raw)
			field := "ref"
			if group == "project_environment" {
				field = "key"
			}
			alias := packagefmt.Text(item[field])
			if alias == "" {
				return nil, output.New(9, "Retained object contains an invalid destination requirement")
			}
			switch group {
			case "credentials":
				if !uuidReference(credentials[alias]) {
					return nil, output.New(2, "Bind the retained provider "+alias+" before Stage; no credentials are inferred from current YAML")
				}
				values[alias] = map[string]any{"credential_id": credentials[alias]}
			case "knowledge":
				return nil, output.New(2, "Stage needs a closed portable Knowledge object; retained Knowledge references require explicit binding")
			default:
				values[alias] = map[string]any{"existing_key": alias}
			}
		}
		spec[group] = values
	}
	return map[string]any{"format": "woobe-package", "schema_version": "1.0", "kind": "ImportBindings",
		"metadata": map[string]any{"name": "Candidate"}, "spec": spec}, nil
}

func candidateManifestBindings(manifest map[string]any, credentials map[string]string) (map[string]any, error) {
	spec := packagefmt.Object(manifest["spec"])
	requirements := packagefmt.Object(spec["requires"])
	if manifest["schema_version"] != "2.0" {
		return candidateBindings(requirements, credentials)
	}
	connections := []any{}
	for alias := range packagefmt.Object(spec["connections"]) {
		connections = append(connections, map[string]any{"ref": alias})
	}
	bindings, err := candidateBindings(map[string]any{"credentials": connections,
		"project_environment": packagefmt.List(packagefmt.Object(spec["configuration"])["keys"]), "knowledge": requirements["knowledge"]}, credentials)
	if err != nil {
		return nil, err
	}
	bindings["schema_version"] = "2.0"
	delete(packagefmt.Object(bindings["spec"]), "secrets")
	for _, group := range []string{"credentials", "project_environment"} {
		for _, raw := range packagefmt.Object(packagefmt.Object(bindings["spec"])[group]) {
			packagefmt.Object(raw)["create"] = false
		}
	}
	return bindings, nil
}

func (a *App) asacCandidateCommands() {
	for _, kind := range []string{"agent", "network"} {
		command := &cobra.Command{Use: "candidate REFERENCE CANDIDATE_UUID", Short: "Inspect exact isolated preparation without selecting an environment", Args: cobra.ExactArgs(2),
			Long: "Read the current Candidate preparation state. A ready Candidate is frozen executable evidence; it is not an Evaluation, published Release or Production selection.",
			RunE: func(cmd *cobra.Command, args []string) error {
				if !uuidReference(args[1]) {
					return output.New(2, "Use the Candidate UUID returned by Stage")
				}
				id, err := a.nativeReference(kind+"_id", args[0])
				if err != nil {
					return err
				}
				if err = resourceID(id); err != nil {
					return err
				}
				if _, err = a.resolve(); err != nil {
					return err
				}
				path := fmt.Sprintf("/projects/%s/%ss/%s/asac/candidates/%s", url.PathEscape(a.Project), kind, url.PathEscape(id), url.PathEscape(args[1]))
				if a.DryRun {
					return a.emit(map[string]any{"method": "GET", "path": path, "executed": false})
				}
				control, err := a.client()
				if err != nil {
					return err
				}
				response, _, err := control.Request(cmd.Context(), "GET", path, nil, nil)
				if err != nil {
					return err
				}
				data, err := developmentResponseData(response)
				if err != nil {
					return err
				}
				if data["candidate_id"] != args[1] || data["resource_id"] != id || data["schema_version"] != "1.0" {
					return output.New(9, "Candidate response belongs to another resource or protocol")
				}
				return a.emit(data)
			}}
		a.group("develop " + kind).AddCommand(command)
	}
}

func validateCandidateAcceptance(data map[string]any, operation, id, uid, revision, draft, recordDigest string) error {
	if data["operation_id"] != operation || data["write_outcome"] != "committed" || data["resource_id"] != id ||
		data["resource_uid"] != uid || data["revision_id"] != revision || data["record_digest"] != recordDigest || data["draft_id"] != draft ||
		!uuidReference(packagefmt.Text(data["candidate_id"])) || !uuidReference(packagefmt.Text(data["preparation_operation_id"])) ||
		data["state"] != "preparing" || data["published"] != false || data["production_changed"] != false {
		return output.New(9, "Candidate acceptance is uncertain; run draft reconcile for the original operation")
	}
	return nil
}

// Stage reads the immutable executable object and selected remote Draft only.
// It must remain independent of subsequent edits to local author descriptors.
func (a *App) stageASaCRevision(cmd *cobra.Command, kind, reference, revision string) error {
	if a.File != "" {
		return output.New(2, "Stage uses the sealed revision object; --file does not update its Source")
	}
	if !a.Yes && !a.DryRun {
		return output.New(2, "Candidate preparation requires --yes")
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
	state, err := c.ReadState(strings.TrimRight(control.Base, "/"), a.Workspace, a.Project)
	if err != nil {
		return output.New(2, err.Error())
	}
	resource, err := developmentReference(c, state, kind, reference, "")
	if err != nil {
		return err
	}
	id := state.Bindings[resource.UID].ResourceID
	if !uuidReference(id) {
		return output.New(2, "Recover the native binding before Stage")
	}
	pendingPath := asacPrivatePath(c, state, resource.UID, "pending")
	if raw, readErr := c.ReadOperationalFile(pendingPath, 16<<20); readErr == nil {
		if !clearedASaCPending(raw) {
			return output.New(9, "An ASaC write is unresolved; run draft reconcile before preparing another candidate")
		}
	} else if !os.IsNotExist(readErr) {
		return output.New(2, readErr.Error())
	}
	raw, err := c.ReadOperationalFile(asacPrivatePath(c, state, resource.UID, "draft"), 16<<20)
	if err != nil {
		return output.New(2, "Select and checkpoint an isolated remote Draft before Stage")
	}
	var selected asacDraftObservation
	if json.Unmarshal(raw, &selected) != nil || selected.ResourceID != id || selected.ResourceUID != resource.UID || !uuidReference(selected.DraftID) {
		return output.New(9, "Selected Draft belongs to another destination or logical resource")
	}
	record, err := c.ReadRevision(*resource, revision)
	if err != nil {
		return output.New(9, err.Error())
	}
	bundle, err := c.OpenExecutableObject(*resource, *record)
	if err != nil {
		return output.New(9, "Verify or hydrate the sealed revision object before Stage: "+err.Error())
	}
	defer bundle.Close()
	bindings, err := candidateManifestBindings(bundle.Graph.Manifest, state.Credentials)
	if err != nil {
		return err
	}
	request := func(method, path string, body any) (map[string]any, error) {
		var encoded []byte
		if body != nil {
			encoded, err = json.Marshal(body)
			if err != nil {
				return nil, err
			}
		}
		response, _, requestErr := control.Request(cmd.Context(), method, path, nil, encoded)
		if requestErr != nil {
			return nil, requestErr
		}
		return developmentResponseData(response)
	}
	base := fmt.Sprintf("/projects/%s/%ss/%s/asac", url.PathEscape(a.Project), kind, url.PathEscape(id))
	capabilities, err := request("GET", fmt.Sprintf("/projects/%s/packages/capabilities", url.PathEscape(a.Project)), nil)
	if err != nil {
		return err
	}
	supported := packagefmt.Object(capabilities["asac"])
	if supported["candidate_preparation"] != true || supported["schema_version"] != "1.0" {
		return output.New(9, "Backend does not support isolated Candidate preparation; update it before Stage --revision")
	}
	if record.DefinitionScope == devworkspace.ConfigurationDefinitionScope && !asacSupportsDefinition(supported, record.DefinitionScope) {
		return output.New(9, "Backend does not advertise configuration-aware Candidate definitions; update Woobe before Stage")
	}
	remote, err := request("GET", base+"/drafts/"+url.PathEscape(selected.DraftID), nil)
	if err != nil {
		return err
	}
	if remote["resource_id"] != id || remote["resource_uid"] != resource.UID || remote["draft_id"] != selected.DraftID ||
		fmt.Sprint(remote["generation"]) != fmt.Sprint(selected.Generation) || remote["working_revision_id"] != revision || remote["definition_digest"] != record.DefinitionDigest {
		return output.New(6, "Remote Draft changed or does not select this sealed revision; inspect, push and checkpoint explicitly")
	}
	registered, err := request("GET", base+"/revisions/"+url.PathEscape(revision), nil)
	if err != nil {
		return err
	}
	var remoteRecord devworkspace.Revision
	encoded, _ := json.Marshal(registered["record"])
	if json.Unmarshal(encoded, &remoteRecord) != nil || devworkspace.ValidateRemoteRevision(*resource, remoteRecord) != nil || remoteRecord.RecordDigest != record.RecordDigest {
		return output.New(9, "Remote registered revision differs from the verified local record")
	}
	op, err := a.nextASaCOperation()
	if err != nil {
		return err
	}
	payload := map[string]any{"operation_id": op, "draft_id": selected.DraftID, "expected_generation": selected.Generation,
		"revision_id": revision, "registry_id": c.RegistryID, "bindings": bindings}
	if a.DryRun {
		return a.emit(map[string]any{"revision_id": revision, "draft_id": selected.DraftID,
			"expected_generation": selected.Generation, "candidate_prepared": false, "executed": false, "production_changed": false, "published": false})
	}
	path := base + "/candidates"
	encoded, _ = json.Marshal(asacPending{RecordDigest: record.RecordDigest, OperationID: op, Method: "POST", Path: path, Body: payload})
	if err = c.WriteOperationalFile(pendingPath, encoded); err != nil {
		return output.New(10, "Cannot persist Stage operation identity before acceptance")
	}
	data, err := request("POST", path, payload)
	if err != nil {
		normalized := output.Normalize(err)
		if normalized.Outcome == "rejected" || normalized.Outcome == "not_attempted" {
			if clearErr := c.WriteOperationalFile(pendingPath, []byte("{}")); clearErr != nil {
				return output.New(10, "Stage rejected; its local receipt could not be cleared")
			}
		}
		return err
	}
	if err = validateCandidateAcceptance(data, op, id, resource.UID, revision, selected.DraftID, record.RecordDigest); err != nil {
		return err
	}
	encoded, _ = json.Marshal(data)
	if err = c.WriteOperationalFile(asacPrivatePath(c, state, resource.UID, "candidate"), encoded); err != nil {
		return output.New(10, "Stage accepted; run draft reconcile to save its Candidate receipt")
	}
	if err = c.WriteOperationalFile(pendingPath, []byte("{}")); err != nil {
		return output.New(10, "Stage accepted; run draft reconcile before another write")
	}
	return a.emit(data)
}
