package cli

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/spf13/cobra"
)

type deployOptions struct {
	Source, Environment, Release, Publication, Notes, Action, Intent, Checkpoint, Suite, Smoke string
	ViaStaging, PlanOnly                                                                       bool
	Expected                                                                                   int64
}

var deployUUID = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)

type deployStep struct {
	Operation string         `json:"operation_id"`
	Method    string         `json:"method"`
	Path      string         `json:"path"`
	Body      map[string]any `json:"body,omitempty"`
	State     string         `json:"state"`
	Receipt   map[string]any `json:"receipt,omitempty"`
}
type deployIntent struct {
	Version                                            string `json:"schema_version"`
	ID                                                 string `json:"intent_id"`
	API, Workspace, Project, Kind, Resource, Principal string
	Request                                            deployOptions          `json:"request"`
	Status                                             string                 `json:"status"`
	Source                                             map[string]any         `json:"source"`
	Steps                                              map[string]*deployStep `json:"steps"`
	Local                                              map[string]string      `json:"local,omitempty"`
}
type deployWorkflow struct {
	app    *App
	cmd    *cobra.Command
	client *controlplane.Client
	store  *packagecheckpoint.Store
	intent *deployIntent
	base   string
}

func deployOperationID(intent *deployIntent, step string) string {
	raw, _ := json.Marshal([]string{"woobe-deploy-intent@1", intent.API, intent.Workspace, intent.Project, intent.Kind, intent.Resource, intent.ID, step})
	hash := sha256.Sum256(raw)
	hash[6] = hash[6]&0x0f | 0x50
	hash[8] = hash[8]&0x3f | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", hash[:4], hash[4:6], hash[6:8], hash[8:10], hash[10:16])
}

func (a *App) unifiedDeployCommands() {
	for _, kind := range []string{"agent", "network"} {
		opts := deployOptions{}
		cmd := &cobra.Command{Use: "deploy REFERENCE [status|resume|inspect]", Short: "Deploy an exact qualified Release, promote Staging or deliver local ASaC", Args: cobra.RangeArgs(1, 2),
			Long:    "Use --from release with --release UUID, --from staging to capture its exact qualified selection, or --from local with --suite FILE. Activation requires --notes and --yes. Local delivery first verifies target capture and remotely accepted revision parents (requires backend draft_source_preflight); preserve edits and explicitly recover stale sources or unaccepted ancestors. It uses an isolated Draft, immutable revision, exact Candidate, passed Evaluation and Publication; it never imports or activates arbitrary YAML. --plan-only and --dry-run are read-only preflights, not server qualification. A private intent journal retains original operations before writes. status reads the journal; resume reconciles originals before advancing and requires --yes. Native UUIDs need no .woobe-config. Preserve --checkpoint privately between CI attempts: missing state never authorizes replay. inspect reads the remote environment. Legacy deployment/activate/rollback commands keep their semantics.",
			Example: "woobe agent AGENT_UUID deploy --from release --release RELEASE_UUID --notes 'Approved release' --yes\nwoobe network '@support' deploy --from staging --notes 'Promote tested selection' --yes\nwoobe agent '@support' deploy --from local --suite tests/evaluation.yaml --notes 'Deliver author changes' --yes\nwoobe agent AGENT_UUID deploy resume --intent INTENT_UUID --yes",
			RunE:    func(cmd *cobra.Command, args []string) error { return a.runUnifiedDeploy(cmd, kind, args, opts) },
		}
		f := cmd.Flags()
		f.StringVar(&opts.Source, "from", "", "Required source: release, staging or local")
		f.StringVar(&opts.Environment, "env", "production", "Destination: staging or production")
		f.StringVar(&opts.Release, "release", "", "Exact qualified Release UUID (only --from release)")
		f.StringVar(&opts.Publication, "publication", "", "Exact Publication UUID (only --from release)")
		f.StringVar(&opts.Notes, "notes", "", "Audit reason, at least three characters")
		f.StringVar(&opts.Action, "action", "activate", "activate or rollback; rollback requires an explicit Release")
		f.StringVar(&opts.Intent, "intent", "", "Stable intent UUID; reuse only with the original private journal")
		f.StringVar(&opts.Checkpoint, "checkpoint", "", "Private journal path; retain securely across CI attempts")
		f.StringVar(&opts.Suite, "suite", "", "Versioned Candidate evaluation YAML for local delivery")
		f.StringVar(&opts.Smoke, "smoke", "", "Explicit Runtime smoke YAML for --via-staging")
		f.BoolVar(&opts.ViaStaging, "via-staging", false, "Deploy the same local Release to Staging and verify --smoke before Production")
		f.BoolVar(&opts.PlanOnly, "plan-only", false, "Read-only source/capability preflight; no plan, lease, provider call or activation")
		f.Int64Var(&opts.Expected, "expect-generation", -1, "Require this exact destination generation")
		a.group("develop " + kind).AddCommand(cmd)
	}
}

