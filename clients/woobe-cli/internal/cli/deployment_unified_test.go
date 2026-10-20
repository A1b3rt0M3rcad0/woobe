package cli

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/asac"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
)

const deployTestTarget = "01a0a033-5820-770c-854b-902864857273"
const deployTestProject = "12345678-1234-4321-8321-123456789099"
const deployTestRelease = "12345678-1234-4321-8321-123456789077"
const deployTestIntent = "12345678-1234-4321-8321-123456789011"

type deployFixture struct {
	kind                  string
	generation            int64
	selected              string
	sourceGeneration      int64
	staging               string
	authority             string
	capability            bool
	missingOperationScope bool
	lost, deny, forged    string
	writes                map[string]int
	operations            map[string]map[string]any
	plans                 map[string]map[string]any
	deployments           map[string]map[string]any
	driftStaging          bool
	unobserved            bool
	denyOperationRead     bool
	principal             string
}

func newDeployFixture(kind string) *deployFixture {
	return &deployFixture{kind: kind, generation: 4, sourceGeneration: 2, staging: deployTestRelease, authority: "asac", capability: true, writes: map[string]int{}, operations: map[string]map[string]any{}, plans: map[string]map[string]any{}, deployments: map[string]map[string]any{}}
}
func testDeployDigest(data map[string]any, key, scope string) {
	delete(data, key)
	digest, _ := asac.Digest(scope, data)
	data[key] = digest
}
func (f *deployFixture) serve(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path
	var data map[string]any
	if r.Method == "POST" {
		var body map[string]any
		dec := json.NewDecoder(r.Body)
		dec.UseNumber()
		_ = dec.Decode(&body)
		op, _ := body["operation_id"].(string)
		action := strings.TrimPrefix(path, fmt.Sprintf("/projects/%s/%ss/%s/asac/", deployTestProject, strings.ToLower(f.kind), deployTestTarget))
		f.writes[action]++
		if action == f.deny {
			w.WriteHeader(403)
			_ = json.NewEncoder(w).Encode(map[string]any{"success": false})
			return
		}
		switch action {
		case "deployment-plans":
			data = deploymentTestPlan(body, deployTestProject, deployTestTarget)
			data["kind"] = f.kind
			data["native_fingerprint"] = "qualified"
			data["previous_fingerprint"] = "qualified"
			data["previous_release_id"] = f.selected
			if body["publication_id"] != nil {
				data["publication_id"] = body["publication_id"]
			}
			testDeployDigest(data, "plan_digest", "deployment-plan")
			f.plans[data["plan_id"].(string)] = data
		case "leases/acquire", "leases/release":
			if action == "leases/acquire" && f.driftStaging {
				f.sourceGeneration++
			}
			now := time.Now().UTC()
			data = map[string]any{"schema_version": "1.0", "complete": true, "clock_authority": "database", "project_id": deployTestProject, "resource_id": deployTestTarget, "operation_id": op, "scope": body["scope"], "write_outcome": "committed", "actor": "control:fixture", "state": "active", "lease_id": deployTestTarget, "workflow_id": body["workflow_id"], "fencing_token": 7, "acquired_at": now.Format(time.RFC3339Nano), "server_time": now.Format(time.RFC3339Nano), "expires_at": now.Add(time.Minute).Format(time.RFC3339Nano), "maximum_expires_at": now.Add(time.Hour).Format(time.RFC3339Nano)}
			if action == "leases/release" {
				data["state"] = "released"
				data["lease_id"] = body["lease_id"]
				data["fencing_token"] = body["fencing_token"]
			}
		case "deployments":
			plan := f.plans[body["plan_id"].(string)]
			data = map[string]any{}
			for k, v := range plan {
				data[k] = v
			}
			delete(data, "expires_at")
			delete(data, "expected_generation")
			delete(data, "executed")
			data["operation_id"] = op
			data["state"] = "committed"
			data["deployment_id"] = deployTestRelease
			data["outbox_id"] = deployTestIntent
			data["leases"] = body["leases"]
			data["generation_before"] = f.generation
			f.generation++
			data["generation_after"] = f.generation
			data["selection_changed"] = true
			f.selected = plan["release_id"].(string)
			testDeployDigest(data, "receipt_digest", "deployment-receipt")
			f.deployments[deployTestRelease] = data
		default:
			w.WriteHeader(404)
			return
		}
		f.operations[op] = data
		if action == f.lost {
			f.lost = ""
			w.WriteHeader(500)
			_ = json.NewEncoder(w).Encode(map[string]any{"success": false})
			return
		}
		if action == f.forged {
			clone := map[string]any{}
			for k, v := range data {
				clone[k] = v
			}
			clone["resource_id"] = deployTestRelease
			data = clone
		}
	} else {
		switch {
		case strings.HasSuffix(path, "/capabilities"):
			principal := f.principal
			if principal == "" {
				principal = strings.Repeat("a", 64)
			}
			data = map[string]any{"principal_fingerprint": principal, "asac": map[string]any{"schema_version": "1.0", "fenced_deployment": f.capability, "operation_environment_reads": !f.missingOperationScope, "deployment_scope": "exact-release-owner-selection@1", "operation_leases": true, "lease_clock": "database", "lease_fencing_scope": "owner-authoring-transaction@1"}}
		case strings.HasSuffix(path, "/current"):
			env := r.URL.Query().Get("environment")
			selected, generation := f.selected, f.generation
			if env == "staging" {
				selected, generation = f.staging, f.sourceGeneration
			}
			var snapshot any
			if selected != "" {
				snapshot = selected
			}
			data = map[string]any{"schema_version": "1.0", "kind": f.kind, "resource_id": deployTestTarget, "environment": env, "snapshot_id": snapshot, "environment_generation": generation, "selection_authority": f.authority, "generation_status": "monotonic_owner_selection", "complete": true}
		case strings.Contains(path, "/operations/"):
			if f.denyOperationRead {
				w.WriteHeader(403)
				_ = json.NewEncoder(w).Encode(map[string]any{"success": false})
				return
			}
			if f.unobserved {
				data = map[string]any{"state": "not_observed", "retry_authorized": false, "complete": false}
				break
			}
			op := path[strings.LastIndex(path, "/")+1:]
			receipt := f.operations[op]
			if receipt == nil {
				w.WriteHeader(404)
				_ = json.NewEncoder(w).Encode(map[string]any{"success": false})
				return
			}
			data = map[string]any{"state": "committed", "operation_id": op, "result": receipt}
		case strings.Contains(path, "/deployments/"):
			data = f.deployments[path[strings.LastIndex(path, "/")+1:]]
		default:
			w.WriteHeader(404)
			return
		}
	}
	_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
}
func deployTestFlags(t *testing.T, server *httptest.Server) []string {
	t.Helper()
	t.Setenv("WOOBE_CONTROL_KEY", "fixture-secret-never-output")
	return []string{"--api-url", server.URL, "--workspace", "workspace", "--project", deployTestProject, "--config", filepath.Join(t.TempDir(), "config.json"), "--no-project-config", "--output", "json", "--checkpoint", filepath.Join(t.TempDir(), "state", "intent.json")}
}
func deployInvocation(flags []string, kind, source string) []string {
	args := []string{strings.ToLower(kind), deployTestTarget, "deploy", "--from", source, "--notes", "Deploy approved revision", "--intent", deployTestIntent, "--yes"}
	if source == "release" {
		args = append(args, "--release", deployTestRelease)
	}
	return append(args, flags...)
}

