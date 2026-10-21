package cli

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"strings"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/requestinput"
)

func (a *App) nextASaCOperation() (string, error) {
	if a.asacOperation != "" {
		return a.asacOperation, nil
	}
	return devworkspace.NewID()
}

// This typed result adapter keeps existing lifecycle validation and private
// pending receipts. It does not execute a Cobra command or parse console output.
func (a *App) captureASaCResult(operation string, call func() error) (map[string]any, error) {
	priorSink, priorID := a.asacResult, a.asacOperation
	defer func() { a.asacResult, a.asacOperation = priorSink, priorID }()
	var result map[string]any
	a.asacOperation = operation
	a.asacResult = func(value any) error {
		raw, err := json.Marshal(value)
		if err != nil {
			return err
		}
		decoder := json.NewDecoder(bytes.NewReader(raw))
		decoder.UseNumber()
		return decoder.Decode(&result)
	}
	err := call()
	return result, err
}

func readDeployDocument(path string) (map[string]any, string, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, "", output.New(2, "Cannot read deploy suite/smoke file")
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil || !info.Mode().IsRegular() || info.Size() > 1<<20 {
		return nil, "", output.New(2, "Deploy suite/smoke must be a bounded regular file (1 MiB)")
	}
	raw := make([]byte, info.Size())
	if _, err = file.ReadAt(raw, 0); err != nil {
		return nil, "", err
	}
	decoded, err := requestinput.Decode(raw, path, "auto")
	if err != nil {
		return nil, "", output.New(2, err.Error())
	}
	var data map[string]any
	decoder := json.NewDecoder(bytes.NewReader(decoded))
	decoder.UseNumber()
	if decoder.Decode(&data) != nil || data == nil {
		return nil, "", output.New(2, "Deploy input must be a YAML/JSON object")
	}
	digest := sha256.Sum256(raw)
	return data, fmt.Sprintf("sha256:%x", digest), nil
}

func (w *deployWorkflow) localWorkspace() (*devworkspace.Config, *devworkspace.State, *devworkspace.Resource, error) {
	c, err := w.app.developmentConfig(true)
	if err != nil {
		return nil, nil, nil, err
	}
	state, err := c.ReadState(w.intent.API, w.intent.Workspace, w.intent.Project)
	if err != nil {
		return nil, nil, nil, err
	}
	resource, err := developmentReference(c, state, strings.ToLower(w.intent.Kind), w.intent.Resource, "")
	if err != nil {
		return nil, nil, nil, err
	}
	id, err := asacRegisteredResourceID(c, state, resource)
	if err != nil || id != w.intent.Resource || state.Bindings[resource.UID].ResourceID != id {
		return nil, nil, nil, output.New(9, "Local deploy requires an existing accepted native binding; recover/reconcile explicitly before delivery")
	}
	return c, state, resource, nil
}