func validateDeployOptions(a *App, verb string, opts deployOptions) error {
	if a.File != "" || a.IfMatch != "" || a.IdempotencyKey != "" || len(a.Query) > 0 {
		return output.New(2, "Deploy owns its exact payloads; omit --file, --query, --if-match and --idempotency-key")
	}
	if opts.Environment != "production" && opts.Environment != "staging" {
		return output.New(2, "Deploy environment must be staging or production")
	}
	if opts.Intent != "" {
		if !deployUUID.MatchString(opts.Intent) {
			return output.New(2, "--intent requires a UUID")
		}
	}
	if verb != "" {
		if verb != "status" && verb != "resume" && verb != "inspect" {
			return output.New(2, "Use deploy [status|resume|inspect]")
		}
		if opts.Source != "" || opts.Release != "" || opts.Publication != "" || opts.Suite != "" || opts.Smoke != "" || opts.ViaStaging || opts.Notes != "" || opts.PlanOnly || opts.Expected != -1 || opts.Action != "activate" {
			return output.New(2, "Recovery uses the frozen intent; omit source and activation flags")
		}
		if verb != "inspect" && opts.Intent == "" {
			return output.New(2, "status/resume requires the original --intent UUID")
		}
		if verb == "resume" && (!a.Yes || a.DryRun) {
			return output.New(2, "Resuming requires --yes and explicit execution")
		}
		return nil
	}
	if opts.Expected < -1 || len(strings.TrimSpace(opts.Notes)) < 3 || len(opts.Notes) > 2000 || (opts.Action != "activate" && opts.Action != "rollback") {
		return output.New(2, "Deploy requires meaningful --notes (3–2000 characters), a valid action and nonnegative generation")
	}
	if opts.Action == "rollback" && (opts.Source != "release" || opts.Environment != "production") {
		return output.New(2, "Rollback requires --from release and --env production")
	}
	switch opts.Source {
	case "release":
		if !deployUUID.MatchString(opts.Release) {
			return output.New(2, "--from release requires --release UUID")
		}
	case "staging":
		if opts.Environment == "staging" || opts.Release != "" || opts.Publication != "" {
			return output.New(2, "--from staging promotes the captured Release to Production; omit --release/--publication")
		}
	case "local":
		if opts.Suite == "" || opts.Release != "" || opts.Publication != "" {
			return output.New(2, "--from local requires --suite FILE and no --release/--publication")
		}
	default:
		return output.New(2, "Supply --from release, staging or local")
	}
	if opts.Publication != "" {
		if !deployUUID.MatchString(opts.Publication) {
			return output.New(2, "--publication requires a UUID")
		}
	}
	if opts.Source != "local" && (opts.Suite != "" || opts.Smoke != "" || opts.ViaStaging) {
		return output.New(2, "--suite/--smoke/--via-staging apply only to local delivery")
	}
	if opts.ViaStaging && (opts.Smoke == "" || opts.Environment != "production") || !opts.ViaStaging && opts.Smoke != "" {
		return output.New(2, "--via-staging requires --smoke FILE and Production destination")
	}
	if !opts.PlanOnly && !a.DryRun && !a.Yes {
		return output.New(2, "Activation requires --yes")
	}
	return nil
}

