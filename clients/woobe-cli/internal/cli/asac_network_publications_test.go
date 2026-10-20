package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/asac"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
)

func TestNetworkPublicationRecoveryKeepsOriginalAcceptanceAndMirrorsTerminalEvidence(t *testing.T) {
	for _, cancel := range []bool{false, true} {
		t.Run(map[bool]string{false: "resume", true: "cancel"}[cancel], func(t *testing.T) {
			root, _ := filepath.Abs("../..")
			t.Setenv("WOOBE_TEST_REPOSITORY", root)
			t.Setenv("WOOBE_CONTROL_KEY", "test-control")
			const native = "01a0a033-5820-770c-854b-902864857273"
			const project = "12345678-1234-4321-8321-123456789012"
			const candidate = "12345678-1234-4321-8321-123456789014"
			const evaluation = "12345678-1234-4321-8321-123456789015"
			const publication = "12345678-1234-4321-8321-123456789016"
			const release = "12345678-1234-4321-8321-123456789017"
			hash := "sha256:" + strings.Repeat("d", 64)
			var resource devworkspace.Resource
			var accepted, current map[string]any
			publishes, resumes, cancels := 0, 0, 0
			mutateIdentity := false
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				var data any
				switch {
				case strings.HasSuffix(r.URL.Path, "/capabilities"):
					data = map[string]any{"asac": map[string]any{"schema_version": "1.0", "candidate_publication_kinds": []any{"Agent", "Network"}}}
				case strings.HasSuffix(r.URL.Path, "/candidates/"+candidate):
					data = map[string]any{"state": "ready", "candidate_id": candidate, "resource_id": native, "resource_uid": resource.UID, "record_digest": hash, "runtime_digest": hash, "runtime_digest_scope": "network-execution-runtime@2"}
				case strings.HasSuffix(r.URL.Path, "/evaluations/"+evaluation):
					data = map[string]any{"state": "passed", "evaluation_id": evaluation, "candidate_id": candidate, "resource_id": native, "record_digest": hash, "runtime_digest": hash}
				case r.Method == "POST" && strings.HasSuffix(r.URL.Path, "/publications"):
					publishes++
					var body map[string]any
					_ = json.NewDecoder(r.Body).Decode(&body)
					accepted = map[string]any{"schema_version": "1.0", "kind": "Network", "publication_id": publication, "project_id": project, "resource_id": native, "resource_uid": resource.UID, "operation_id": body["operation_id"], "candidate_id": candidate, "evaluation_id": evaluation, "state": "preparing", "accepted": true, "published": false, "production_changed": false, "complete": false, "write_outcome": "committed", "prepared_constituents": 1, "required_constituents": 2, "error_code": "ASAC_PUBLICATION_PREPARATION_PENDING", "runtime_digest": hash, "runtime_digest_scope": "network-execution-runtime@2", "record_digest": hash}
					current = accepted
					data = accepted
				case strings.Contains(r.URL.Path, "/operations/"):
					data = map[string]any{"operation_id": accepted["operation_id"], "state": "committed", "result": accepted}
				case r.Method == "POST" && strings.HasSuffix(r.URL.Path, "/reconcile"):
					resumes++
					current = map[string]any{"schema_version": "1.0", "kind": "Network", "publication_id": publication, "project_id": project, "resource_id": native, "resource_uid": resource.UID, "operation_id": accepted["operation_id"], "candidate_id": candidate, "evaluation_id": evaluation, "release_id": release, "release_version": "v0.0.20261009.01", "revision_id": "rv_12345678-1234-4321-8321-123456789019", "reused": false, "actor": "control:12345678-1234-4321-8321-123456789011", "reason": "Qualified Network", "created_at": "2026-10-09T00:00:00+00:00", "git": map[string]any{"status": "unavailable"}, "published": true, "production_changed": false, "complete": true, "write_outcome": "committed", "state": "published", "runtime_digest_scope": "network-execution-runtime@2", "constituent_releases": []any{map[string]any{"node_id": candidate, "agent_id": native, "source_snapshot_id": evaluation, "release_id": release, "runtime_digest": hash}}}
					for _, key := range []string{"record_digest", "runtime_digest", "definition_digest", "artifact_digest", "binding_digest", "suite_digest", "dataset_digest", "policy_digest"} {
						current[key] = hash
					}
					current["receipt_digest"], _ = asac.Digest("publication-receipt", current)
					data = current
				case r.Method == "POST" && strings.HasSuffix(r.URL.Path, "/cancel"):
					cancels++
					var body map[string]any
					_ = json.NewDecoder(r.Body).Decode(&body)
					current = map[string]any{}
					for key, value := range accepted {
						current[key] = value
					}
					current["state"] = "cancelled"
					current["complete"] = true
					current["actor"] = "control:12345678-1234-4321-8321-123456789011"
					current["reason"] = body["reason"]
					current["receipt_digest"], _ = asac.Digest("publication-cancellation", current)
					data = current
				case r.Method == "GET" && strings.HasSuffix(r.URL.Path, "/publications/"+publication):
					data = current
					if mutateIdentity {
						changed := map[string]any{}
						for key, value := range current {
							changed[key] = value
						}
						changed["candidate_id"] = release
						delete(changed, "receipt_digest")
						scope := "publication-receipt"
						if cancel {
							scope = "publication-cancellation"
						}
						changed["receipt_digest"], _ = asac.Digest(scope, changed)
						data = changed
					}
				default:
					t.Error("Unexpected implicit publication/activation", r.Method, r.URL.Path)
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
			}))
			defer server.Close()
			c, state, _ := asacWorkspace(t, server.URL)
			for _, r := range c.Resources {
				if r.Kind == "Network" {
					resource = r
					break
				}
			}
			if resource.UID == "" {
				t.Fatal("No Network fixture")
			}
			state.Project = project
			binding := state.Bindings[resource.UID]
			binding.ResourceID = native
			state.Bindings[resource.UID] = binding
			if err := c.WriteState(state); err != nil {
				t.Fatal(err)
			}
			flags := []string{"--api-url", server.URL, "--project", project, "--workspace", "workspace", "--output", "json"}
			run := func(args ...string) (int, map[string]any) { return invoke(t, append(args, flags...), "") }
			publish := []string{"network", "@" + resource.Alias, "publish", "--candidate", candidate, "--evaluation", evaluation, "--notes", "Qualified Network", "--yes"}
			if code, value := run(publish...); code != 9 || publishes != 1 {
				t.Fatal(code, value, publishes)
			}
			if code, value := run(publish...); code != 9 || publishes != 1 {
				t.Fatal("Repeated acceptance", code, value, publishes)
			}
			if code, value := run("network", "@"+resource.Alias, "draft", "reconcile"); code != 9 || resumes+cancels != 0 {
				t.Fatal("Read reconciler repeated a write", code, value)
			}
			action := "reconcile"
			if cancel {
				action = "cancel"
			}
			recovery := []string{"network", native, "publication", publication, action, "--no-project-config", "--yes"}
			if cancel {
				recovery = append(recovery, "--notes", "Discard blocked preparation")
			}
			if code, value := run(recovery...); code != 0 {
				t.Fatal("Native UUID recovery needs registry", code, value)
			}
			mutateIdentity = true
			if code, value := run("network", "@"+resource.Alias, "draft", "reconcile"); code != 9 {
				t.Fatal("Accepted another candidate", code, value)
			}
			mutateIdentity = false
			if code, value := run(publish...); code != 9 || publishes != 1 {
				t.Fatal("Mismatched evidence cleared pending", code, value)
			}
			descriptor, err := c.ResourcePath(resource)
			if err != nil {
				t.Fatal(err)
			}
			directory := "publications"
			if cancel {
				directory = "cancellations"
			}
			blocked := filepath.Join(strings.TrimSuffix(descriptor, filepath.Ext(descriptor))+".asac", directory)
			if err = os.MkdirAll(filepath.Dir(blocked), 0700); err != nil {
				t.Fatal(err)
			}
			if err = os.WriteFile(blocked, []byte("blocked"), 0600); err != nil {
				t.Fatal(err)
			}
			if code, value := run("network", "@"+resource.Alias, "draft", "reconcile"); code != 10 {
				t.Fatal("Lost documentary failure", code, value)
			}
			if err = os.Remove(blocked); err != nil {
				t.Fatal(err)
			}
			if code, value := run("network", "@"+resource.Alias, "draft", "reconcile"); code != 0 {
				t.Fatal(code, value)
			}
			for _, mutation := range []func(map[string]any){
				func(v map[string]any) { v["runtime_digest_scope"] = "network-execution-runtime@1" },
				func(v map[string]any) { v["production_changed"] = true },
				func(v map[string]any) { v["resource_id"] = "invalid" },
				func(v map[string]any) {
					if cancel {
						v["prepared_constituents"] = 99
					} else {
						v["constituent_releases"] = []any{}
					}
				},
				func(v map[string]any) {
					if cancel {
						v["complete"] = false
					} else {
						v["constituent_releases"].([]any)[0].(map[string]any)["runtime_digest"] = "invalid"
					}
				},
			} {
				raw, _ := json.Marshal(current)
				var changed map[string]any
				_ = json.Unmarshal(raw, &changed)
				mutation(changed)
				delete(changed, "receipt_digest")
				scope := "publication-receipt"
				if cancel {
					scope = "publication-cancellation"
				}
				changed["receipt_digest"], _ = asac.Digest(scope, changed)
				validate := devworkspace.ValidatePublicationReceipt
				if cancel {
					validate = devworkspace.ValidatePublicationPreparation
				}
				if err := validate(changed); err == nil {
					t.Fatal("Malformed evidence accepted despite rehashed digest", changed)
				}
			}
			verify := c.VerifyPublicationReceipts
			if cancel {
				verify = c.VerifyPublicationCancellations
			}
			if count, err := verify(resource); err != nil || count != 1 {
				t.Fatal("Missing terminal evidence", count, err)
			}
			if publishes != 1 || resumes+cancels != 1 {
				t.Fatal("Repeated original write", publishes, resumes, cancels)
			}
			files, _ := filepath.Glob(filepath.Join(blocked, "*.yaml"))
			raw, err := os.ReadFile(files[0])
			if err != nil {
				t.Fatal(err)
			}
			raw = []byte(strings.Replace(string(raw), "sha256:"+strings.Repeat("d", 64), "sha256:"+strings.Repeat("a", 64), 1))
			if err = os.WriteFile(files[0], raw, 0600); err != nil {
				t.Fatal(err)
			}
			if _, err := verify(resource); err == nil {
				t.Fatal("Tampered observed evidence accepted")
			}
		})
	}
}