func (w *deployWorkflow) prepareLocal(write bool) error {
	suite, digest, err := readDeployDocument(w.intent.Request.Suite)
	if err != nil {
		return err
	}
	if err := validateEvaluationSuite(suite); err != nil {
		return err
	}
	if previous := w.intent.Local["suite_digest"]; previous != "" && previous != digest {
		return output.New(6, "Evaluation suite changed after deploy intent creation")
	}
	w.intent.Local["suite_digest"] = digest
	if w.intent.Request.ViaStaging {
		if _, err = w.smokeInput(); err != nil {
			return err
		}
	}
	cap, err := w.read(fmt.Sprintf("/projects/%s/packages/capabilities", url.PathEscape(w.intent.Project)), nil)
	if err != nil {
		return err
	}
	protocol := packagefmt.Object(cap["asac"])
	for _, key := range []string{"isolated_drafts", "candidate_preparation", "candidate_evaluation", "author_source_retention", "draft_source_preflight"} {
		if protocol[key] != true {
			return output.New(9, "Backend lacks local deploy capability: "+key)
		}
	}
	supported := false
	for _, kind := range packagefmt.List(protocol["candidate_publication_kinds"]) {
		supported = supported || kind == w.intent.Kind
	}
	if !supported {
		return output.New(9, "Backend does not support exact Publication for this target kind")
	}
	c, state, resource, err := w.localWorkspace()
	if err != nil {
		return err
	}
	unlock, err := c.Lock()
	if err != nil {
		return err
	}
	defer unlock()
	graph, err := devworkspace.LoadGraph(c)
	if err != nil {
		return output.New(2, err.Error())
	}
	nodes, err := graph.Closure(resource.Key)
	if err != nil {
		return output.New(2, err.Error())
	}
	packages, err := packageapi.New(w.client, w.intent.Project)
	if err != nil {
		return err
	}
	registry, err := packages.Registry(w.cmd.Context(), c.RegistryID)
	if err != nil {
		return err
	}
	_, stale, err := recoveredDevelopmentBindings(nodes, state, registry)
	if err != nil {
		return output.New(9, "Local deploy has no complete accepted native closure; inspect bindings recover --dry-run and establish it explicitly with managed push before delivery")
	}
	if stale != 0 {
		return output.New(6, "Accepted native bindings changed; explicitly inspect/recover the closure before a new delivery")
	}
	tracking, err := c.ReadTracking(*resource)
	if err != nil {
		return output.New(9, "Local deploy requires retained source custody; pull/recover explicitly first")
	}
	if w.intent.Local["registry_id"] != "" && (w.intent.Local["registry_id"] != c.RegistryID || w.intent.Local["resource_uid"] != resource.UID) {
		return output.New(6, "Local registry identity changed during deployment")
	}
	w.intent.Local["registry_id"], w.intent.Local["resource_uid"] = c.RegistryID, resource.UID
	// Preserve the previously accepted source. Opening an isolated line must
	// never silently recapture a different native Draft or adopt new bindings.
	export := state.Bindings[resource.UID].ExportID
	if !deployUUID.MatchString(export) {
		return output.New(9, "Local deploy requires the retained accepted source export; recover explicitly first")
	}
	if old := w.intent.Local["source_export_id"]; old != "" && old != export {
		return output.New(6, "Accepted local binding changed during deployment")
	}
	w.intent.Local["source_export_id"] = export
	if w.intent.Steps["draft-open"] == nil {
		if err := w.checkLocalOrigin(resource, export); err != nil {
			return err
		}
	}
	bundle, _, err := graph.Compile(resource.Key, tracking.Requirements, state.Credentials)
	if err != nil {
		return output.New(2, err.Error())
	}
	defer bundle.Close()
	content := "sha256:" + bundle.ArtifactDigest
	if previous := w.intent.Local["artifact_digest"]; previous != "" && previous != content {
		return output.New(6, "Local author changed after deploy checkpoint; restore exact source or create a new intent")
	}
	w.intent.Local["artifact_digest"] = content
	// A checkpoint can exist even when persisting the intent failed. Recognize
	// only this exact operation and artifact; its parents still need acceptance.
	message := "Deploy intent " + w.intent.ID + ": " + w.intent.Request.Notes
	record, parents, err := localDeployRevision(c, resource, tracking.Working, w.intent.Local["revision_id"], message, content)
	if err != nil {
		return err
	}
	if step := w.intent.Steps["revision-checkpoint"]; step == nil || step.State != "committed" {
		if err := w.checkLocalParents(c, resource, parents); err != nil {
			return err
		}
	}
	if !write {
		w.intent.Source = map[string]any{"mode": "local", "artifact_digest": content}
		return nil
	}
	if w.intent.Local["revision_id"] == "" {
		if record == nil {
			record, err = graph.CreateRevision(*resource, state, message, nil)
			if err != nil {
				return output.New(2, err.Error())
			}
		}
		w.intent.Local["revision_id"], w.intent.Local["record_digest"] = record.ID, record.RecordDigest
	}
	return w.save()
}

