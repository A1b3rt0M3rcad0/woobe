package cli

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/spf13/cobra"
)

const candidateEvaluationHelp = " With --candidate UUID, read a versioned YAML suite containing schema_version: '1.0', suite_id, suite_version, dataset_version and 1–16 cases with id, message, optional external_context and expected_output. Evaluate that exact ready Candidate, independently of current YAML or environments. Do not combine --candidate with --env or --version. Acceptance is not qualification: inspect evaluation UUID. A lost acceptance must use draft reconcile before another write; evaluation UUID reconcile --yes reads original Runs without executing another case. Neither testing nor reconciliation publishes or changes Production."

func validateEvaluationAcceptance(data map[string]any, operation, resource, candidate, record, runtime string) error {
	if data["schema_version"] != "1.0" || data["operation_id"] != operation || data["resource_id"] != resource || data["candidate_id"] != candidate || data["record_digest"] != record || data["runtime_digest"] != runtime || data["write_outcome"] != "committed" || data["state"] != "accepted" || !uuidReference(packagefmt.Text(data["evaluation_id"])) || data["published"] != false || data["production_changed"] != false {
		return output.New(9, "Evaluation acceptance is uncertain; run draft reconcile for the original operation")
	}
	return nil
}

func (a *App) asacEvaluationCommands() {
	for _, kind := range []string{"agent", "network"} {
		command := &cobra.Command{Use: "evaluation REFERENCE EVALUATION_UUID [reconcile]", Short: "Inspect or reconcile original Candidate execution evidence", Args: cobra.RangeArgs(2, 3), Long: "Read the evaluation ledger. The optional reconcile action reads original native Runs and saves qualification; it never executes another case, calls providers, publishes a Release or changes Production.", RunE: func(cmd *cobra.Command, args []string) error {
			if !uuidReference(args[1]) {
				return output.New(2, "Use the Evaluation UUID returned by test --candidate")
			}
			method := "GET"
			if len(args) == 3 {
				if args[2] != "reconcile" {
					return output.New(2, "Use evaluation REFERENCE UUID [reconcile]")
				}
				method = "POST"
				if !a.Yes && !a.DryRun {
					return output.New(2, "Evaluation reconciliation requires --yes")
				}
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
			path := fmt.Sprintf("/projects/%s/%ss/%s/asac/evaluations/%s", url.PathEscape(a.Project), kind, url.PathEscape(id), url.PathEscape(args[1]))
			if method == "POST" {
				path += "/reconcile"
			}
			if a.DryRun {
				return a.emit(map[string]any{"method": method, "path": path, "executed": false})
			}
			control, err := a.client()
			if err != nil {
				return err
			}
			response, _, err := control.Request(cmd.Context(), method, path, nil, nil)
			if err != nil {
				return err
			}
			data, err := developmentResponseData(response)
			if err != nil {
				return err
			}
			if data["schema_version"] != "1.0" || data["resource_id"] != id || data["evaluation_id"] != args[1] {
				return output.New(9, "Evaluation response belongs to another resource or protocol")
			}
			return a.emitEvaluation(data)
		}}
		a.group("develop " + kind).AddCommand(command)
	}
	var candidate string
	command := &cobra.Command{Use: "test REFERENCE --candidate UUID --file SUITE.yaml", Short: "Evaluate a ready Network Candidate with a versioned YAML suite", Long: candidateEvaluationHelp, Example: "woobe network '@helpdesk' test --candidate CANDIDATE_UUID --file suite.yaml --yes\nwoobe network '@helpdesk' evaluation EVALUATION_UUID", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
		return a.evaluateASaCCandidate(cmd, "network", args[0], candidate)
	}}
	command.Flags().StringVar(&candidate, "candidate", "", "Ready Candidate UUID (required)")
	_ = command.MarkFlagRequired("candidate")
	a.group("develop network").AddCommand(command)
}

func (a *App) emitEvaluation(data map[string]any) error {
	if data["state"] == "failed" {
		return &releaseTestFailure{Data: data, Cause: output.New(6, "Candidate evaluation failed; inspect cases and native Run evidence")}
	}
	return a.emit(data)
}