func (a *App) runUnifiedDeploy(cmd *cobra.Command, kind string, args []string, opts deployOptions) error {
	verb := ""
	if len(args) == 2 {
		verb = args[1]
	}
	if err := validateDeployOptions(a, verb, opts); err != nil {
		return err
	}
	opts.Intent, opts.Release, opts.Publication = strings.ToLower(opts.Intent), strings.ToLower(opts.Release), strings.ToLower(opts.Publication)
	id, err := a.nativeReference(kind+"_id", args[0])
	if err != nil {
		return err
	}
	if !deployUUID.MatchString(id) {
		return output.New(2, "Deploy requires a native UUID or an unambiguous registered @alias/path")
	}
	id = strings.ToLower(id)
	control, err := a.client()
	if err != nil {
		return err
	}
	if a.Project == "" {
		return output.New(2, "Select a Project before deployment")
	}
	a.Project, a.Workspace = strings.ToLower(a.Project), strings.ToLower(a.Workspace)
	w := &deployWorkflow{app: a, cmd: cmd, client: control, base: fmt.Sprintf("/projects/%s/%ss/%s/asac", url.PathEscape(a.Project), kind, url.PathEscape(id))}
	if verb == "inspect" {
		current, err := w.current(opts.Environment)
		if err != nil {
			return err
		}
		return a.emit(current)
	}
	cap, err := w.read(fmt.Sprintf("/projects/%s/packages/capabilities", url.PathEscape(a.Project)), nil)
	if err != nil {
		return err
	}
	protocol := packagefmt.Object(cap["asac"])
	if protocol["schema_version"] != "1.0" || protocol["fenced_deployment"] != true || protocol["operation_environment_reads"] != true || protocol["deployment_scope"] != "exact-release-owner-selection@1" || protocol["operation_leases"] != true || protocol["lease_clock"] != "database" || protocol["lease_fencing_scope"] != "owner-authoring-transaction@1" {
		return output.New(9, "Backend lacks exact fenced deployment/workflow leases; no legacy activation fallback")
	}
	principal := packagefmt.Text(cap["principal_fingerprint"])
	if principal == "" {
		return output.New(9, "Backend omitted deployment principal identity")
	}
	if opts.Intent == "" {
		opts.Intent, err = devworkspace.NewID()
		if err != nil {
			return err
		}
	}
	w.intent = &deployIntent{Version: "1.0", ID: opts.Intent, API: control.Base, Workspace: a.Workspace, Project: a.Project, Kind: strings.Title(kind), Resource: id, Principal: principal, Request: opts, Status: "created", Source: map[string]any{}, Steps: map[string]*deployStep{}, Local: map[string]string{}}
	if opts.PlanOnly || a.DryRun {
		if opts.Source == "local" {
			if err = w.prepareLocal(false); err != nil {
				return err
			}
		} else if err = w.resolveSource(); err != nil {
			return err
		}
		current, err := w.current(opts.Environment)
		if err != nil {
			return err
		}
		if err = w.checkGeneration(current); err != nil {
			return err
		}
		return a.emit(map[string]any{"kind": w.intent.Kind, "resource_id": id, "environment": opts.Environment, "source": w.intent.Source, "current": current, "status": "preflight", "executed": false, "server_qualification": "not_evaluated"})
	}
	checkpoint := opts.Checkpoint
	if checkpoint == "" {
		namespace := sha256.Sum256([]byte(control.Base + "\x00" + a.Workspace + "\x00" + a.Project))
		checkpoint = filepath.Join(filepath.Dir(a.ConfigPath), "deploy-intents", fmt.Sprintf("%x", namespace[:12]), opts.Intent+".json")
	}
	if err = packagecheckpoint.EnsurePrivateDirectory(filepath.Dir(checkpoint)); err != nil {
		return err
	}
	store, err := packagecheckpoint.Open(checkpoint)
	if err != nil {
		return err
	}
	defer store.Close()
	w.store = store
	raw, readErr := store.ReadDocument()
	if readErr == nil {
		decoder := json.NewDecoder(bytes.NewReader(raw))
		decoder.UseNumber()
		decoder.DisallowUnknownFields()
		var recorded deployIntent
		if decoder.Decode(&recorded) != nil || recorded.Version != "1.0" || recorded.ID != opts.Intent || recorded.API != control.Base || recorded.Workspace != a.Workspace || recorded.Project != a.Project || recorded.Resource != id || recorded.Kind != w.intent.Kind || recorded.Principal != principal || recorded.Steps == nil || recorded.Source == nil {
			return output.New(6, "Deploy intent belongs to another destination, principal or target")
		}
		if verb == "" {
			left, _ := json.Marshal(opts)
			right, _ := json.Marshal(recorded.Request)
			if !bytes.Equal(left, right) {
				return output.New(6, "Deploy intent input changed; inspect the original or create a new explicit intention")
			}
		}
		w.intent = &recorded
		if w.intent.Local == nil {
			w.intent.Local = map[string]string{}
		}
	} else if !os.IsNotExist(readErr) {
		return readErr
	} else if verb != "" {
		return output.New(9, "Original deploy journal is unavailable; restore its private checkpoint before recovery. No write attempted")
	} else {
		// A surviving remote operation with no local journal must not be replayed.
		original, probeErr := w.read(w.base+"/operations/"+deployOperationID(w.intent, "plan:"+opts.Environment), url.Values{"environment": {opts.Environment}})
		if probeErr == nil && original != nil && !(original["operation_id"] == deployOperationID(w.intent, "plan:"+opts.Environment) && original["complete"] == false && original["retry_authorized"] == false && original["state"] == "not_observed") {
			return output.New(9, "This intent already has remote evidence; restore its original checkpoint before continuing")
		}
		if probeErr != nil && output.Normalize(probeErr).Code != 5 {
			return probeErr
		}
		if err = w.save(); err != nil {
			return err
		}
	}
	if verb == "status" {
		result := w.result()
		result["observation"] = "journal_only"
		delete(result, "observed_current_matches")
		return a.emit(result)
	}
	if w.intent.Status == "completed" || w.intent.Status == "already_selected" {
		current, observeErr := w.current(w.intent.Request.Environment)
		expected := w.result()["generation_after"]
		if observeErr == nil && (current["snapshot_id"] != w.intent.Source["release_id"] || fmt.Sprint(current["environment_generation"]) != fmt.Sprint(expected)) {
			observeErr = output.New(6, "Original deploy is complete but the environment has since changed; inspect current")
		}
		if observeErr != nil {
			w.intent.Status = "committed_unconfirmed"
			_ = w.save()
			return &deployFailure{Data: w.result(), Cause: output.Normalize(observeErr)}
		}
		return a.emit(w.result())
	}
	if w.intent.Status == "rejected_terminal" {
		return output.New(6, "Deploy intent was rejected; inspect current and create a new explicit intention")
	}
	if err = w.execute(); err != nil {
		failure := output.Normalize(err)
		if failure.Outcome == "unknown" {
			w.intent.Status = "outcome_unknown"
			if failure.Code != 8 {
				failure.Code = 9
			}
		}
		_ = w.save()
		failure.Message += "; intent " + w.intent.ID + " retained; use deploy resume --intent " + w.intent.ID + " --yes"
		return &deployFailure{Data: w.result(), Cause: failure}
	}
	return a.emit(w.result())
}