func (w *deployWorkflow) localStep(name string, call func() error) (map[string]any, error) {
	step := w.intent.Steps[name]
	if step != nil && step.State == "committed" {
		return step.Receipt, nil
	}
	if step != nil && step.State == "rejected" {
		return nil, output.New(6, "Local deployment step rejected; inspect state before a new intent")
	}
	fresh := step == nil
	if fresh {
		step = &deployStep{Operation: deployOperationID(w.intent, name), Method: "lifecycle", Path: w.base, State: "submitted"}
		w.intent.Steps[name] = step
		if err := w.save(); err != nil {
			return nil, err
		}
	}
	var receipt map[string]any
	var err error
	if fresh {
		receipt, err = w.app.captureASaCResult(step.Operation, call)
	} else {
		operation, readErr := w.read(w.base+"/operations/"+step.Operation, nil)
		if readErr != nil {
			return nil, &output.Error{Code: 9, Message: "Original local step is unobserved; restore/reconcile its original receipt, never repeat it", Outcome: "unknown"}
		}
		if operation["operation_id"] != step.Operation || operation["state"] != "committed" {
			return nil, &output.Error{Code: 9, Message: "Original lifecycle step remains unconfirmed; no replay permitted", Outcome: "unknown"}
		}
		receipt = packagefmt.Object(operation["result"])
		if name == "publication" && receipt["state"] == "preparing" && w.intent.Kind == "Network" {
			publication := packagefmt.Text(receipt["publication_id"])
			if !deployUUID.MatchString(publication) {
				return nil, output.New(9, "Original Network preparation omitted its identity")
			}
			current, observeErr := w.read(w.base+"/publications/"+publication, nil)
			if observeErr != nil {
				return nil, observeErr
			}
			if current["state"] == "preparing" {
				// Resume only the retained preparation, not the original publish.
				raw, _, reconcileErr := w.client.Request(w.cmd.Context(), "POST", w.base+"/publications/"+publication+"/reconcile", nil, nil)
				if reconcileErr != nil {
					return nil, reconcileErr
				}
				current, observeErr = developmentResponseData(raw)
				if observeErr != nil {
					return nil, observeErr
				}
			}
			if current["publication_id"] != publication || current["operation_id"] != step.Operation || current["resource_id"] != w.intent.Resource || current["project_id"] != w.intent.Project || current["kind"] != w.intent.Kind {
				return nil, output.New(9, "Network preparation belongs to another original Publication")
			}
			if validateErr := devworkspace.ValidatePublicationReceipt(current); validateErr != nil {
				return nil, output.New(9, "Original Network preparation is unfinished; resume the same deploy intent")
			}
			receipt = current
		}
		// Repair the existing per-resource documentary receipt before advancing.
		c, state, resource, workspaceErr := w.localWorkspace()
		if workspaceErr != nil {
			return nil, workspaceErr
		}
		pending, readErr := c.ReadOperationalFile(asacPrivatePath(c, state, resource.UID, "pending"), 16<<20)
		if readErr == nil && !clearedASaCPending(pending) {
			var original asacPending
			if decodeASaCPending(pending, &original) != nil || original.OperationID != step.Operation {
				return nil, output.New(9, "Another unresolved local operation requires explicit reconciliation")
			}
			_, err = w.app.captureASaCResult("", func() error {
				return w.app.runASaCDraft(w.cmd, strings.ToLower(w.intent.Kind), []string{w.intent.Resource, "reconcile"}, "draft", "", step.Operation)
			})
		} else if readErr != nil && !os.IsNotExist(readErr) {
			return nil, readErr
		}
	}
	if err != nil {
		failure := output.Normalize(err)
		if failure.Outcome == "rejected" || failure.Outcome == "not_attempted" {
			step.State = "rejected"
			w.intent.Status = "rejected_terminal"
		}
		_ = w.save()
		return nil, err
	}
	identityMatches := receipt != nil && receipt["resource_id"] == w.intent.Resource
	if name == "revision-checkpoint" {
		record := packagefmt.Object(receipt["record"])
		identityMatches = record["resource_uid"] == w.intent.Local["resource_uid"] && record["revision_id"] == w.intent.Local["revision_id"] && record["record_digest"] == w.intent.Local["record_digest"] && receipt["draft_id"] == w.intent.Local["draft_id"]
	}
	if receipt == nil || receipt["operation_id"] != step.Operation || !identityMatches || receipt["write_outcome"] != "committed" {
		return nil, output.New(9, "Local lifecycle "+name+" receipt differs from the original intent")
	}
	step.Receipt = receipt
	step.State = "committed"
	if err = w.save(); err != nil {
		return nil, err
	}
	return receipt, nil
}

func (w *deployWorkflow) observeUntil(path, field, id, terminal string) (map[string]any, error) {
	ctx, cancel := context.WithTimeout(w.cmd.Context(), w.app.Timeout)
	defer cancel()
	for {
		if err := ctx.Err(); err != nil {
			return nil, output.New(8, "Observation deadline exceeded; original operation remains retained")
		}
		data, err := w.read(path, nil)
		if err != nil {
			return nil, err
		}
		if data[field] != id || data["resource_id"] != w.intent.Resource || data["schema_version"] != "1.0" {
			return nil, output.New(9, "Lifecycle observation belongs to another target or original operation")
		}
		if data["state"] == terminal {
			return data, nil
		}
		if data["state"] == "failed" || data["state"] == "cancelled" {
			return nil, output.New(6, "Lifecycle preparation/evaluation failed; Production is unchanged")
		}
		if field == "evaluation_id" {
			raw, _, err := w.client.Request(ctx, "POST", path+"/reconcile", nil, nil)
			if err != nil {
				return nil, err
			}
			next, err := developmentResponseData(raw)
			if err != nil {
				return nil, err
			}
			if next[field] != id || next["resource_id"] != w.intent.Resource {
				return nil, output.New(9, "Reconciled evaluation identity mismatch")
			}
			if next["state"] == terminal {
				return next, nil
			}
			if next["state"] == "failed" {
				return nil, output.New(6, "Candidate evaluation failed; no publication or activation attempted")
			}
		}
		select {
		case <-ctx.Done():
			return nil, output.New(8, "Observation deadline exceeded; resume the original intent")
		case <-time.After(250 * time.Millisecond):
		}
	}
}