func TestUnifiedDeployNativeAgentAndNetworkReleaseStagingRollbackAndNoop(t *testing.T) {
	for _, kind := range []string{"Agent", "Network"} {
		for _, source := range []string{"release", "staging"} {
			t.Run(kind+source, func(t *testing.T) {
				fixture := newDeployFixture(kind)
				server := httptest.NewServer(http.HandlerFunc(fixture.serve))
				defer server.Close()
				flags := deployTestFlags(t, server)
				args := deployInvocation(flags, kind, source)
				if code, value := invoke(t, args, ""); code != 0 || value["data"].(map[string]any)["status"] != "completed" || fixture.selected != deployTestRelease || fixture.writes["deployments"] != 1 {
					t.Fatal(code, value, fixture.writes)
				}
				if code, value := invoke(t, args, ""); code != 0 || fixture.writes["deployments"] != 1 {
					t.Fatal("completed intent replayed", code, value)
				}
				resume := append([]string{strings.ToLower(kind), deployTestTarget, "deploy", "resume", "--intent", deployTestIntent, "--yes"}, flags...)
				if code, value := invoke(t, resume, ""); code != 0 || fixture.writes["deployments"] != 1 {
					t.Fatal(code, value)
				}
				fresh := deployInvocation(flags, kind, "release")
				for i, arg := range fresh {
					if arg == deployTestIntent {
						fresh[i] = deployTestRelease
					}
					if strings.HasSuffix(arg, "intent.json") {
						fresh[i] = strings.TrimSuffix(arg, "intent.json") + "second.json"
					}
				}
				if code, value := invoke(t, fresh, ""); code != 0 || value["data"].(map[string]any)["status"] != "already_selected" || fixture.writes["deployments"] != 1 {
					t.Fatal(code, value, fixture.writes)
				}
			})
		}
	}
}
func TestUnifiedDeployLostResponsesReconcileEveryOriginalWithoutRepeatingWrite(t *testing.T) {
	for _, lost := range []string{"deployment-plans", "leases/acquire", "deployments", "leases/release"} {
		t.Run(lost, func(t *testing.T) {
			fixture := newDeployFixture("Agent")
			fixture.lost = lost
			server := httptest.NewServer(http.HandlerFunc(fixture.serve))
			defer server.Close()
			flags := deployTestFlags(t, server)
			args := deployInvocation(flags, "Agent", "release")
			if code, value := invoke(t, args, ""); code == 0 || !strings.Contains(fmt.Sprint(value), deployTestIntent) {
				t.Fatal(code, value)
			}
			resume := append([]string{"agent", deployTestTarget, "deploy", "resume", "--intent", deployTestIntent, "--yes"}, flags...)
			if code, value := invoke(t, resume, ""); code != 0 {
				t.Fatal(code, value)
			}
			for action, count := range fixture.writes {
				if count != 1 {
					t.Fatal("write repeated", action, count)
				}
			}
		})
	}
}
func TestUnifiedDeployPreflightCapabilitiesLegacyStagingGenerationAndAuthority(t *testing.T) {
	for _, scenario := range []string{"plan-only", "dry-run", "capability", "operation-scope", "legacy", "empty-staging", "generation", "forbidden", "forged", "changed-input"} {
		t.Run(scenario, func(t *testing.T) {
			fixture := newDeployFixture("Agent")
			server := httptest.NewServer(http.HandlerFunc(fixture.serve))
			defer server.Close()
			flags := deployTestFlags(t, server)
			args := deployInvocation(flags, "Agent", "release")
			expected := 0
			switch scenario {
			case "plan-only":
				args = append(args, "--plan-only")
			case "dry-run":
				args = append(args, "--dry-run")
			case "capability":
				fixture.capability = false
				expected = 9
			case "operation-scope":
				fixture.missingOperationScope = true
				expected = 9
			case "legacy":
				fixture.authority = "legacy"
				args = deployInvocation(flags, "Agent", "staging")
				expected = 6
			case "empty-staging":
				fixture.staging = ""
				args = deployInvocation(flags, "Agent", "staging")
				expected = 6
			case "generation":
				args = append(args, "--expect-generation", "9")
				expected = 6
			case "forbidden":
				fixture.deny = "deployment-plans"
				expected = 4
			case "forged":
				fixture.forged = "deployments"
				expected = 9
			case "changed-input":
				if code, value := invoke(t, args, ""); code != 0 {
					t.Fatal(code, value)
				}
				for i, arg := range args {
					if arg == "Deploy approved revision" {
						args[i] = "Changed reason"
					}
				}
				expected = 6
			}
			if code, value := invoke(t, args, ""); code != expected {
				t.Fatal(code, value)
			}
			if scenario != "forged" && scenario != "changed-input" && fixture.writes["deployments"] != 0 {
				t.Fatal("unexpected selection write", fixture.writes)
			}
			if (scenario == "plan-only" || scenario == "dry-run" || scenario == "capability") && len(fixture.writes) != 0 {
				t.Fatal("preflight performed writes", fixture.writes)
			}
		})
	}
}
func TestUnifiedDeployInvalidInputAndMissingRecoveryStateNeverWrite(t *testing.T) {
	for _, options := range [][]string{{}, {"--from", "release", "--release", "not-uuid"}, {"--from", "local"}, {"--from", "release", "--release", deployTestRelease, "--suite", "suite.yaml"}, {"--from", "staging", "--env", "staging"}, {"--from", "release", "--release", deployTestRelease, "--action", "rollback", "--env", "staging"}, {"status"}, {"resume", "--intent", deployTestIntent}} {
		args := append([]string{"agent", deployTestTarget, "deploy"}, options...)
		if code, value := invoke(t, args, ""); code != 2 {
			t.Fatal(args, code, value)
		}
	}
	fixture := newDeployFixture("Agent")
	server := httptest.NewServer(http.HandlerFunc(fixture.serve))
	defer server.Close()
	flags := deployTestFlags(t, server)
	args := append([]string{"agent", deployTestTarget, "deploy", "resume", "--intent", deployTestIntent, "--yes"}, flags...)
	if code, value := invoke(t, args, ""); code != 9 || len(fixture.writes) != 0 {
		t.Fatal(code, value, fixture.writes)
	}
}
func TestDeployIntentPrivateStoreRejectsMalformedExternalEditsAndLocks(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "state")
	if err := packagecheckpoint.EnsurePrivateDirectory(dir); err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(dir, "intent.json")
	store, err := packagecheckpoint.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	if err := store.SaveDocument([]byte(`{"intent":"original"}`)); err != nil {
		t.Fatal(err)
	}
	if _, err := packagecheckpoint.Open(path); err == nil {
		t.Fatal("concurrent writer acquired checkpoint")
	}
	if err := os.WriteFile(path, []byte(`{"intent":"a","intent":"b"}`), 0600); err != nil {
		t.Fatal(err)
	}
	if err := store.SaveDocument([]byte(`{"intent":"new"}`)); err == nil {
		t.Fatal("ambiguous document overwritten")
	}
}
func TestDeployOperationsAreStableScopedDistinctUUIDs(t *testing.T) {
	intent := &deployIntent{API: "https://woobe.example", Project: deployTestProject, Resource: deployTestTarget, ID: deployTestIntent, Kind: "Agent"}
	plan := deployOperationID(intent, "plan:production")
	if !deployUUID.MatchString(plan) || plan != deployOperationID(intent, "plan:production") || plan == deployOperationID(intent, "apply:production") {
		t.Fatal(plan)
	}
	intent.API = "https://another.example"
	if plan == deployOperationID(intent, "plan:production") {
		t.Fatal("cross-instance identity collision")
	}
}