type deployFailure struct {
	Data  map[string]any
	Cause *output.Error
}

func (f *deployFailure) Error() string { return f.Cause.Error() }

func (w *deployWorkflow) read(path string, query url.Values) (map[string]any, error) {
	raw, _, err := w.client.Request(w.cmd.Context(), "GET", path, query, nil)
	if err != nil {
		return nil, err
	}
	return developmentResponseData(raw)
}
func (w *deployWorkflow) save() error {
	raw, err := json.Marshal(w.intent)
	if err == nil {
		err = w.store.SaveDocument(raw)
	}
	if err != nil {
		return output.New(10, "Cannot durably retain deploy intent; original operations must be recovered before continuing")
	}
	return nil
}
func deployGeneration(value any) (int64, error) {
	raw, _ := json.Marshal(value)
	number, err := strconv.ParseInt(string(raw), 10, 64)
	if err != nil || number < 0 {
		return 0, output.New(9, "Server omitted monotonic environment generation")
	}
	return number, nil
}
func (w *deployWorkflow) current(env string) (map[string]any, error) {
	data, err := w.read(w.base+"/current", url.Values{"environment": {env}})
	if err != nil {
		return nil, err
	}
	if data["schema_version"] != "1.0" || data["resource_id"] != w.intentResource() || data["kind"] != w.intentKind() || data["environment"] != env || data["complete"] != true || data["generation_status"] != "monotonic_owner_selection" {
		return nil, output.New(9, "Environment observation has incompatible identity, completeness or generation")
	}
	if _, err = deployGeneration(data["environment_generation"]); err != nil {
		return nil, err
	}
	return data, nil
}
func (w *deployWorkflow) intentResource() string {
	if w.intent != nil {
		return w.intent.Resource
	}
	parts := strings.Split(w.base, "/")
	return parts[len(parts)-2]
}
func (w *deployWorkflow) intentKind() string {
	if w.intent != nil {
		return w.intent.Kind
	}
	if strings.Contains(w.base, "/agents/") {
		return "Agent"
	}
	return "Network"
}
func (w *deployWorkflow) checkGeneration(current map[string]any) error {
	generation, err := deployGeneration(current["environment_generation"])
	if err != nil {
		return err
	}
	if w.intent.Request.Expected != -1 && generation != w.intent.Request.Expected {
		return output.New(6, "Destination generation differs from --expect-generation; inspect current")
	}
	return nil
}
func (w *deployWorkflow) resolveSource() error {
	if packagefmt.Text(w.intent.Source["release_id"]) != "" {
		return nil
	}
	opts := w.intent.Request
	if opts.Source == "release" {
		w.intent.Source = map[string]any{"mode": "release", "release_id": opts.Release}
		return nil
	}
	current, err := w.current("staging")
	if err != nil {
		return err
	}
	release := packagefmt.Text(current["snapshot_id"])
	if current["selection_authority"] != "asac" || !uuidReference(release) {
		return output.New(6, "Staging does not select a qualified immutable ASaC Release. Evaluate/publish and deploy an exact Release to Staging first")
	}
	w.intent.Source = map[string]any{"mode": "staging", "release_id": release, "staging_generation": current["environment_generation"]}
	return nil
}

