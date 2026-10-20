package cli

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestConfigurationDeclareNegotiatesBeforeMutationAndSendsNoMaterial(t *testing.T) {
	requests := []string{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests = append(requests, r.Method+" "+r.URL.Path)
		data := map[string]any{"schema_version": "project_configuration.v1", "declaration_without_value": true}
		if r.Method == "POST" {
			var body map[string]any
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			if body["key"] != "PRIMARY_API_KEY" || body["kind"] != "secret" || len(body) != 4 {
				t.Error(body)
			}
			data = map[string]any{"id": "key-id", "key": "PRIMARY_API_KEY", "kind": "secret"}
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	code, result := invoke(t, []string{"project", "configuration", "declare", "PRIMARY_API_KEY", "--project", "p", "--api-url", server.URL, "--output", "json"}, "")
	if code != 0 {
		t.Fatal(result)
	}
	if len(requests) != 2 || !strings.HasSuffix(requests[0], "/capabilities") || requests[1] != "POST /core/projects/p/configuration/keys" {
		t.Fatal(requests)
	}
}

func TestConfigurationOldServerNeverFallsBackOrWrites(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if r.Method != "GET" || !strings.HasSuffix(r.URL.Path, "/capabilities") {
			t.Error("unexpected request", r.Method, r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"schema_version": "older"}})
	}))
	defer server.Close()
	code, result := invoke(t, []string{"project", "configuration", "declare", "PRIMARY_API_KEY", "--project", "p", "--api-url", server.URL, "--output", "json"}, "")
	if code != 9 || requests != 1 {
		t.Fatal(code, result, requests)
	}
}

func TestConfigurationListScopeAndRejectMaterialBeforeRendering(t *testing.T) {
	for _, format := range []string{"json", "text", "compact", "table"} {
		t.Run(format, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				data := map[string]any{"schema_version": "project_configuration.v1", "declaration_without_value": true}
				if strings.HasSuffix(r.URL.Path, "/keys") {
					if r.URL.Query().Get("environment") != "staging" || r.URL.Query().Get("limit") != "7" {
						t.Error(r.URL.RawQuery)
					}
					data = map[string]any{"items": []any{map[string]any{"key": "API_KEY", "value": "private-canary"}}}
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
			}))
			defer server.Close()
			code, rendered := secretPlanRun(t, []string{"project", "configuration", "list", "--env", "staging", "--limit", "7", "--project", "p", "--api-url", server.URL, "--output", format}, "")
			if code != 9 || strings.Contains(rendered, "private-canary") {
				t.Fatal(code, rendered)
			}
		})
	}
}

func TestConfigurationRejectsLocalValueFileBeforeReading(t *testing.T) {
	code, result := invoke(t, []string{"project", "configuration", "declare", "API_KEY", "--file", "does-not-exist", "--dry-run", "--output", "json"}, "")
	if code != 2 || !strings.Contains(result["error"].(map[string]any)["message"].(string), "does not accept --file") {
		t.Fatal(result)
	}
}

func TestConfigurationCheckUsesExactTargetEnvironmentAndFailClosedStates(t *testing.T) {
	for state, wantCode := range map[string]int{"ready": 0, "ready_with_notices": 0, "blocked": 6, "unknown": 9, "unexpected": 9} {
		t.Run(state, func(t *testing.T) {
			requests := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				requests++
				if r.Method != "GET" || r.URL.Query().Get("environment") != "production" {
					t.Error(r.Method, r.URL.String())
				}
				data := map[string]any{"schema_version": "project_configuration.v1", "declaration_without_value": true, "target_readiness": true}
				if requests == 2 {
					if !strings.HasSuffix(r.URL.Path, "/readiness/network/11111111-1111-4111-8111-111111111111") {
						t.Error(r.URL.Path)
					}
					data = map[string]any{"state": state, "environment": "production", "missing_key_count": 1}
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
			}))
			defer server.Close()
			code, result := invoke(t, []string{"project", "configuration", "check", "network", "11111111-1111-4111-8111-111111111111", "--env", "production", "--project", "p", "--api-url", server.URL, "--output", "json"}, "")
			if code != wantCode || requests != 2 {
				t.Fatal(code, requests, result)
			}
			if state != "unexpected" && result["data"].(map[string]any)["state"] != state {
				t.Fatal(result)
			}
		})
	}
}