func TestUnifiedDeployStagingDriftAndUnknownNeverAuthorizeReplay(t *testing.T) {
	for _, kind := range []string{"Agent", "Network"} {
		t.Run(kind+"drift", func(t *testing.T) {
			f := newDeployFixture(kind)
			f.driftStaging = true
			server := httptest.NewServer(http.HandlerFunc(f.serve))
			defer server.Close()
			flags := deployTestFlags(t, server)
			code, result := invoke(t, deployInvocation(flags, kind, "staging"), "")
			if code != 6 || f.writes["deployments"] != 0 || !strings.Contains(fmt.Sprint(result), "staging_changed_since_capture") {
				t.Fatal(code, result, f.writes)
			}
		})
		t.Run(kind+"unknown", func(t *testing.T) {
			f := newDeployFixture(kind)
			f.lost = "deployments"
			server := httptest.NewServer(http.HandlerFunc(f.serve))
			defer server.Close()
			flags := deployTestFlags(t, server)
			if code, result := invoke(t, deployInvocation(flags, kind, "release"), ""); code == 0 {
				t.Fatal(result)
			}
			// Neither 404 nor an explicit not_observed response is retry proof.
			f.operations = map[string]map[string]any{}
			f.unobserved = true
			resume := append([]string{strings.ToLower(kind), deployTestTarget, "deploy", "resume", "--intent", deployTestIntent, "--yes"}, flags...)
			if code, result := invoke(t, resume, ""); code != 9 || f.writes["deployments"] != 1 {
				t.Fatal(code, result, f.writes)
			}
			f.unobserved = false
			if code, result := invoke(t, resume, ""); code != 9 || f.writes["deployments"] != 1 {
				t.Fatal(code, result, f.writes)
			}
		})
		t.Run(kind+"principal", func(t *testing.T) {
			f := newDeployFixture(kind)
			f.lost = "deployment-plans"
			server := httptest.NewServer(http.HandlerFunc(f.serve))
			defer server.Close()
			flags := deployTestFlags(t, server)
			invoke(t, deployInvocation(flags, kind, "release"), "")
			f.principal = strings.Repeat("b", 64)
			resume := append([]string{strings.ToLower(kind), deployTestTarget, "deploy", "resume", "--intent", deployTestIntent, "--yes"}, flags...)
			if code, result := invoke(t, resume, ""); code != 6 || f.writes["deployments"] != 0 {
				t.Fatal(code, result)
			}
		})
	}
}