// Each mutating step freezes its exact payload before submission. On every
// subsequent invocation it can only observe the original operation, never POST.
func (w *deployWorkflow) step(name, method, path string, body map[string]any, validate func(map[string]any, map[string]any) error) (map[string]any, error) {
	step := w.intent.Steps[name]
	if step == nil {
		op := deployOperationID(w.intent, name)
		body["operation_id"] = op
		step = &deployStep{Operation: op, Method: method, Path: path, Body: body, State: "prepared"}
		w.intent.Steps[name] = step
		if err := w.save(); err != nil {
			return nil, err
		}
	}
	if step.Operation != deployOperationID(w.intent, name) || step.Method != method || step.Path != path {
		return nil, output.New(6, "Deploy step differs from its frozen identity")
	}
	if step.State == "committed" {
		if err := validate(step.Receipt, step.Body); err != nil {
			return nil, err
		}
		return step.Receipt, nil
	}
	if step.State == "rejected" {
		return nil, output.New(6, "Original deploy step was rejected; create a new intention after inspection")
	}
	var data map[string]any
	var err error
	if step.State == "prepared" {
		step.State = "submitted"
		if err = w.save(); err != nil {
			return nil, err
		}
		encoded, _ := json.Marshal(step.Body)
		var raw any
		raw, _, err = w.client.Request(w.cmd.Context(), method, path, nil, encoded)
		if err == nil {
			data, err = developmentResponseData(raw)
		}
	} else {
		var operation map[string]any
		environment := packagefmt.Text(step.Body["environment"])
		if environment == "" {
			environment = packagefmt.Text(step.Body["scope"])
		}
		operation, err = w.read(w.base+"/operations/"+url.PathEscape(step.Operation), url.Values{"environment": {environment}})
		if err == nil {
			if operation["operation_id"] != step.Operation || operation["state"] != "committed" {
				err = output.New(9, "Original operation is not proven committed; no replay permitted")
			} else {
				data = packagefmt.Object(operation["result"])
			}
		}
		if err != nil {
			// A failed observation never proves the original submitted write was
			// rejected, including an authorization failure during recovery.
			failure := output.Normalize(err)
			failure.Outcome = "unknown"
			if failure.Code != 8 {
				failure.Code = 9
			}
			failure.Message = "Original operation cannot be observed; restore access and reconcile the same intent. No write repeated"
			err = failure
		}
	}
	if err != nil {
		failure := output.Normalize(err)
		if failure.Outcome == "rejected" || failure.Outcome == "not_attempted" {
			step.State = "rejected"
			w.intent.Status = "rejected_terminal"
		} else {
			w.intent.Status = "outcome_unknown"
		}
		if saveErr := w.save(); saveErr != nil {
			return nil, saveErr
		}
		return nil, err
	}
	if err = validate(data, step.Body); err != nil {
		return nil, err
	}
	step.State = "committed"
	step.Receipt = data
	if err = w.save(); err != nil {
		return nil, err
	}
	return data, nil
}

