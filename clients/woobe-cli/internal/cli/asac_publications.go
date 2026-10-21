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

func validatePublicationAcceptance(data map[string]any, operation, id, uid, candidate, evaluation, record, runtime string) error {
	if err := devworkspace.ValidatePublicationReceipt(data); err != nil {
		return output.New(9, "Publication acceptance is uncertain; run draft reconcile: "+err.Error())
	}
	if data["operation_id"] != operation || data["resource_id"] != id || data["resource_uid"] != uid || data["candidate_id"] != candidate || data["evaluation_id"] != evaluation || data["record_digest"] != record || data["runtime_digest"] != runtime {
		return output.New(9, "Publication receipt differs from the original request; run draft reconcile")
	}
	return nil
}

func validatePublicationObservation(data map[string]any) error {
	if data["state"] == "published" {
		return devworkspace.ValidatePublicationReceipt(data)
	}
	return devworkspace.ValidatePublicationPreparation(data)
}

func (a *App) asacPublicationCommands() {
	for _, kind := range []string{"agent", "network"} {
		var notes string
		command := &cobra.Command{Use: "publication REFERENCE PUBLICATION_UUID [reconcile|cancel]", Short: "Inspect publication or explicitly resume/cancel a Network preparation", Args: cobra.RangeArgs(2, 3), Long: "Read exact Candidate publication provenance independently of Production. Network reconcile resumes the original accepted preparation with current authorization and binding checks; it never starts a second publication. Cancel seals an unfinished preparation and preserves already copied immutable Agent Releases. Mutations require --yes; cancellation requires --notes. After recovering an unresolved local publish, use draft reconcile to mirror its terminal receipt. Native UUID operations do not require project configuration.", RunE: func(cmd *cobra.Command, args []string) error {
			if !uuidReference(args[1]) {
				return output.New(2, "Use the Publication UUID returned by publish --candidate")
			}
			action := ""
			if len(args) == 3 {
				action = args[2]
			}
			if action != "" && (kind != "network" || (action != "reconcile" && action != "cancel")) {
				return output.New(2, "Only Network publication reconcile/cancel is supported")
			}
			if action != "" && !a.Yes && !a.DryRun {
				return output.New(2, "Publication recovery requires --yes")
			}
			if a.File != "" {
				return output.New(2, "Publication recovery does not accept --file")
			}
			if action == "cancel" && len(strings.TrimSpace(notes)) < 3 {
				return output.New(2, "Cancellation requires an audit reason in --notes")
			}
			if action != "cancel" && notes != "" {
				return output.New(2, "--notes applies only to cancellation")
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
			path := fmt.Sprintf("/projects/%s/%ss/%s/asac/publications/%s", url.PathEscape(a.Project), kind, url.PathEscape(id), url.PathEscape(args[1]))
			method := "GET"
			var body []byte
			if action != "" {
				method = "POST"
				path += "/" + action
				if action == "cancel" {
					body, _ = json.Marshal(map[string]any{"reason": notes})
				}
			}
			if a.DryRun {
				return a.emit(map[string]any{"method": method, "path": path, "executed": false, "production_changed": false})
			}
			control, err := a.client()
			if err != nil {
				return err
			}
			response, _, err := control.Request(cmd.Context(), method, path, nil, body)
			if err != nil {
				return err
			}
			data, err := developmentResponseData(response)
			if err != nil {
				return err
			}
			if err = validatePublicationObservation(data); err != nil {
				return output.New(9, err.Error())
			}
			if data["resource_id"] != id || data["publication_id"] != args[1] || data["project_id"] != a.Project || data["kind"] != strings.Title(kind) {
				return output.New(9, "Publication belongs to another resource or destination")
			}
			return a.emit(data)
		}}
		command.Flags().StringVar(&notes, "notes", "", "Audit reason for cancelling an unfinished Network publication")
		a.group("develop " + kind).AddCommand(command)
	}
}

// Only reads original acceptance and the current phase; never repeats a write.
func resolvePublicationAcceptance(request func(string, string, any) (map[string]any, error), base string, data map[string]any, operation, id, uid, candidate, evaluation, record, runtime, project, kind string) (map[string]any, error) {
	validate := func(value map[string]any) error {
		if err := validatePublicationObservation(value); err != nil {
			return output.New(9, "Publication acceptance is uncertain; run draft reconcile: "+err.Error())
		}
		if value["operation_id"] != operation || value["resource_id"] != id || value["resource_uid"] != uid || value["candidate_id"] != candidate || value["evaluation_id"] != evaluation || value["record_digest"] != record || value["runtime_digest"] != runtime || value["project_id"] != project || value["kind"] != kind {
			return output.New(9, "Publication receipt differs from the original request; run draft reconcile")
		}
		return nil
	}
	if err := validate(data); err != nil {
		return nil, err
	}
	if data["state"] == "preparing" {
		publication := packagefmt.Text(data["publication_id"])
		current, err := request("GET", base+"/publications/"+url.PathEscape(publication), nil)
		if err != nil {
			return nil, err
		}
		if err = validate(current); err != nil {
			return nil, err
		}
		if current["publication_id"] != publication {
			return nil, output.New(9, "Publication phase belongs to another original acceptance")
		}
		data = current
	}
	if data["state"] == "preparing" {
		return nil, output.New(9, "Network publication is accepted but unfinished. Inspect publication "+packagefmt.Text(data["publication_id"])+"; explicitly reconcile or cancel it, then run draft reconcile. Do not publish again")
	}
	return data, nil
}

func (a *App) publishASaCCandidate(cmd *cobra.Command, kind, reference, candidate, evaluation, reason string) error {
	if !uuidReference(candidate) || !uuidReference(evaluation) {
		return output.New(2, "Exact publication requires --candidate UUID and --evaluation UUID")
	}
	if len(strings.TrimSpace(reason)) < 3 {
		return output.New(2, "Supply a publication reason with --notes (at least three characters)")
	}
	if a.File != "" {
		return output.New(2, "Publication uses exact server Candidate and Evaluation evidence; omit --file")
	}
	if !a.Yes && !a.DryRun {
		return output.New(2, "Exact publication requires --yes")
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
		return output.New(2, "Recover the native binding before publication")
	}
	pendingPath := asacPrivatePath(c, state, resource.UID, "pending")
	if raw, readErr := c.ReadOperationalFile(pendingPath, 16<<20); readErr == nil {
		var prior asacPending
		if json.Unmarshal(raw, &prior) != nil || prior.OperationID != "" {
			return output.New(9, "An ASaC write is unresolved; run draft reconcile before publication")
		}
	} else if !os.IsNotExist(readErr) {
		return output.New(2, readErr.Error())
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
	protocol := packagefmt.Object(capabilities["asac"])
	supported := false
	for _, value := range packagefmt.List(protocol["candidate_publication_kinds"]) {
		if value == resource.Kind {
			supported = true
		}
	}
	if protocol["schema_version"] != "1.0" || !supported {
		return output.New(9, "Backend does not support exact Candidate publication for this kind; update it first")
	}
	frozen, err := request("GET", base+"/candidates/"+url.PathEscape(candidate), nil)
	if err != nil {
		return err
	}
	if frozen["state"] != "ready" || frozen["candidate_id"] != candidate || frozen["resource_id"] != id || frozen["resource_uid"] != resource.UID {
		return output.New(9, "Candidate is not ready or belongs to another resource")
	}
	if kind == "network" && frozen["runtime_digest_scope"] != "network-execution-runtime@2" {
		return output.New(9, "Network Candidate uses an older runtime scope; prepare and evaluate a new Candidate without rewriting old evidence")
	}
	qualified, err := request("GET", base+"/evaluations/"+url.PathEscape(evaluation), nil)
	if err != nil {
		return err
	}
	if qualified["state"] != "passed" || qualified["evaluation_id"] != evaluation || qualified["candidate_id"] != candidate || qualified["resource_id"] != id || qualified["record_digest"] != frozen["record_digest"] || qualified["runtime_digest"] != frozen["runtime_digest"] {
		return output.New(6, "Evaluation does not qualify this exact Candidate; inspect its original native Runs")
	}
	operation, err := a.nextASaCOperation()
	if err != nil {
		return err
	}
	body := map[string]any{"operation_id": operation, "candidate_id": candidate, "evaluation_id": evaluation, "reason": reason}
	path := base + "/publications"
	if a.DryRun {
		return a.emit(map[string]any{"method": "POST", "path": path, "body": body, "executed": false, "production_changed": false})
	}
	pendingBody := map[string]any{}
	for key, value := range body {
		pendingBody[key] = value
	}
	pendingBody["runtime_digest"] = frozen["runtime_digest"]
	raw, _ := json.Marshal(asacPending{OperationID: operation, RecordDigest: packagefmt.Text(frozen["record_digest"]), Method: "POST", Path: path, Body: pendingBody})
	if err = c.WriteOperationalFile(pendingPath, raw); err != nil {
		return output.New(10, "Cannot persist publication identity before acceptance")
	}
	receipt, err := request("POST", path, body)
	if err != nil {
		normalized := output.Normalize(err)
		if normalized.Outcome == "rejected" || normalized.Outcome == "not_attempted" {
			if clearErr := c.WriteOperationalFile(pendingPath, []byte("{}")); clearErr != nil {
				return output.New(10, "Publication rejected; its local receipt could not be cleared")
			}
		}
		return err
	}
	receipt, err = resolvePublicationAcceptance(request, base, receipt, operation, id, resource.UID, candidate, evaluation, packagefmt.Text(frozen["record_digest"]), packagefmt.Text(frozen["runtime_digest"]), a.Project, resource.Kind)
	if err != nil {
		return err
	}
	if receipt["state"] == "cancelled" {
		err = c.StorePublicationCancellation(*resource, strings.TrimRight(control.Base, "/"), a.Workspace, a.Project, receipt)
	} else {
		err = c.StorePublicationReceipt(*resource, strings.TrimRight(control.Base, "/"), a.Workspace, a.Project, receipt)
	}
	if err != nil {
		return output.New(10, "Terminal publication receipt is pending; run draft reconcile without publishing again: "+err.Error())
	}

	if err = c.WriteOperationalFile(pendingPath, []byte("{}")); err != nil {
		return output.New(10, "Published; run draft reconcile before another write")
	}
	return a.emit(receipt)
}