func TestDeployIntentRejectsSymlinkAndHardlinkWithoutReplacingOriginal(t *testing.T) {
	for _, link := range []struct {
		name   string
		create func(string, string) error
	}{{"symlink", os.Symlink}, {"hardlink", os.Link}} {
		t.Run(link.name, func(t *testing.T) {
			parent := filepath.Join(t.TempDir(), "state")
			if err := packagecheckpoint.EnsurePrivateDirectory(parent); err != nil {
				t.Fatal(err)
			}
			original := filepath.Join(parent, "original.json")
			if err := os.WriteFile(original, []byte(`{"original":true}`), 0600); err != nil {
				t.Fatal(err)
			}
			path := filepath.Join(parent, "intent.json")
			if err := link.create(original, path); err != nil {
				t.Skip("filesystem does not permit this link:", err)
			}
			store, err := packagecheckpoint.Open(path)
			if err == nil {
				defer store.Close()
				if err = store.SaveDocument([]byte(`{"replacement":true}`)); err == nil {
					t.Fatal("linked journal accepted")
				}
			}
			raw, err := os.ReadFile(original)
			if err != nil || string(raw) != `{"original":true}` {
				t.Fatal("original modified", err, string(raw))
			}
		})
	}
}

func TestUnifiedDeployUppercaseUUIDsAndRollbackRemainExact(t *testing.T) {
	f := newDeployFixture("Agent")
	f.selected = deployTestRelease
	server := httptest.NewServer(http.HandlerFunc(f.serve))
	defer server.Close()
	args := deployInvocation(deployTestFlags(t, server), "Agent", "release")
	for i, arg := range args {
		if deployUUID.MatchString(arg) {
			args[i] = strings.ToUpper(arg)
		}
	}
	args = append(args, "--action", "rollback")
	code, result := invoke(t, args, "")
	if code != 0 || f.writes["deployments"] != 1 || result["data"].(map[string]any)["release_id"] != deployTestRelease {
		t.Fatal(code, result, f.writes)
	}
}