func (w *deployWorkflow) selectRelease(environment string) error {
	opts := w.intent.Request
	name := "plan:" + environment
	planStep := w.intent.Steps[name]
	body := map[string]any{"environment": environment, "release_id": w.intent.Source["release_id"], "reason": opts.Notes, "action": opts.Action}
	if publication := packagefmt.Text(w.intent.Source["publication_id"]); publication != "" {
		body["publication_id"] = publication
	} else if opts.Publication != "" {
		body["publication_id"] = opts.Publication
	}
	if planStep == nil {
		current, err := w.current(environment)
		if err != nil {
			return err
		}
		if environment == opts.Environment {
			if err = w.checkGeneration(current); err != nil {
				return err
			}
		}
		body["expected_generation"] = current["environment_generation"]
	}
	validatePlan := func(data, payload map[string]any) error {
		if data["kind"] != w.intent.Kind {
			return output.New(9, "Plan target kind mismatch")
		}
		return validateDeploymentAcceptance(data, w.intent.Project, w.intent.Resource, packagefmt.Text(payload["operation_id"]), environment, payload, true)
	}
	plan, err := w.step(name, "POST", w.base+"/deployment-plans", body, validatePlan)
	if err != nil {
		return err
	}
	if w.intent.Steps["apply:"+environment] == nil && plan["previous_release_id"] == plan["release_id"] && packagefmt.Text(plan["native_fingerprint"]) != "" && plan["previous_fingerprint"] == plan["native_fingerprint"] && opts.Action != "rollback" {
		current, err := w.current(environment)
		if err != nil {
			return err
		}
		if current["snapshot_id"] != plan["release_id"] || fmt.Sprint(current["environment_generation"]) != fmt.Sprint(plan["expected_generation"]) {
			return output.New(6, "Environment changed after qualification; create a new intentional plan")
		}
		if environment == opts.Environment {
			w.intent.Status = "already_selected"
			return w.save()
		}
		return nil
	}
	leaseBody := map[string]any{"scope": environment, "workflow_id": deployOperationID(w.intent, "workflow:"+environment), "ttl_seconds": 120}
	leaseValidator := func(data, payload map[string]any) error {
		if err := validateLeaseReceipt(data, w.intent.Project, w.intent.Resource, packagefmt.Text(payload["operation_id"]), environment, payload); err != nil {
			return err
		}
		return validateLeaseAction(data, "acquire")
	}
	lease, err := w.step("lease:"+environment, "POST", w.base+"/leases/acquire", leaseBody, leaseValidator)
	if err != nil {
		return err
	}
	if opts.Source == "staging" && w.intent.Steps["apply:"+environment] == nil {
		staging, err := w.current("staging")
		if err != nil {
			return err
		}
		if staging["snapshot_id"] != w.intent.Source["release_id"] || fmt.Sprint(staging["environment_generation"]) != fmt.Sprint(w.intent.Source["staging_generation"]) {
			_ = w.releaseLease(environment, lease)
			return output.New(6, "staging_changed_since_capture: inspect Staging and create a new intent")
		}
	}
	proof := map[string]any{"lease_id": lease["lease_id"], "workflow_id": lease["workflow_id"], "fencing_token": lease["fencing_token"]}
	applyBody := map[string]any{"environment": environment, "plan_id": plan["plan_id"], "leases": []map[string]any{proof}}
	validateApply := func(data, payload map[string]any) error {
		if err := validateDeploymentAcceptance(data, w.intent.Project, w.intent.Resource, packagefmt.Text(payload["operation_id"]), environment, payload, false); err != nil {
			return err
		}
		if data["kind"] != w.intent.Kind || data["release_id"] != plan["release_id"] || data["publication_id"] != plan["publication_id"] || data["plan_digest"] != plan["plan_digest"] || fmt.Sprint(data["generation_before"]) != fmt.Sprint(plan["expected_generation"]) {
			return output.New(9, "Committed deployment differs from qualified plan")
		}
		return nil
	}
	receipt, err := w.step("apply:"+environment, "POST", w.base+"/deployments", applyBody, validateApply)
	if err != nil {
		if w.intent.Status == "rejected_terminal" {
			_ = w.releaseLease(environment, lease)
		}
		return err
	}
	// Prove the retained receipt and current pointer, rather than trusting POST.
	observed, err := w.read(w.base+"/deployments/"+url.PathEscape(packagefmt.Text(receipt["deployment_id"])), url.Values{"environment": {environment}})
	if err != nil {
		w.intent.Status = "committed_unconfirmed"
		_ = w.save()
		return err
	}
	if err = validateApply(observed, w.intent.Steps["apply:"+environment].Body); err != nil {
		return err
	}
	current, err := w.current(environment)
	if err != nil {
		w.intent.Status = "committed_unconfirmed"
		_ = w.save()
		return err
	}
	if current["selection_authority"] != "asac" || current["snapshot_id"] != receipt["release_id"] || fmt.Sprint(current["environment_generation"]) != fmt.Sprint(receipt["generation_after"]) {
		w.intent.Status = "committed_unconfirmed"
		_ = w.save()
		return output.New(6, "Deployment committed but current changed; inspect the receipt and current before another deployment")
	}
	if err = w.releaseLease(environment, lease); err != nil {
		w.intent.Status = "cleanup_pending"
		_ = w.save()
		return err
	}
	return nil
}
func (w *deployWorkflow) releaseLease(environment string, lease map[string]any) error {
	body := map[string]any{"scope": environment, "lease_id": lease["lease_id"], "workflow_id": lease["workflow_id"], "fencing_token": lease["fencing_token"]}
	validator := func(data, payload map[string]any) error {
		if err := validateLeaseReceipt(data, w.intent.Project, w.intent.Resource, packagefmt.Text(payload["operation_id"]), environment, payload); err != nil {
			return err
		}
		return validateLeaseAction(data, "release")
	}
	_, err := w.step("release-lease:"+environment, "POST", w.base+"/leases/release", body, validator)
	return err
}
func (w *deployWorkflow) execute() error {
	if w.intent.Request.Source == "local" {
		if err := w.deliverLocal(); err != nil {
			return err
		}
	} else if err := w.resolveSource(); err != nil {
		return err
	}
	if err := w.save(); err != nil {
		return err
	}
	if w.intent.Request.ViaStaging {
		if err := w.selectRelease("staging"); err != nil {
			return err
		}
		if err := w.runStagingSmoke(); err != nil {
			return err
		}
	}
	if err := w.selectRelease(w.intent.Request.Environment); err != nil {
		return err
	}
	if w.intent.Status != "already_selected" {
		w.intent.Status = "completed"
	}
	return w.save()
}
func (w *deployWorkflow) result() map[string]any {
	data := map[string]any{"intent_id": w.intent.ID, "kind": w.intent.Kind, "resource_id": w.intent.Resource, "source": w.intent.Source, "environment": w.intent.Request.Environment, "status": w.intent.Status, "git_verification": "not_evaluated"}
	if plan := w.intent.Steps["plan:"+w.intent.Request.Environment]; plan != nil && plan.Receipt != nil {
		for _, key := range []string{"plan_id", "publication_id", "candidate_id", "evaluation_id", "previous_release_id", "release_id", "actor"} {
			data[key] = plan.Receipt[key]
		}
		data["generation_before"] = plan.Receipt["expected_generation"]
	}
	if applied := w.intent.Steps["apply:"+w.intent.Request.Environment]; applied != nil && applied.Receipt != nil {
		for _, key := range []string{"deployment_id", "generation_after", "write_outcome"} {
			data[key] = applied.Receipt[key]
		}
		data["observed_current_matches"] = w.intent.Status == "completed"
	}
	if w.intent.Status == "already_selected" {
		data["generation_after"] = data["generation_before"]
		data["observed_current_matches"] = true
		data["write_outcome"] = "not_attempted"
	}
	operations := map[string]any{}
	for name, step := range w.intent.Steps {
		operations[name] = map[string]any{"operation_id": step.Operation, "state": step.State}
	}
	data["operations"] = operations
	if w.intent.Request.Source == "local" {
		data["local"] = w.intent.Local
	}
	return data
}

// The local adapter is implemented alongside the existing typed lifecycle
// primitives; no child process or manifest reconciliation is used.