func TestConfigurationCheckRequiresReadinessCapabilityBeforeTargetRequest(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{
			"schema_version": "project_configuration.v1", "declaration_without_value": true}})
	}))
	defer server.Close()
	code, result := invoke(t, []string{"project", "configuration", "check", "agent", "11111111-1111-4111-8111-111111111111", "--project", "p", "--api-url", server.URL, "--output", "json"}, "")
	if code != 9 || requests != 1 {
		t.Fatal(code, requests, result)
	}
}

func TestConfigurationBindingUsesServerRevisionAndRemoteKeysOnly(t *testing.T) {
	id := "01a00d46-b804-7f4c-b5bd-e3c814db9f0f"
	requests := []string{}
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests = append(requests, r.Method)
		data := map[string]any{"schema_version": "project_configuration.v1", "declaration_without_value": true, "binding_updates": true}
		if strings.Contains(r.URL.Path, "/bindings/") {
			data = map[string]any{"revision": "7"}
			if r.Method == "PUT" {
				var body map[string]any
				if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
					t.Fatal(err)
				}
				if body["expected_revision"] != "7" {
					t.Error(body)
				}
				auth := body["authentication"].(map[string]any)
				fields := auth["fields"].(map[string]any)
				ref := fields["api_key"].(map[string]any)
				if ref["source"] != "project_environment" || ref["key"] != "PRIMARY_KEY" || len(ref) != 2 {
					t.Error(ref)
				}
				data = map[string]any{"revision": "8", "authentication": auth}
			}
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	code, result := invoke(t, []string{"project", "configuration", "bind", "provider", id, "--key", "PRIMARY_KEY", "--project", "p", "--api-url", server.URL, "--output", "json"}, "")
	if code != 0 || strings.Join(requests, ",") != "GET,GET,PUT" {
		t.Fatal(code, result, requests)
	}
}

func TestConfigurationBindingUnsupportedServerNeverMutates(t *testing.T) {
	writes := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			writes++
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"schema_version": "project_configuration.v1", "declaration_without_value": true}})
	}))
	defer server.Close()
	code, result := invoke(t, []string{"project", "configuration", "bind", "provider", "01a00d46-b804-7f4c-b5bd-e3c814db9f0f", "--key", "PRIMARY_KEY", "--project", "p", "--api-url", server.URL}, "")
	if code != 9 || writes != 0 {
		t.Fatal(code, result, writes)
	}
}

func TestConfigurationExternalTestNegotiatesAndReportsFailure(t *testing.T) {
	for _, state := range []string{"valid", "ready", "configuration_required", "unknown", "unsupported"} {
		t.Run(state, func(t *testing.T) {
			requests := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				requests++
				if r.URL.Query().Get("environment") != "staging" {
					t.Error(r.URL.RawQuery)
				}
				data := map[string]any{"schema_version": "project_configuration.v1", "declaration_without_value": true, "external_validation": state != "unsupported"}
				if r.Method == "POST" {
					if !strings.HasSuffix(r.URL.Path, "/tests/tool/11111111-1111-4111-8111-111111111111") {
						t.Error(r.URL.Path)
					}
					var body map[string]any
					if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
						t.Fatal(err)
					}
					if len(body) != 1 || body["environment"] != "staging" {
						t.Error(body)
					}
					data = map[string]any{"state": state}
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
			}))
			defer server.Close()
			code, result := invoke(t, []string{"project", "configuration", "test", "tool", "11111111-1111-4111-8111-111111111111", "--env", "staging", "--project", "p", "--api-url", server.URL, "--output", "json"}, "")
			want, calls := 0, 2
			if state == "configuration_required" {
				want = 6
			}
			if state == "unknown" || state == "unsupported" {
				want = 9
			}
			if state == "unsupported" {
				calls = 1
			}
			if code != want || requests != calls {
				t.Fatal(code, requests, result)
			}
		})
	}
}

