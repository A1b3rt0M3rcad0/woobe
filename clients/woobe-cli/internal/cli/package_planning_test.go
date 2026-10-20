package cli

import (
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

const packageBindingShortcut = "credential.primary-key=00000000-0000-4000-8000-000000000001"

func TestPackagePlanDryRunNeverLoadsCredentialsOrHTTP(t *testing.T) {
	var requests atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) { requests.Add(1) }))
	defer server.Close()
	code, result := invoke(t, []string{"package", "plan", localPackageFixture(t), "--bind", packageBindingShortcut, "--dry-run", "--credential", "missing", "--api-url", server.URL}, "")
	if code != 0 || requests.Load() != 0 || result["data"].(map[string]any)["executed"] != false {
		t.Fatal(code, result, requests.Load())
	}
}

func TestPackagePlanRejectsDuplicateBindingsAndMissingAuditBeforeHTTP(t *testing.T) {
	for _, extra := range [][]string{{"--bind", packageBindingShortcut, "--bind", packageBindingShortcut}, {"--bind", packageBindingShortcut, "--lifecycle", "production"}, {"--dry-run", "--validate-body"}} {
		args := append([]string{"package", "plan", localPackageFixture(t), "--credential", "missing"}, extra...)
		code, result := invoke(t, args, "")
		if code != 2 {
			t.Fatal(code, result)
		}
	}
}

func TestPackagePlanUploadsCapturedClosureAndSavesPrivateReceipt(t *testing.T) {
	t.Setenv("WOOBE_CONTROL_KEY", "test-control-key")
	var uploads atomic.Int32
	var server *httptest.Server
	server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		data := map[string]any{"package_schema_version": "1.0"}
		switch {
		case strings.HasSuffix(r.URL.Path, "/capabilities"):
			data["schema_catalog_sha256"] = packagefmt.CatalogDigest()
			data["supported_operations"] = []string{"plan"}
			data["principal_fingerprint"] = strings.Repeat("b", 64)
		case strings.HasSuffix(r.URL.Path, "/uploads"):
			if err := r.ParseMultipartForm(16 << 20); err != nil {
				t.Error(err)
				return
			}
			defer r.MultipartForm.RemoveAll()
			file, _, err := r.FormFile("file")
			if err != nil {
				t.Error(err)
				return
			}
			defer file.Close()
			captured, err := packagebundle.ReceiveArchive(file, true)
			if err != nil {
				t.Error(err)
				return
			}
			defer captured.Close()
			uploads.Add(1)
			data["upload_id"] = "00000000-0000-4000-8000-000000000002"
			data["project_id"] = "project"
			data["artifact_digest"] = captured.ArtifactDigest
			data["inventory"] = captured.Inventory
			data["expires_at"] = time.Now().Add(time.Hour).UTC().Format(time.RFC3339)
		case strings.HasSuffix(r.URL.Path, "/plan"):
			var request packageapi.PlanRequest
			if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
				t.Error(err)
				return
			}
			encoded, _ := json.Marshal(request)
			_ = json.Unmarshal(encoded, &data)
			data["package_schema_version"] = "1.0"
			data["api_origin"] = server.URL
			data["project_id"] = "project"
			data["plan_id"] = "plan"
			data["plan_digest"] = strings.Repeat("c", 64)
			data["definition_digest"] = strings.Repeat("d", 64)
			data["capabilities_digest"] = strings.Repeat("e", 64)
			data["bindings_digest"], _ = packageapi.BindingsDigest(data["bindings"].(map[string]any))
			data["effects"] = []any{map[string]any{"key": "model.primary", "owner": "agent", "action": "resolve_model", "permission": "model:write", "state": "materializing"}}
			data["created_at"] = time.Now().UTC().Format(time.RFC3339)
			data["expires_at"] = time.Now().Add(time.Hour).UTC().Format(time.RFC3339)
		default:
			t.Error(r.URL.Path)
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	receiptPath := filepath.Join(t.TempDir(), "approved.json")
	code, result := invoke(t, []string{"package", "plan", localPackageFixture(t), "--bind", packageBindingShortcut, "--save-plan", receiptPath, "--api-url", server.URL, "--project", "project"}, "")
	if code != 0 || uploads.Load() != 1 {
		t.Fatal(code, result, uploads.Load())
	}
	receipt, err := packageapi.LoadPlanReceipt(receiptPath)
	if err != nil || receipt.Plan.APIOrigin != server.URL {
		t.Fatal(receipt, err)
	}
	info, err := os.Stat(receiptPath)
	if err != nil || runtime.GOOS != "windows" && info.Mode().Perm() != 0600 {
		t.Fatal(info, err)
	}
	if err = receipt.Save(receiptPath); err == nil {
		t.Fatal("receipt overwrote approved destination")
	}
}

func TestPackagePublicPlanDoesNotExposeProtectedAliases(t *testing.T) {
	plan := map[string]any{"bindings": map[string]any{"spec": map[string]any{"credentials": map[string]any{"primary": map[string]any{"protected_ref": "private-store-reference"}}}}, "artifact_digest": "public-artifact"}
	result := packagePublic(plan)
	encoded, _ := json.Marshal(result)
	if strings.Contains(string(encoded), "private-store-reference") || !strings.Contains(string(encoded), "public-artifact") {
		t.Fatal("unsafe public plan")
	}
	original, _ := json.Marshal(plan)
	if !strings.Contains(string(original), "private-store-reference") {
		t.Fatal("changed private approved bindings")
	}
}
