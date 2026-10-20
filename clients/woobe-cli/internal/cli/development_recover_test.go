package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func TestBindingRecoveryPreservesAcceptedGenerationWithoutForgingAuthorBase(t *testing.T) {
	id := "01a00d46-1ed7-71f7-99a4-aaa2cf81637c"
	snapshot := "01a00d46-b804-7f4c-b5bd-e3c814db9f0f"
	nodes := []*devworkspace.Node{{Resource: devworkspace.Resource{UID: "root", Kind: "Network"}}, {Resource: devworkspace.Resource{UID: "frozen", Kind: "Agent", Frozen: true, SnapshotID: snapshot}}, {Resource: devworkspace.Resource{UID: "provider", Kind: "Provider"}}}
	state := &devworkspace.State{Bindings: map[string]devworkspace.Binding{}, Credentials: map[string]string{"private": "unchanged"}}
	good := []packageapi.RegistryBinding{{ResourceUID: "root", Kind: "Network", ResourceID: id, OperationID: id, DefinitionDigest: strings.Repeat("a", 64), GenerationScope: "accepted_native_phase", AcceptedRevision: 7, Revision: 7, CurrentRevision: 8, BindingStatus: "resource_changed"}, {ResourceUID: "frozen", Kind: "Agent", ResourceID: id, OperationID: id, DefinitionDigest: strings.Repeat("a", 64), GenerationScope: "accepted_native_phase", AcceptedRevision: 1, Revision: 1, BindingStatus: "frozen_snapshot", Frozen: true, SnapshotID: snapshot, SourceKind: "release", FrozenEvidenceRetained: true}}
	recovered, stale, err := recoveredDevelopmentBindings(nodes, state, packageapi.Registry{Resources: good})
	if err != nil || stale != 1 || recovered["root"].Revision != 7 || recovered["root"].Base != nil || recovered["frozen"].SnapshotID != snapshot || len(state.Bindings) != 0 || !reflect.DeepEqual(state.Credentials, map[string]string{"private": "unchanged"}) {
		t.Fatal(recovered, stale, state, err)
	}
	cases := map[string]func([]packageapi.RegistryBinding) []packageapi.RegistryBinding{
		"missing_dependency":  func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding { return v[:1] },
		"duplicate":           func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding { return append(v, v[1]) },
		"current_as_accepted": func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding { v[0].Revision = 8; return v },
		"unsealed": func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding {
			v[0].GenerationScope = "unsealed_native_binding"
			return v
		},
		"another_snapshot":     func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding { v[1].SnapshotID = id; return v },
		"mutable_substitution": func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding { v[1].Frozen = false; return v },
		"wrong_kind":           func(v []packageapi.RegistryBinding) []packageapi.RegistryBinding { v[1].Kind = "Tool"; return v },
	}
	for name, mutate := range cases {
		t.Run(name, func(t *testing.T) {
			result, _, err := recoveredDevelopmentBindings(nodes, state, packageapi.Registry{Resources: mutate(append([]packageapi.RegistryBinding{}, good...))})
			if err == nil || result != nil || len(state.Bindings) != 0 {
				t.Fatal("partial or forged recovery", result, err)
			}
		})
	}
	state.Bindings["root"] = devworkspace.Binding{ResourceID: snapshot, Revision: 7}
	if _, _, err := recoveredDevelopmentBindings(nodes, state, packageapi.Registry{Resources: good}); err == nil {
		t.Fatal("overwrote contradictory destination")
	}
}

func TestBindingRecoveryCommandFreshStateIsReadOnlyAndRejectsUncertainWrites(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	var registry packageapi.Registry
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if r.Method != "GET" {
			t.Error("recovery attempted remote mutation", r.Method)
			w.WriteHeader(500)
			return
		}
		var data any
		if strings.HasSuffix(r.URL.Path, "/capabilities") {
			data = map[string]any{"package_schema_version": "1.0", "schema_catalog_sha256": packagefmt.CatalogDigest(), "principal_fingerprint": strings.Repeat("a", 64), "supported_operations": []string{"sync"}, "asac": map[string]any{"schema_version": "1.0", "accepted_binding_generations": true, "definition_digest_scope": devworkspace.PortableDefinitionScope}}
		} else if strings.Contains(r.URL.Path, "/registries/") {
			data = map[string]any{"package_schema_version": "1.0", "registry_id": registry.RegistryID, "resources": registry.Resources}
		} else {
			t.Error("unexpected request", r.URL.Path)
		}
		json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	c, state, resource := asacWorkspace(t, server.URL)
	graph, err := devworkspace.LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	nodes, err := graph.Closure(resource.Key)
	if err != nil {
		t.Fatal(err)
	}
	registry.RegistryID = c.RegistryID
	for _, node := range nodes {
		if node.Resource.Kind == "Provider" {
			continue
		}
		native, _ := devworkspace.NewID()
		if node.Resource.UID == resource.UID {
			native = state.Bindings[resource.UID].ResourceID
		}
		registry.Resources = append(registry.Resources, packageapi.RegistryBinding{ResourceUID: node.Resource.UID, Kind: node.Resource.Kind, ResourceID: native, OperationID: native, DefinitionDigest: strings.Repeat("a", 64), Revision: 7, AcceptedRevision: 7, CurrentRevision: 8, GenerationScope: "accepted_native_phase", BindingStatus: "resource_changed"})
	}
	if err := os.Remove(c.StatePath(state.API, state.Workspace, state.Project)); err != nil {
		t.Fatal(err)
	}
	flags := []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}
	run := func(extra ...string) (int, map[string]any) {
		return invoke(t, append(append([]string{"agent", resource.UID, "bindings", "recover"}, flags...), extra...), "")
	}
	if code, result := run("--dry-run"); code != 0 || result["data"].(map[string]any)["bindings_recovered"] != false {
		t.Fatal(code, result)
	}
	if _, err := os.Stat(c.StatePath(state.API, state.Workspace, state.Project)); !os.IsNotExist(err) {
		t.Fatal("dry-run wrote state", err)
	}
	if code, result := run(); code != 0 || result["data"].(map[string]any)["author_base"] != "not_recovered" {
		t.Fatal(code, result)
	}
	recovered, err := c.ReadState(state.API, state.Workspace, state.Project)
	if err != nil || recovered.Bindings[resource.UID].Base != nil || recovered.Bindings[resource.UID].Revision == nil || len(recovered.Credentials) != 0 || len(recovered.Requirements) == 0 {
		t.Fatal(recovered, err)
	}
	if err := c.WriteOperationalFile(asacPrivatePath(c, recovered, resource.UID, "pending"), []byte("{}")); err != nil {
		t.Fatal(err)
	}
	if code, result := run(); code != 0 || result["data"].(map[string]any)["bindings_recovered"] != true {
		t.Fatal("cleared checkpoint blocked recovery", code, result)
	}
	for _, checkpoint := range []string{`{"operation_id":"01a00d46-1ed7-71f7-99a4-aaa2cf81637c"}`, `{"action":"save"}`, `null`, `{`, `{} {}`} {
		if err := c.WriteOperationalFile(asacPrivatePath(c, recovered, resource.UID, "pending"), []byte(checkpoint)); err != nil {
			t.Fatal(err)
		}
		before := requests
		if code, result := run(); code != 9 || requests != before {
			t.Fatal("uncertain write did not block recovery", code, result, requests, before)
		}
	}
}