func TestUnifiedDeployDeniedRecoveryReadDoesNotRejectOriginalCommittedApply(t *testing.T) {
	fixture := newDeployFixture("Agent")
	fixture.lost = "deployments"
	server := httptest.NewServer(http.HandlerFunc(fixture.serve))
	defer server.Close()
	flags := deployTestFlags(t, server)
	if code, value := invoke(t, deployInvocation(flags, "Agent", "release"), ""); code != 9 {
		t.Fatal(code, value)
	}
	fixture.denyOperationRead = true
	resume := append([]string{"agent", deployTestTarget, "deploy", "resume", "--intent", deployTestIntent, "--yes"}, flags...)
	if code, value := invoke(t, resume, ""); code != 9 || value["data"].(map[string]any)["status"] != "outcome_unknown" {
		t.Fatal(code, value)
	}
	if fixture.writes["deployments"] != 1 {
		t.Fatal("Original write repeated after denied observation")
	}
	fixture.denyOperationRead = false
	if code, value := invoke(t, resume, ""); code != 0 {
		t.Fatal(code, value)
	}
	if fixture.writes["deployments"] != 1 {
		t.Fatal("Original apply repeated after restoring access")
	}
}

func TestUnifiedLocalInvalidSuiteNeverCreatesAuthoringOrProviderWrites(t *testing.T) {
	for _, problem := range []string{"unknown-suite-field", "unknown-case-field", "missing-id", "duplicate-id", "blank-message", "numeric-version", "numeric-message", "nonobject-case", "null-context", "unsupported-policy"} {
		t.Run(problem, func(t *testing.T) {
			suite := map[string]any{"schema_version": "1.0", "suite_id": "delivery", "suite_version": "1", "dataset_version": "1"}
			item := map[string]any{"id": "question", "message": "Hello"}
			suite["cases"] = []any{item}
			switch problem {
			case "unknown-suite-field":
				suite["unexpected"] = true
			case "unknown-case-field":
				item["unexpected"] = true
			case "missing-id":
				delete(item, "id")
			case "duplicate-id":
				suite["cases"] = []any{item, item}
			case "blank-message":
				item["message"] = " \n\t "
			case "numeric-version":
				suite["suite_version"] = 1
			case "numeric-message":
				item["message"] = 1
			case "nonobject-case":
				suite["cases"] = []any{"wrong"}
			case "null-context":
				item["external_context"] = nil
			case "unsupported-policy":
				suite["policy_version"] = "unsupported"
			}
			file := filepath.Join(t.TempDir(), "suite.json")
			raw, _ := json.Marshal(suite)
			if err := os.WriteFile(file, raw, 0600); err != nil {
				t.Fatal(err)
			}
			fixture := newDeployFixture("Agent")
			server := httptest.NewServer(http.HandlerFunc(fixture.serve))
			defer server.Close()
			flags := deployTestFlags(t, server)
			args := append([]string{"agent", deployTestTarget, "deploy", "--from", "local", "--suite", file, "--notes", "Reject invalid evaluation before authoring", "--yes"}, flags...)
			if code, value := invoke(t, args, ""); code != 2 {
				t.Fatal(code, value)
			}
			if len(fixture.writes) != 0 {
				t.Fatal("Malformed suite caused a server write", fixture.writes)
			}
		})
	}
}