// Persist the original write identity before executing. Never repeat an unknown
// request or infer qualification from the immutable acceptance receipt.
func (a *App) evaluateASaCCandidate(cmd *cobra.Command, kind, reference, candidate string) error {
	if !uuidReference(candidate) {
		return output.New(2, "--candidate requires a ready Candidate UUID")
	}
	if !a.Yes && !a.DryRun {
		return output.New(2, "Candidate evaluation requires --yes")
	}
	raw, err := a.body(true)
	if err != nil {
		return err
	}
	if len(raw) > 1<<20 {
		return output.New(2, "Evaluation suite exceeds 1 MiB")
	}
	var suite map[string]any
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	if decoder.Decode(&suite) != nil {
		return output.New(2, "Evaluation suite must be a YAML/JSON object")
	}
	if err := validateEvaluationSuite(suite); err != nil {
		return err
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
		return output.New(2, "Recover the native binding before evaluation")
	}
	pendingPath := asacPrivatePath(c, state, resource.UID, "pending")
	if raw, readErr := c.ReadOperationalFile(pendingPath, 16<<20); readErr == nil {
		if !clearedASaCPending(raw) {
			return output.New(9, "An ASaC write is unresolved; run draft reconcile before another evaluation")
		}
	} else if !os.IsNotExist(readErr) {
		return output.New(2, readErr.Error())
	}
	base := fmt.Sprintf("/projects/%s/%ss/%s/asac", url.PathEscape(a.Project), kind, url.PathEscape(id))
	request := func(method, path string, body []byte) (map[string]any, error) {
		response, _, requestErr := control.Request(cmd.Context(), method, path, nil, body)
		if requestErr != nil {
			return nil, requestErr
		}
		return developmentResponseData(response)
	}
	capabilities, err := request("GET", fmt.Sprintf("/projects/%s/packages/capabilities", url.PathEscape(a.Project)), nil)
	if err != nil {
		return err
	}
	protocol := packagefmt.Object(capabilities["asac"])
	if protocol["schema_version"] != "1.0" || protocol["candidate_evaluation"] != true {
		return output.New(9, "Backend does not support exact Candidate evaluation; update it first")
	}
	observed, err := request("GET", base+"/candidates/"+url.PathEscape(candidate), nil)
	if err != nil {
		return err
	}
	if observed["candidate_id"] != candidate || observed["resource_id"] != id || observed["resource_uid"] != resource.UID || observed["state"] != "ready" || packagefmt.Text(observed["record_digest"]) == "" || packagefmt.Text(observed["runtime_digest"]) == "" {
		return output.New(9, "Candidate is not ready or belongs to another logical resource")
	}
	operation, err := a.nextASaCOperation()
	if err != nil {
		return err
	}
	payload := map[string]any{"operation_id": operation, "suite": suite}
	path := base + "/candidates/" + url.PathEscape(candidate) + "/evaluations"
	if a.DryRun {
		return a.emit(map[string]any{"method": "POST", "path": path, "body": payload, "executed": false, "production_changed": false, "published": false})
	}
	raw, _ = json.Marshal(asacPending{OperationID: operation, RecordDigest: packagefmt.Text(observed["record_digest"]), Method: "POST", Path: path, Body: map[string]any{"operation_id": operation, "suite": suite, "candidate_id": candidate, "runtime_digest": observed["runtime_digest"]}})
	if err = c.WriteOperationalFile(pendingPath, raw); err != nil {
		return output.New(10, "Cannot persist Evaluation operation identity before acceptance")
	}
	raw, _ = json.Marshal(payload)
	receipt, err := request("POST", path, raw)
	if err != nil {
		normalized := output.Normalize(err)
		if normalized.Outcome == "rejected" || normalized.Outcome == "not_attempted" {
			if err = c.WriteOperationalFile(pendingPath, []byte("{}")); err != nil {
				return output.New(10, "Evaluation rejected; its local receipt could not be cleared")
			}
		}
		return err
	}
	if err = validateEvaluationAcceptance(receipt, operation, id, candidate, packagefmt.Text(observed["record_digest"]), packagefmt.Text(observed["runtime_digest"])); err != nil {
		return err
	}
	raw, _ = json.Marshal(receipt)
	if err = c.WriteOperationalFile(asacPrivatePath(c, state, resource.UID, "evaluation"), raw); err != nil {
		return output.New(10, "Evaluation accepted; run draft reconcile to save its original receipt")
	}
	if err = c.WriteOperationalFile(pendingPath, []byte("{}")); err != nil {
		return output.New(10, "Evaluation accepted; run draft reconcile before another write")
	}
	data, err := request("GET", base+"/evaluations/"+url.PathEscape(packagefmt.Text(receipt["evaluation_id"])), nil)
	if err != nil {
		return err
	}
	if data["evaluation_id"] != receipt["evaluation_id"] || data["resource_id"] != id || data["candidate_id"] != candidate || data["record_digest"] != receipt["record_digest"] || data["runtime_digest"] != receipt["runtime_digest"] {
		return output.New(9, "Evaluation evidence differs from its original acceptance")
	}
	return a.emitEvaluation(data)
}
