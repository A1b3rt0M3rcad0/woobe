package cli

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func TestPackageCompatibilityDistinguishesWindowsCatalogAndAuthority(t *testing.T) {
	crlf := sha256.Sum256(bytes.ReplaceAll(packagefmt.CatalogBytes(), []byte("\n"), []byte("\r\n")))
	for _, tc := range []struct {
		name, digest, principal, message string
		code                             int
	}{
		{"compatible", packagefmt.CatalogDigest(), strings.Repeat("a", 64), "", 0},
		{"crlf", hex.EncodeToString(crlf[:]), strings.Repeat("a", 64), "Windows CRLF", 9},
		{"different", strings.Repeat("b", 64), strings.Repeat("a", 64), "matching Package schemas", 9},
		{"authority", packagefmt.CatalogDigest(), "", "authority fingerprint", 9},
		{"invalid hex authority", packagefmt.CatalogDigest(), strings.Repeat("z", 64), "authority fingerprint", 9},
	} {
		t.Run(tc.name, func(t *testing.T) {
			s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method != "GET" || r.URL.Path != "/projects/project/packages/capabilities" {
					t.Errorf("unexpected request: %s %s", r.Method, r.URL.Path)
				}
				json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"package_schema_version": "1.0", "schema_catalog_sha256": tc.digest, "principal_fingerprint": tc.principal, "supported_operations": []string{"sync"}}})
			}))
			defer s.Close()
			control, err := controlplane.New(s.URL, "", 0)
			if err != nil {
				t.Fatal(err)
			}
			client, err := packageapi.New(control, "project")
			if err != nil {
				t.Fatal(err)
			}
			_, err = developmentCapabilities(context.Background(), client)
			if tc.code == 0 && err != nil {
				t.Fatal(err)
			}
			if tc.code != 0 && (err == nil || !strings.Contains(err.Error(), tc.message)) {
				t.Fatal(err)
			}
			code, result := invoke(t, []string{"package", "doctor", "--no-project-config", "--api-url", s.URL, "--project", "project", "--output", "json"}, "")
			if (tc.code == 0 && code != 0) || (tc.code != 0 && code != 10) {
				t.Fatal(code, result)
			}
			data := result["data"].(map[string]any)
			if data["compatible"] != (tc.code == 0) {
				t.Fatal(data)
			}
			if _, exists := data["principal_fingerprint"]; exists {
				t.Fatal("exposed authority fingerprint")
			}
			if tc.name == "crlf" && data["catalog_status"] != "windows_crlf" {
				t.Fatal(data)
			}
		})
	}
}

func TestPackageDoctorUsesPinnedContextAndExplicitOverride(t *testing.T) {
	t.Chdir(t.TempDir())
	t.Setenv("WOOBE_CONTEXT", "")
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" {
			t.Error("diagnostic mutated server")
		}
		json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"package_schema_version": "1.0", "schema_catalog_sha256": packagefmt.CatalogDigest(), "principal_fingerprint": strings.Repeat("a", 64), "supported_operations": []string{"sync"}}})
	}))
	defer s.Close()
	_, err := devworkspace.Create(".", ".woobe", "pinned")
	if err != nil {
		t.Fatal(err)
	}
	cfg := filepath.Join(t.TempDir(), "config.json")
	err = config.Save(cfg, config.Config{Version: 1, Current: "current", Contexts: map[string]config.Context{
		"pinned": {APIURL: s.URL, Project: "pinned-project"}, "current": {APIURL: s.URL, Project: "current-project"},
	}})
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		extra            []string
		context, project string
	}{
		{nil, "pinned", "pinned-project"},
		{[]string{"--context", "current"}, "current", "current-project"},
		{[]string{"--no-project-config"}, "current", "current-project"},
	} {
		out := &bytes.Buffer{}
		a := New(strings.NewReader(""), out, &bytes.Buffer{})
		args := append([]string{"package", "doctor", "--config", cfg, "--output", "json"}, tc.extra...)
		if code := a.Execute(context.Background(), args); code != 0 {
			t.Fatal(code, out.String())
		}
		var result map[string]any
		if err := json.Unmarshal(out.Bytes(), &result); err != nil {
			t.Fatal(err)
		}
		data := result["data"].(map[string]any)
		if data["context"] != tc.context || data["project_id"] != tc.project {
			t.Fatal(data)
		}
		if _, err := os.Stat(filepath.Join(".woobe", ".state")); !os.IsNotExist(err) {
			t.Fatalf("read-only diagnostic created operational state: %v", err)
		}
	}
}
