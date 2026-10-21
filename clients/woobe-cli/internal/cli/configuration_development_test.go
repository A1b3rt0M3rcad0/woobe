package cli

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func TestDevelopmentCaptureNegotiatesDefinitionSchemaWithoutSilentFallback(t *testing.T) {
	for _, mode := range []string{"old", "new", "wrong-catalog"} {
		t.Run(mode, func(t *testing.T) {
			exports := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				switch r.URL.Path {
				case "/projects/project/packages/capabilities":
					caps := map[string]any{"package_schema_version": "1.0"}
					if mode != "old" {
						caps["asac"] = map[string]any{"definition_digest_scopes": []string{devworkspace.ConfigurationDefinitionScope}}
						hash := packagefmt.VersionCatalogDigest("2.0")
						if mode == "wrong-catalog" {
							hash = "wrong"
						}
						caps["supported_package_schemas"] = map[string]string{"2.0": hash}
					}
					_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": caps})
				case "/projects/project/packages/export":
					exports++
					var body map[string]any
					_ = json.NewDecoder(r.Body).Decode(&body)
					want := any("2.0")
					if mode == "old" {
						want = nil
					}
					if body["package_schema_version"] != want || body["development"] != true || body["source"] != "production" {
						t.Error(body)
					}
					// Stop after proving the selected export request; no archive is served.
					w.WriteHeader(422)
					_ = json.NewEncoder(w).Encode(map[string]any{"success": false, "message": "fixture rejected"})
				default:
					t.Error("unexpected fallback or request", r.URL.Path)
					w.WriteHeader(500)
				}
			}))
			defer server.Close()
			control, _ := controlplane.New(server.URL, "", time.Second)
			client, _ := packageapi.New(control, "project")
			_, _, err := developmentCapture(context.Background(), client, "agent", "agent-id", "production", "")
			if err == nil {
				t.Fatal("fixture should stop export")
			}
			want := 1
			if mode == "wrong-catalog" {
				want = 0
			}
			if exports != want {
				t.Fatal("unexpected export/fallback", exports)
			}
		})
	}
}

func TestConfigurationCandidateUsesSealedReferencesOnly(t *testing.T) {
	t.Setenv("TOKEN", "must-not-resolve")
	spec := map[string]any{"configuration": map[string]any{"keys": []any{map[string]any{"key": "TOKEN"}}}, "connections": map[string]any{"provider": map[string]any{}}}
	manifest := map[string]any{"schema_version": "2.0", "spec": spec}
	id := "01a0a033-5820-770c-854b-902864857273"
	bindings, err := candidateManifestBindings(manifest, map[string]string{"provider": id})
	if err != nil {
		t.Fatal(err)
	}
	bound := packagefmt.Object(bindings["spec"])
	if bindings["schema_version"] != "2.0" || bound["secrets"] != nil || packagefmt.Object(packagefmt.Object(bound["project_environment"])["TOKEN"])["create"] != false {
		t.Fatal(bindings)
	}
	if _, err = candidateManifestBindings(manifest, nil); err == nil {
		t.Fatal("inferred missing provider authority")
	}
	if asacSupportsDefinition(map[string]any{"definition_digest_scope": devworkspace.PortableDefinitionScope}, devworkspace.ConfigurationDefinitionScope) {
		t.Fatal("old server accepted new scope")
	}
}

func TestConfigurationBindingsTemplatePreservesSchemaAndRemoteChoices(t *testing.T) {
	raw, err := os.ReadFile("../../testdata/asac-portable-definition-v2.json")
	if err != nil {
		t.Fatal(err)
	}
	var fixture struct {
		Files map[string]string `json:"files"`
	}
	if err = json.Unmarshal(raw, &fixture); err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	for name, value := range fixture.Files {
		if err = os.WriteFile(filepath.Join(dir, name), []byte(value), 0600); err != nil {
			t.Fatal(err)
		}
	}
	destination := filepath.Join(t.TempDir(), "bindings.yaml")
	code, response := invoke(t, []string{"package", "bindings", dir, "--destination", destination}, "")
	if code != 0 {
		t.Fatal(code, response)
	}
	data, err := os.ReadFile(destination)
	if err != nil {
		t.Fatal(err)
	}
	if strings.Contains(string(data), "protected_ref") || strings.Contains(string(data), "local-value") || !strings.Contains(string(data), "create: true") {
		t.Fatal("unsafe configuration template")
	}
	code, response = invoke(t, []string{"package", "plan", dir, "--structural", "--bindings", destination, "--dry-run"}, "")
	if code != 0 {
		t.Fatal(code, response)
	}
}
