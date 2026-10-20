package cli

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

const exportUUID = "00000000-0000-4000-8000-000000000001"

func TestPackageExportEnvironmentDefaultsAndLegacyCompatibility(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	bundle, err := packagebundle.Load(localPackageFixture(t), false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	var archive bytes.Buffer
	if err = bundle.Archive(&archive, true); err != nil {
		t.Fatal(err)
	}
	hash := sha256.Sum256(archive.Bytes())
	transport := hex.EncodeToString(hash[:])
	var request packageapi.ExportRequest
	lists := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		data := map[string]any{"package_schema_version": "1.0"}
		switch {
		case strings.HasSuffix(r.URL.Path, "/capabilities"):
			data["schema_catalog_sha256"] = packagefmt.CatalogDigest()
			data["supported_operations"] = []string{"export"}
		case r.URL.Path == "/ai/agents":
			lists++
			if r.URL.Query().Get("project_id") != "project" {
				t.Error("name search escaped project")
			}
			json.NewEncoder(w).Encode(map[string]any{"success": true, "data": []any{map[string]string{"id": exportUUID, "name": "Support"}}})
			return
		case strings.HasSuffix(r.URL.Path, "/export"):
			request = packageapi.ExportRequest{}
			if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
				t.Error(err)
			}
			receipt := packageapi.ExportReceipt{PackageSchemaVersion: "1.0", ExportID: "export", ProjectID: "project", ArtifactDigest: bundle.ArtifactDigest, TransportDigest: transport, SizeBytes: int64(archive.Len()), Inventory: bundle.Inventory, ClosureComplete: true, SelfContained: true, Knowledge: "portable", ExpiresAt: time.Now().Add(time.Hour).Format(time.RFC3339), Source: map[string]any{"environment": *request.Source, "version": request.ReleaseVersion}}
			json.NewEncoder(w).Encode(map[string]any{"success": true, "data": receipt})
			return
		case strings.HasSuffix(r.URL.Path, "/artifact"):
			w.Header().Set("X-Woobe-Transport-Sha256", transport)
			w.Header().Set("X-Woobe-Artifact-Digest", bundle.ArtifactDigest)
			w.Write(archive.Bytes())
			return
		default:
			t.Error(r.URL.Path)
		}
		json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	for _, scenario := range []struct {
		name, target, env, version, packageVersion string
		legacy                                     bool
	}{
		{name: "default", target: exportUUID}, {name: "named", target: "Support", env: "staging"}, {name: "release", target: exportUUID, env: "release", version: "1.2.0"}, {name: "production", target: exportUUID, env: "production"}, {name: "legacy", target: exportUUID, env: "draft", version: "2.0.0", legacy: true},
	} {
		t.Run(scenario.name, func(t *testing.T) {
			directory := t.TempDir()
			t.Chdir(directory)
			args := []string{"package", "export", "agent", scenario.target, "--api-url", server.URL, "--project", "project"}
			if scenario.env != "" {
				flag := "--env"
				if scenario.legacy {
					flag = "--source"
				}
				args = append(args, flag, scenario.env)
			}
			if scenario.version != "" {
				args = append(args, "--version", scenario.version)
			}
			code, result := invoke(t, args, "")
			if code != 0 {
				t.Fatal(code, result)
			}
			if request.TargetID != exportUUID {
				t.Fatal(request)
			}
			expectedEnv := scenario.env
			if expectedEnv == "" {
				expectedEnv = "draft"
			}
			if request.Source == nil || *request.Source != expectedEnv {
				t.Fatal(request)
			}
			if scenario.legacy {
				if request.Version != "2.0.0" || request.ReleaseVersion != "" {
					t.Fatal(request)
				}
			} else if request.ReleaseVersion != scenario.version || request.Name != "" || request.Version != "" {
				t.Fatal(request)
			}
			if _, err := os.Stat(filepath.Join(directory, "support", "woobe.yaml")); err != nil {
				t.Fatal(err)
			}
			code, _ = invoke(t, args, "")
			if code != 2 {
				t.Fatal("existing folder replaced", code)
			}
		})
	}
	if lists != 2 {
		t.Fatal("UUID export must not enumerate resources", lists)
	}
}