func TestKnowledgePreparationAcceptsYAMLAndQueuesOneExplicitRequest(t *testing.T) {
	calls := 0
	id := "00000000-0000-4000-8000-000000000001"
	hash := strings.Repeat("a", 64)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.URL.Path == "/openapi.json" {
			_ = json.NewEncoder(w).Encode(map[string]any{"paths": map[string]any{"/agent/knowledge/vector-snapshots/{snapshot_id}/prepare": map[string]any{"post": map[string]any{"operationId": "prepare_vector_snapshot"}}}})
			return
		}
		if r.Method != "POST" || r.URL.Path != "/agent/knowledge/vector-snapshots/"+id+"/prepare" {
			t.Error(r.Method, r.URL.Path)
		}
		var body map[string]any
		if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
			t.Fatal(err)
		}
		if body["expected_build_config_hash"] != hash || body["environment"] != "staging" {
			t.Error(body)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"id": id, "status": "BUILDING", "runtime_preparation_status": "pending"}})
	}))
	defer server.Close()
	code, result := invoke(t, []string{"project", "knowledge", "snapshot", "prepare", id, "--api-url", server.URL, "--project", id, "--file", "-", "--input-format", "yaml", "--output", "json"}, "project_id: "+id+"\nenvironment: staging\nexpected_build_config_hash: "+hash+"\n")
	if code != 0 || calls != 2 {
		t.Fatal(code, result, calls)
	}
}

func TestKnowledgePreparationRejectsUnadvertisedServerBeforeWriting(t *testing.T) {
	calls := 0
	id := "00000000-0000-4000-8000-000000000001"
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.Method != "GET" || r.URL.Path != "/openapi.json" {
			t.Error("unexpected write", r.Method, r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"paths": map[string]any{}})
	}))
	defer server.Close()
	code, result := invoke(t, []string{"project", "knowledge", "snapshot", "prepare", id, "--api-url", server.URL, "--project", id, "--file", "-", "--input-format", "yaml", "--output", "json"}, "project_id: "+id+"\nexpected_build_config_hash: "+strings.Repeat("a", 64)+"\n")
	if code == 0 || calls != 1 {
		t.Fatal(code, result, calls)
	}
}

func TestConfigurationSummaryScopesCapabilityCountsAndFailureStates(t *testing.T) {
	for _, tc := range []struct {
		name, state          string
		advertised, complete bool
		code, requests       int
	}{
		{"ready", "ready", true, true, 0, 2}, {"notices", "ready_with_notices", true, true, 0, 2},
		{"blocked", "blocked", true, true, 6, 2}, {"truncated", "unknown", true, false, 9, 2},
		{"false-ready", "ready", true, false, 9, 2}, {"unsupported", "ready", false, true, 9, 1},
	} {
		t.Run(tc.name, func(t *testing.T) {
			requests := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				requests++
				if r.Method != "GET" || r.URL.Query().Get("environment") != "staging" {
					t.Error("unexpected operation")
				}
				data := map[string]any{"schema_version": "project_configuration.v1", "declaration_without_value": true, "project_summary": tc.advertised}
				if strings.HasSuffix(r.URL.Path, "/summary") {
					data = map[string]any{"scope": "current_selections", "environment": "staging", "state": tc.state, "complete": tc.complete,
						"inspected_target_count": 2, "unselected_target_count": 0, "affected_target_count": 0,
						"blocked_key_count": 0, "missing_key_count": 0, "required_key_count": 0, "affected_consumer_count": 0}
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
			}))
			defer server.Close()
			code, result := invoke(t, []string{"project", "configuration", "summary", "--env", "staging", "--project", "p", "--api-url", server.URL, "--output", "json"}, "")
			if code != tc.code || requests != tc.requests {
				t.Fatal(code, result, requests)
			}
		})
	}
}

func TestConfigurationSummaryRejectsInvalidCountsAndCrossEnvironmentReply(t *testing.T) {
	base := map[string]any{"scope": "current_selections", "environment": "draft", "state": "ready", "complete": true,
		"inspected_target_count": 0, "unselected_target_count": 0, "affected_target_count": 0,
		"blocked_key_count": 0, "missing_key_count": 0, "required_key_count": 0, "affected_consumer_count": 0}
	if !validConfigurationSummary(base, "draft") || validConfigurationSummary(base, "production") {
		t.Fatal("Environment mismatch")
	}
	for _, invalid := range []any{nil, -1, 0.5, "0", json.Number("9007199254740992")} {
		base["required_key_count"] = invalid
		if validConfigurationSummary(base, "draft") {
			t.Fatal("invalid count accepted")
		}
	}
}

