package cli

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

func localPackageFixture(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	files := map[string]string{
		"woobe.yaml": `{"format":"woobe-package","schema_version":"1.0","kind":"Package","metadata":{"name":"support","version":"1.0.0"},"spec":{"entrypoint":{"kind":"Agent","ref":"support"},"resources":["agent.yaml","model.yaml"],"requires":{"credentials":[{"ref":"primary-key","provider":"openai_compatible"}]}}}`,
		"agent.yaml": `{"format":"woobe-package","schema_version":"1.0","kind":"Agent","metadata":{"key":"support","name":"Support"},"spec":{"legacy_system_prompt":"Answer","model":{"primary":{"ref":"primary"}}}}`,
		"model.yaml": `{"format":"woobe-package","schema_version":"1.0","kind":"Model","metadata":{"key":"primary","name":"Primary"},"spec":{"provider":"openai_compatible","model":"fake","credential":{"ref":"primary-key"}}}`,
	}
	for name, data := range files {
		if err := os.WriteFile(filepath.Join(root, name), []byte(data), 0600); err != nil {
			t.Fatal(err)
		}
	}
	return root
}

func TestPackageValidateIsOfflineAndDoesNotOpenCredentials(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { requests++ }))
	defer server.Close()
	for _, extra := range [][]string{nil, {"--dry-run"}} {
		args := []string{"package", "validate", localPackageFixture(t), "--api-url", server.URL, "--credential", "missing-private-reference"}
		code, result := invoke(t, append(args, extra...), "")
		if code != 0 || requests != 0 {
			t.Fatal(code, result, requests)
		}
		data := result["data"].(map[string]any)
		if result["schema_version"] != "1" || data["package_schema_version"] != "1.0" || data["executed"] != false {
			t.Fatal(result)
		}
	}
}

func TestPackageValidateRejectsInheritedBodyAndReportsSafeDiagnostics(t *testing.T) {
	root := localPackageFixture(t)
	code, _ := invoke(t, []string{"package", "validate", root, "--file", "-"}, "")
	if code != 2 {
		t.Fatal(code)
	}
	if err := os.WriteFile(filepath.Join(root, "agent.yaml"), []byte("a: first\na: secret-do-not-echo\n"), 0600); err != nil {
		t.Fatal(err)
	}
	code, result := invoke(t, []string{"package", "validate", root}, "")
	if code != 2 {
		t.Fatal(result)
	}
	diagnostic := result["data"].(map[string]any)["diagnostics"].([]any)[0].(map[string]any)
	if diagnostic["code"] != "PACKAGE_PARSE_INVALID" || diagnostic["file"] != "agent.yaml" {
		t.Fatal(diagnostic)
	}
}