func TestPackageExportRejectsBadSelectorsBeforeHTTP(t *testing.T) {
	for _, flags := range [][]string{{"--env", "release"}, {"--env", "staging", "--version", "1"}, {"--env", "production", "--source", "draft"}, {"--env", "other"}} {
		code, result := invoke(t, append([]string{"package", "export", "agent", exportUUID, "--api-url", "http://127.0.0.1:1"}, flags...), "")
		if code != 2 {
			t.Fatal(code, result)
		}
	}
}

func TestPackageNamesMustBeUniqueAndComplete(t *testing.T) {
	for _, scenario := range []string{"duplicate", "missing", "incomplete"} {
		t.Run(scenario, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				rows := []any{}
				if scenario != "missing" {
					rows = []any{map[string]string{"id": exportUUID, "name": "Support"}, map[string]string{"id": "00000000-0000-4000-8000-000000000002", "name": "Support"}}
				}
				data := map[string]any{"items": rows}
				if scenario == "incomplete" {
					data["has_next"] = true
				}
				json.NewEncoder(w).Encode(map[string]any{"data": data})
			}))
			defer server.Close()
			control, _ := controlplane.New(server.URL, "", time.Second)
			client, _ := packageapi.New(control, "project")
			a := New(strings.NewReader(""), &bytes.Buffer{}, &bytes.Buffer{})
			a.NoInput = true
			_, err := a.packageTarget(context.Background(), client, "agent", "Support")
			if err == nil {
				t.Fatal("accepted ambiguous/incomplete/missing name")
			}
			if scenario == "duplicate" && !strings.Contains(err.Error(), exportUUID) {
				t.Fatal(err)
			}
		})
	}
}

func TestPackageBindingsTemplateCanBeFilledAndPlannedOffline(t *testing.T) {
	source := localPackageFixture(t)
	destination := filepath.Join(t.TempDir(), "destination.yaml")
	code, result := invoke(t, []string{"package", "bindings", source, "--destination", destination}, "")
	if code != 0 {
		t.Fatal(code, result)
	}
	data, err := os.ReadFile(destination)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.HasPrefix(data, []byte("format: woobe-package\nschema_version: \"1.0\"\nkind: ImportBindings\n")) || !bytes.Contains(data, []byte("\n  credentials:\n")) {
		t.Fatalf("bindings template is not ordered, two-space block YAML:\n%s", data)
	}
	data = bytes.ReplaceAll(data, []byte("REPLACE_WITH_DESTINATION_CREDENTIAL_UUID"), []byte("00000000-0000-4000-8000-000000000002"))
	if err = os.WriteFile(destination, data, 0600); err != nil {
		t.Fatal(err)
	}
	code, result = invoke(t, []string{"package", "plan", source, "--bindings", destination, "--dry-run"}, "")
	if code != 0 {
		t.Fatal(code, result)
	}
	code, _ = invoke(t, []string{"package", "bindings", source, "--destination", destination}, "")
	if code != 2 {
		t.Fatal("template overwritten")
	}
}

func TestPackageHelpExamplesAndApplicableFlags(t *testing.T) {
	code, text := outputInvoke(t, []string{"package", "export", "agent", "--help"})
	if code != 0 || !strings.Contains(text, "--env release --version v1.0.20261007.01") || strings.Contains(text, "--file string") {
		t.Fatal(code, text)
	}
	code, result := invoke(t, []string{"help", "package", "export", "agent", "--output", "compact"}, "")
	if code != 0 {
		t.Fatal(result)
	}
	data := result["data"].(map[string]any)
	if data["examples"] == nil || data["summary"] == nil {
		t.Fatal(result)
	}
	_, full := invoke(t, []string{"help", "package", "export", "agent", "--output", "json"}, "")
	for _, flag := range full["data"].(map[string]any)["flags"].([]any) {
		if flag.(map[string]any)["name"] == "file" {
			t.Fatal("incompatible flag advertised")
		}
	}
}

func TestPackageSlugIsSafeOnSupportedPlatforms(t *testing.T) {
	for _, name := range []string{"../Orders & Requests Agent", "CON", "LPT1", "", "équipe", "a\\b:c"} {
		slug := packageSlug(name)
		if slug == "" || strings.ContainsAny(slug, "/\\:.") || strings.EqualFold(slug, "con") || strings.EqualFold(slug, "lpt1") {
			t.Fatal(name, slug)
		}
	}
}