func (w *deployWorkflow) deliverLocal() error {
	if packagefmt.Text(w.intent.Source["release_id"]) != "" {
		return nil
	}
	if err := w.prepareLocal(true); err != nil {
		return err
	}
	kind, ref := strings.ToLower(w.intent.Kind), w.intent.Resource
	priorExport, priorArtifact := w.app.asacSourceExport, w.app.asacArtifactDigest
	defer func() { w.app.asacSourceExport, w.app.asacArtifactDigest = priorExport, priorArtifact }()
	w.app.asacSourceExport = w.intent.Local["source_export_id"]
	w.app.asacArtifactDigest = w.intent.Local["artifact_digest"]
	draft := func(action, name string) func() error {
		return func() error {
			args := []string{ref, action}
			if name != "" {
				args = append(args, name)
			}
			return w.app.runASaCDraft(w.cmd, kind, args, "draft", "", "")
		}
	}
	opened, err := w.localStep("draft-open", draft("open", "deploy-"+w.intent.ID))
	if err != nil {
		return err
	}
	w.intent.Local["draft_id"] = packagefmt.Text(opened["draft_id"])
	// An external selection must not redirect the remaining writes to another line.
	c, state, resource, err := w.localWorkspace()
	if err != nil {
		return err
	}
	raw, err := c.ReadOperationalFile(asacPrivatePath(c, state, resource.UID, "draft"), 1<<20)
	if err != nil {
		return err
	}
	var selected asacDraftObservation
	if json.Unmarshal(raw, &selected) != nil || selected.DraftID != w.intent.Local["draft_id"] {
		return output.New(6, "Selected isolated Draft changed; explicitly restore the original deploy Draft")
	}
	if _, err = w.localStep("draft-push", draft("push", "")); err != nil {
		return err
	}
	revision := w.intent.Local["revision_id"]
	if _, err = w.localStep("revision-checkpoint", draft("checkpoint", revision)); err != nil {
		return err
	}
	prepared, err := w.localStep("candidate", func() error { return w.app.stageASaCRevision(w.cmd, kind, ref, revision) })
	if err != nil {
		return err
	}
	candidate := packagefmt.Text(prepared["candidate_id"])
	if _, err = w.observeUntil(w.base+"/candidates/"+candidate, "candidate_id", candidate, "ready"); err != nil {
		return err
	}
	priorFile := w.app.File
	w.app.File = w.intent.Request.Suite
	evaluation, err := w.localStep("evaluation", func() error { return w.app.evaluateASaCCandidate(w.cmd, kind, ref, candidate) })
	w.app.File = priorFile
	if failure, ok := err.(*releaseTestFailure); ok {
		return failure.Cause
	}
	if err != nil {
		return err
	}
	evaluated := packagefmt.Text(evaluation["evaluation_id"])
	if _, err = w.observeUntil(w.base+"/evaluations/"+evaluated, "evaluation_id", evaluated, "passed"); err != nil {
		return err
	}
	publication, err := w.localStep("publication", func() error {
		return w.app.publishASaCCandidate(w.cmd, kind, ref, candidate, evaluated, w.intent.Request.Notes)
	})
	if err != nil {
		// Network Publication has its own resumable preparation. Explicit resume
		// may advance that original preparation, never submit another Publication.
		step := w.intent.Steps["publication"]
		if step != nil && step.State == "submitted" {
			operation, readErr := w.read(w.base+"/operations/"+step.Operation, nil)
			if readErr == nil && operation["state"] == "committed" {
				accepted := packagefmt.Object(operation["result"])
				if accepted["state"] == "preparing" && w.intent.Kind == "Network" {
					w.intent.Local["publication_id"] = packagefmt.Text(accepted["publication_id"])
					w.intent.Status = "publication_preparing"
					_ = w.save()
					publication, err = w.localStep("publication", func() error { return output.New(9, "Never resubmit an accepted Publication") })
				}
			}
		}
		if err != nil {
			return err
		}
	}
	if err = devworkspace.ValidatePublicationReceipt(publication); err != nil {
		return output.New(9, err.Error())
	}
	w.intent.Source = map[string]any{"mode": "local", "release_id": publication["release_id"], "publication_id": publication["publication_id"], "revision_id": revision, "record_digest": publication["record_digest"]}
	return w.save()
}

// Environment smoke is deliberately distinct from a Candidate evaluation suite.
// Its execution/recovery lives in deployment_smoke.go.