func TestConfigurationSummaryPaginationIsExplicitAndNeverQualifiesLastPage(t *testing.T) {
	for _, advertised := range []bool{false, true} {
		t.Run(fmt.Sprint(advertised), func(t *testing.T) {
			requests := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				requests++
				data := map[string]any{"schema_version": "project_configuration.v1", "declaration_without_value": true,
					"project_summary": true, "project_summary_pagination": advertised}
				if strings.HasSuffix(r.URL.Path, "/summary") {
					if r.URL.Query().Get("cursor") != "previous-page" || r.URL.Query().Get("limit") != "2" {
						t.Error("page selectors not preserved")
					}
					data = map[string]any{"scope": "current_selections_page", "environment": "staging", "state": "unknown", "complete": false,
						"page_state": "ready", "page_complete": true, "has_next": false, "next_cursor": nil,
						"inspected_target_count": 2, "unselected_target_count": 2, "affected_target_count": 0,
						"blocked_key_count": 0, "missing_key_count": 0, "required_key_count": 0, "affected_consumer_count": 0}
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
			}))
			defer server.Close()
			code, result := invoke(t, []string{"project", "configuration", "summary", "--env", "staging", "--cursor", "previous-page", "--limit", "2",
				"--project", "p", "--api-url", server.URL, "--output", "json"}, "")
			if code != 9 || (advertised && requests != 2) || (!advertised && requests != 1) {
				t.Fatal(code, result, requests)
			}
		})
	}
}

func TestConfigurationSummaryRejectsPagePretendingToBeGlobalEvidence(t *testing.T) {
	base := map[string]any{"scope": "current_selections_page", "environment": "draft", "state": "unknown", "complete": false,
		"page_state": "ready", "page_complete": true, "has_next": true, "next_cursor": "next-page",
		"inspected_target_count": 1, "unselected_target_count": 1, "affected_target_count": 0,
		"blocked_key_count": 0, "missing_key_count": 0, "required_key_count": 0, "affected_consumer_count": 0}
	if !validConfigurationSummary(base, "draft") {
		t.Fatal("valid page rejected")
	}
	for _, changed := range []map[string]any{{"state": "ready"}, {"complete": true}, {"next_cursor": nil},
		{"page_complete": nil}, {"has_next": false}, {"scope": "current_selections"}} {
		copy := map[string]any{}
		for key, value := range base {
			copy[key] = value
		}
		for key, value := range changed {
			copy[key] = value
		}
		if validConfigurationSummary(copy, "draft") {
			t.Fatal("partial observation accepted", changed)
		}
	}
}

func TestConfigurationRouteBindingNegotiatesAndPreservesRouteCAS(t *testing.T) {
	for _, supported := range []bool{false, true} {
		t.Run(fmt.Sprint(supported), func(t *testing.T) {
			requests := []string{}
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				requests = append(requests, r.Method)
				data := map[string]any{"schema_version": "project_configuration.v1", "declaration_without_value": true,
					"binding_updates": true, "route_authentication_bindings": supported}
				if strings.Contains(r.URL.Path, "/bindings/") {
					data = map[string]any{"revision": "route-revision"}
					if r.Method == "GET" && r.URL.Query().Get("route_id") != "orders/read" {
						t.Error("route read lost scope")
					}
					if r.Method == "PUT" {
						var body map[string]any
						if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
							t.Fatal(err)
						}
						if body["route_id"] != "orders/read" || body["expected_revision"] != "route-revision" {
							t.Error(body)
						}
					}
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
			}))
			defer server.Close()
			code, result := invoke(t, []string{"project", "configuration", "bind", "tool",
				"01a00d46-b804-7f4c-b5bd-e3c814db9f0f", "--route", "orders/read", "--type", "bearer", "--field", "token=ORDER_TOKEN",
				"--project", "p", "--api-url", server.URL, "--output", "json"}, "")
			if supported {
				if code != 0 || strings.Join(requests, ",") != "GET,GET,PUT" {
					t.Fatal(code, result, requests)
				}
			} else if code != 9 || strings.Join(requests, ",") != "GET" {
				t.Fatal(code, result, requests)
			}
		})
	}
}