func packageStableInvoke(t *testing.T, args []string, config string) (int, map[string]any) {
	t.Helper()
	var out bytes.Buffer
	a := New(strings.NewReader(""), &out, &bytes.Buffer{})
	code := a.Execute(context.Background(), append(args, "--config", config))
	var result map[string]any
	if err := json.Unmarshal(out.Bytes(), &result); err != nil {
		t.Fatal(out.String(), err)
	}
	return code, result
}

func TestPackageAutomaticCheckpointScopeAndSourceNormalization(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	fingerprint := strings.Repeat("b", 64)
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if !strings.HasSuffix(r.URL.Path, "/capabilities") {
			t.Error("unexpected write", r.URL.Path)
		}
		json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"package_schema_version": "1.0", "schema_catalog_sha256": packagefmt.CatalogDigest(), "supported_operations": []string{"apply"}, "principal_fingerprint": fingerprint}})
	}))
	defer server.Close()
	a := New(strings.NewReader(""), &bytes.Buffer{}, &bytes.Buffer{})
	a.ConfigPath = filepath.Join(t.TempDir(), "config.json")
	a.APIURL = server.URL
	a.Project = "project"
	source := localPackageFixture(t)
	first, err := a.automaticPackageCheckpoint(context.Background(), source, "", "draft")
	if err != nil {
		t.Fatal(err)
	}
	second, err := a.automaticPackageCheckpoint(context.Background(), filepath.Join(source, "woobe.yaml"), "", "draft")
	if err != nil || first != second {
		t.Fatal(first, second, err)
	}
	a.Project = "other-project"
	different, err := a.automaticPackageCheckpoint(context.Background(), source, "", "draft")
	if err != nil || first == different {
		t.Fatal(first, different, err)
	}
	a.Project = "project"
	fingerprint = strings.Repeat("c", 64)
	different, err = a.automaticPackageCheckpoint(context.Background(), source, "", "draft")
	if err != nil || first == different {
		t.Fatal(first, different, err)
	}
}

func TestPackageReleaseDiscoveryUsesSelectedProject(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/network/"+exportUUID+"/versions" || r.URL.Query().Get("project_id") != "project" {
			t.Error("release discovery lost project", r.URL)
		}
		json.NewEncoder(w).Encode(map[string]any{"success": true, "data": []any{map[string]string{"version": "v1.0.20261007.01", "kind": "release"}}})
	}))
	defer server.Close()
	code, result := invoke(t, []string{"network", "version", "list", exportUUID, "--api-url", server.URL, "--project", "project"}, "")
	if code != 0 {
		t.Fatal(code, result)
	}
}

func TestPackageHelpGroupsAndAliasesAreFocused(t *testing.T) {
	for _, path := range [][]string{{"package"}, {"agent"}, {"agent", "create"}, {"network", "version", "list"}} {
		args := append([]string{"help"}, path...)
		args = append(args, "--output", "compact")
		code, result := invoke(t, args, "")
		if code != 0 {
			t.Fatal(code, result)
		}
		data := result["data"].(map[string]any)
		if data["summary"] == nil || data["examples"] == nil {
			t.Fatal("help missing guidance", result)
		}
	}
}

func TestPackageReleaseDiscoveryOmitsDefinitionsFromCompactLists(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		json.NewEncoder(w).Encode(map[string]any{"success": true, "data": []any{map[string]any{"id": exportUUID, "version": "v1.0.20261007.01", "kind": "release", "definition": map[string]string{"system_prompt": "large-author-definition"}, "resolved_bindings": map[string]string{"root": "large-binding-snapshot"}}}})
	}))
	defer server.Close()
	for _, mode := range []string{"compact", "json"} {
		code, text := outputInvoke(t, []string{"network", "version", "list", exportUUID, "--api-url", server.URL, "--project", "project", "--output", mode})
		if code != 0 || !strings.Contains(text, "v1.0.20261007.01") {
			t.Fatal(code, text)
		}
		if strings.Contains(text, "large-author-definition") != (mode == "json") {
			t.Fatal(mode, text)
		}
	}
}
