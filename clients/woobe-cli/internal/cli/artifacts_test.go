package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
)

func artifactCLIForTest(t *testing.T, apiURL string) (*App, *bytes.Buffer, string) {
	t.Helper()
	root := t.TempDir()
	configPath := filepath.Join(root, "woobe", "config.json")
	app := New(bytes.NewBuffer(nil), &bytes.Buffer{}, &bytes.Buffer{})
	app.ConfigPath = configPath
	if err := config.Save(configPath, config.Config{Version: 1, Current: "test", Contexts: map[string]config.Context{
		"test": {APIURL: apiURL, Project: "project-1", RuntimeCredential: "runtime-ref"},
	}}); err != nil {
		t.Fatal(err)
	}
	if err := app.store().Put("runtime-ref", "runtime-key-do-not-print"); err != nil {
		t.Fatal(err)
	}
	output := &bytes.Buffer{}
	app.Out = output
	app.Root.SetOut(output)
	return app, output, configPath
}

func runArtifactCLI(app *App, args ...string) int {
	args = append(args, "--context", "test", "--output", "json")
	return app.Execute(context.Background(), args)
}

func TestArtifactCommandsAreDiscoveredWithRuntimeRoutesAndPagination(t *testing.T) {
	app, output, _ := artifactCLIForTest(t, "https://example.invalid")
	code := app.Execute(context.Background(), []string{"help", "--output", "json"})
	if code != 0 {
		t.Fatalf("discovery code=%d output=%s", code, output)
	}
	var envelope struct {
		Data []map[string]any `json:"data"`
	}
	if err := json.Unmarshal(output.Bytes(), &envelope); err != nil {
		t.Fatalf("decode discovery: %v (%s)", err, output)
	}
	byCommand := map[string]map[string]any{}
	for _, operation := range envelope.Data {
		command, _ := operation["command"].(string)
		byCommand[command] = operation
	}
	for command, expectedPath := range map[string]string{
		"artifacts workspace list": "/v1/artifact-workspaces",
		"artifacts upload":         "/v1/artifact-workspaces/{workspace_id}/uploads",
		"artifacts read-source":    "/v1/artifact-sources/read",
		"artifacts download":       "/v1/artifacts/{artifact_id}/revisions/{revision_id}/content",
	} {
		operation := byCommand[command]
		if operation == nil || operation["kind"] != "runtime-artifact" || operation["path"] != expectedPath || operation["availability"] != "server-dependent" || operation["permission_source"] != "runtime_key_grants" {
			t.Errorf("discovery for %q = %#v", command, operation)
		}
	}
	if byCommand["artifacts workspace list"]["pagination"] != "cursor-has-next" {
		t.Errorf("workspace pagination contract = %#v", byCommand["artifacts workspace list"]["pagination"])
	}
	if byCommand["artifacts upload resume"]["kind"] != "runtime-artifact-workflow" {
		t.Errorf("upload resume was not discovered as a reconciliation workflow: %#v", byCommand["artifacts upload resume"])
	}
}

func TestArtifactsWorkspaceListUsesOnlyAttachedRuntimeCredentialAndExplicitScope(t *testing.T) {
	var calls atomic.Int64
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		if r.Method != http.MethodGet || r.URL.Path != "/v1/artifact-workspaces" {
			t.Errorf("request = %s %s", r.Method, r.URL.Path)
		}
		if r.Header.Get("Authorization") != "Bearer runtime-key-do-not-print" || r.URL.Query().Get("project_id") != "project-1" || r.URL.Query().Get("environment") != "staging" {
			t.Errorf("scope or credential is incorrect: %s", r.URL.Redacted())
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = io.WriteString(w, `{"schema_version":"1","items":[{"id":"workspace-1","name":"Docs"}],"has_more":false,"next_cursor":"","truncated":false}`)
	}))
	defer server.Close()
	app, output, _ := artifactCLIForTest(t, server.URL)
	code := runArtifactCLI(app, "artifacts", "workspace", "list", "--api-url", server.URL, "--environment", "staging")
	if code != 0 || calls.Load() != 1 {
		t.Fatalf("code=%d calls=%d output=%s", code, calls.Load(), output)
	}
	if strings.Contains(output.String(), "runtime-key-do-not-print") || strings.Contains(output.String(), "Bearer") {
		t.Fatal("Runtime credential leaked in CLI output")
	}
	output.Reset()
	code = app.Execute(context.Background(), []string{"artifacts", "workspace", "list", "--api-url", server.URL, "--environment", "staging", "--output", "compact", "--fields", "id"})
	if code != 0 || calls.Load() != 2 {
		t.Fatalf("compact workspace list code=%d calls=%d output=%s", code, calls.Load(), output)
	}
	var compact struct {
		Data []map[string]any `json:"data"`
		Meta map[string]any   `json:"meta"`
	}
	if err := json.Unmarshal(output.Bytes(), &compact); err != nil || len(compact.Data) != 1 || compact.Data[0]["id"] != "workspace-1" || len(compact.Data[0]) != 1 || compact.Meta["next_cursor"] != "" {
		t.Fatalf("compact field projection = %#v; err=%v output=%s", compact, err, output)
	}
}

func TestArtifactDestructiveAndReplacementMutationsRequireConfirmationBeforeNetwork(t *testing.T) {
	var calls atomic.Int64
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		http.Error(w, "unexpected request", http.StatusInternalServerError)
	}))
	defer server.Close()
	app, output, _ := artifactCLIForTest(t, server.URL)
	code := runArtifactCLI(app, "artifacts", "move", "workspace-1", "artifact-1", "--api-url", server.URL, "--environment", "draft", "--path", "new/path.pdf", "--expected-version", "3", "--operation-id", "move-op")
	if code != 2 || calls.Load() != 0 {
		t.Fatalf("unconfirmed move code=%d requests=%d output=%s", code, calls.Load(), output)
	}
	inputPath := filepath.Join(t.TempDir(), "replacement.pdf")
	if err := os.WriteFile(inputPath, []byte("data"), 0600); err != nil {
		t.Fatal(err)
	}
	code = runArtifactCLI(app, "artifacts", "upload", "workspace-1", "--api-url", server.URL, "--environment", "draft", "--file", inputPath, "--path", "invoice.pdf", "--artifact-id", "artifact-1", "--expected-revision", "revision-3")
	if code != 2 || calls.Load() != 0 {
		t.Fatalf("unconfirmed replacement code=%d requests=%d output=%s", code, calls.Load(), output)
	}
}

func TestArtifactUploadCheckpointReconcilesLostPartAcknowledgement(t *testing.T) {
	var remoteOffset int64
	var partOffsets []string
	var beginCount, finalizeCount atomic.Int64
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer runtime-key-do-not-print" || r.URL.Query().Get("project_id") != "project-1" || r.URL.Query().Get("environment") != "staging" {
			t.Errorf("upload scope or key mismatch: %s", r.URL.Redacted())
		}
		w.Header().Set("Content-Type", "application/json")
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/v1/artifact-capabilities":
			_, _ = io.WriteString(w, `{"schema_version":"1","max_upload_bytes":100,"max_upload_part_bytes":2,"max_upload_parts":10}`)
		case r.Method == http.MethodPost && r.URL.Path == "/v1/artifact-workspaces/workspace-1/uploads":
			beginCount.Add(1)
			var request map[string]any
			if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
				t.Error(err)
			}
			if request["sha256"] != "3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7" || r.Header.Get("Idempotency-Key") == "" {
				t.Errorf("begin request = %#v", request)
			}
			_, _ = io.WriteString(w, `{"schema_version":"1","id":"upload-1","workspace_id":"workspace-1","operation_id":"artifact-op","expected_size":4,"status":"uploading","offset":0}`)
		case r.Method == http.MethodPut && strings.HasSuffix(r.URL.Path, "/parts"):
			offset := r.URL.Query().Get("offset")
			partOffsets = append(partOffsets, offset)
			body, _ := io.ReadAll(r.Body)
			if len(body) != 2 {
				t.Errorf("part body size=%d", len(body))
			}
			if offset == "0" {
				remoteOffset = 2 // The server accepted bytes, but its acknowledgement was lost.
				http.Error(w, "lost acknowledgement", http.StatusGatewayTimeout)
				return
			}
			remoteOffset += int64(len(body))
			_, _ = fmt.Fprintf(w, `{"schema_version":"1","id":"upload-1","workspace_id":"workspace-1","operation_id":"artifact-op","expected_size":4,"status":"uploading","offset":%d}`, remoteOffset)
		case r.Method == http.MethodGet && strings.HasSuffix(r.URL.Path, "/uploads/upload-1"):
			_, _ = fmt.Fprintf(w, `{"schema_version":"1","id":"upload-1","workspace_id":"workspace-1","operation_id":"artifact-op","expected_size":4,"status":"uploading","offset":%d}`, remoteOffset)
		case r.Method == http.MethodPost && strings.HasSuffix(r.URL.Path, "/finalize"):
			finalizeCount.Add(1)
			_, _ = io.WriteString(w, `{"schema_version":"1","id":"upload-1","workspace_id":"workspace-1","operation_id":"artifact-op","expected_size":4,"status":"completed","offset":4,"receipt":{"artifact_id":"artifact-1","revision_id":"revision-1"}}`)
		default:
			t.Errorf("unexpected request %s %s", r.Method, r.URL)
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	app, output, _ := artifactCLIForTest(t, server.URL)
	inputPath := filepath.Join(t.TempDir(), "資料 with spaces.bin")
	if err := os.WriteFile(inputPath, []byte("data"), 0600); err != nil {
		t.Fatal(err)
	}
	checkpoint := filepath.Join(t.TempDir(), "upload.json")
	code := runArtifactCLI(app, "artifacts", "upload", "workspace-1", "--api-url", server.URL, "--environment", "staging", "--file", inputPath, "--path", "folder with spaces/資料.bin", "--content-type", "application/octet-stream", "--operation-id", "artifact-op", "--checkpoint", checkpoint)
	if code != 8 || beginCount.Load() != 1 {
		t.Fatalf("initial upload code=%d calls=%d output=%s", code, beginCount.Load(), output)
	}
	info, err := os.Stat(checkpoint)
	if err != nil || info.Mode().Perm() != 0600 {
		t.Fatalf("checkpoint file=%v error=%v", info, err)
	}
	checkpointBytes, err := os.ReadFile(checkpoint)
	if err != nil || bytes.Contains(checkpointBytes, []byte("runtime-key-do-not-print")) {
		t.Fatal("private checkpoint contains credentials", err)
	}
	code = runArtifactCLI(app, "artifacts", "upload", "resume", "--api-url", server.URL, "--environment", "staging", "--checkpoint", checkpoint)
	if code != 0 || finalizeCount.Load() != 1 || remoteOffset != 4 {
		t.Fatalf("resume code=%d finalizations=%d offset=%d output=%s", code, finalizeCount.Load(), remoteOffset, output)
	}
	if strings.Join(partOffsets, ",") != "0,2" {
		t.Fatalf("part offsets = %v; uncertain part was replayed", partOffsets)
	}
	if strings.Contains(output.String(), "runtime-key-do-not-print") {
		t.Fatal("Runtime credential leaked")
	}
}

func TestArtifactUploadCheckpointReconcilesLostBeginAcknowledgement(t *testing.T) {
	var beginCount, finalizeCount atomic.Int64
	var operationHeaders []string
	var operationIDs []string
	var remoteOffset int64
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/v1/artifact-capabilities":
			_, _ = io.WriteString(w, `{"schema_version":"1","max_upload_bytes":100,"max_upload_part_bytes":8,"max_upload_parts":10}`)
		case r.Method == http.MethodPost && r.URL.Path == "/v1/artifact-workspaces/workspace-1/uploads":
			beginCount.Add(1)
			operationHeaders = append(operationHeaders, r.Header.Get("Idempotency-Key"))
			var request map[string]any
			if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
				t.Error(err)
			}
			operationID, _ := request["operation_id"].(string)
			operationIDs = append(operationIDs, operationID)
			if operationID == "" || r.Header.Get("Idempotency-Key") != operationID || request["path"] != "source.json" || request["artifact_id"] != "artifact-existing" || request["expected_revision"] != "revision-5" {
				t.Errorf("begin request = %#v", request)
			}
			if beginCount.Load() == 1 {
				// Model durable server acceptance followed by a lost HTTP response.
				w.WriteHeader(http.StatusGatewayTimeout)
				_, _ = io.WriteString(w, `{"message":"response lost"}`)
				return
			}
			_, _ = fmt.Fprintf(w, `{"schema_version":"1","id":"upload-begin","workspace_id":"workspace-1","operation_id":%q,"expected_size":4,"status":"uploading","offset":0}`, operationID)
		case r.Method == http.MethodGet && r.URL.Path == "/v1/artifact-workspaces/workspace-1/uploads/upload-begin":
			_, _ = fmt.Fprintf(w, `{"schema_version":"1","id":"upload-begin","workspace_id":"workspace-1","operation_id":%q,"expected_size":4,"status":"uploading","offset":%d}`, operationIDs[0], remoteOffset)
		case r.Method == http.MethodPut && strings.HasSuffix(r.URL.Path, "/parts"):
			if r.URL.Query().Get("offset") != "0" {
				t.Errorf("initial part offset=%s", r.URL.Query().Get("offset"))
			}
			body, _ := io.ReadAll(r.Body)
			remoteOffset += int64(len(body))
			_, _ = fmt.Fprintf(w, `{"schema_version":"1","id":"upload-begin","workspace_id":"workspace-1","operation_id":%q,"expected_size":4,"status":"uploading","offset":%d}`, operationIDs[0], remoteOffset)
		case r.Method == http.MethodPost && strings.HasSuffix(r.URL.Path, "/finalize"):
			finalizeCount.Add(1)
			_, _ = fmt.Fprintf(w, `{"schema_version":"1","id":"upload-begin","workspace_id":"workspace-1","operation_id":%q,"expected_size":4,"status":"completed","offset":4,"receipt":{"artifact_id":"artifact-1","revision_id":"revision-1"}}`, operationIDs[0])
		default:
			t.Errorf("unexpected request %s %s", r.Method, r.URL)
			http.NotFound(w, r)
		}
	}))
	defer server.Close()
	app, output, _ := artifactCLIForTest(t, server.URL)
	inputPath := filepath.Join(t.TempDir(), "upload body.bin")
	if err := os.WriteFile(inputPath, []byte("data"), 0600); err != nil {
		t.Fatal(err)
	}
	checkpoint := filepath.Join(t.TempDir(), "begin-checkpoint.json")
	code := runArtifactCLI(app, "artifacts", "upload", "workspace-1", "--api-url", server.URL, "--environment", "draft", "--yes", "--file", inputPath, "--path", "source.json", "--artifact-id", "artifact-existing", "--expected-revision", "revision-5", "--checkpoint", checkpoint)
	if code != 8 || beginCount.Load() != 1 {
		t.Fatalf("initial begin code=%d calls=%d output=%s", code, beginCount.Load(), output)
	}
	store, cp, err := loadArtifactUploadCheckpoint(checkpoint)
	if err != nil {
		t.Fatal(err)
	}
	_ = store.Close()
	if cp.State != "begin_unknown" || cp.UploadID != "" {
		t.Fatalf("checkpoint after lost begin = %#v", cp)
	}
	code = runArtifactCLI(app, "artifacts", "upload", "resume", "--api-url", server.URL, "--checkpoint", checkpoint)
	if code != 0 || beginCount.Load() != 2 || finalizeCount.Load() != 1 || remoteOffset != 4 {
		t.Fatalf("resume code=%d begin=%d finalize=%d offset=%d output=%s", code, beginCount.Load(), finalizeCount.Load(), remoteOffset, output)
	}
	if len(operationHeaders) != 2 || operationHeaders[0] == "" || operationHeaders[1] != operationHeaders[0] || len(operationIDs) != 2 || operationIDs[1] != operationIDs[0] || operationIDs[0] != operationHeaders[0] {
		t.Fatalf("resume did not reconcile the same idempotent begin operation: %v", operationHeaders)
	}
}

func TestArtifactReadSourceUsesStrictJSONSourceRefAndExplicitWorkspace(t *testing.T) {
	var calls atomic.Int64
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		if r.Method != http.MethodPost || r.URL.Path != "/v1/artifact-sources/read" || r.URL.Query().Get("artifact_workspace_id") != "workspace-1" || r.Header.Get("Authorization") != "Bearer runtime-key-do-not-print" {
			t.Errorf("source read scope = %s %s", r.Method, r.URL.Redacted())
		}
		var request map[string]any
		if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
			t.Error(err)
		}
		source, ok := request["source"].(map[string]any)
		if !ok || source["artifact_id"] != "artifact-1" || source["revision_id"] != "revision-1" || request["max_chars"] != float64(120) {
			t.Errorf("source-read request = %#v", request)
		}
		_, _ = io.WriteString(w, `{"schema_version":"1","source":{"artifact_id":"artifact-1","revision_id":"revision-1","source_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},"text":"cited text","offset":0,"next_offset":null,"truncated":false,"coverage":"exact","page_label":null}`)
	}))
	defer server.Close()
	app, output, _ := artifactCLIForTest(t, server.URL)
	sourcePath := filepath.Join(t.TempDir(), "source ref.json")
	if err := os.WriteFile(sourcePath, []byte(`{"artifact_id":"artifact-1","revision_id":"revision-1","source_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}`), 0600); err != nil {
		t.Fatal(err)
	}
	code := runArtifactCLI(app, "artifacts", "read-source", "workspace-1", "--source-file", sourcePath, "--max-chars", "120", "--environment", "staging")
	if code != 0 || calls.Load() != 1 || !strings.Contains(output.String(), "cited text") {
		t.Fatalf("read-source code=%d calls=%d output=%s", code, calls.Load(), output)
	}
	if err := os.WriteFile(sourcePath, []byte(`{"artifact_id":"artifact-1","revision_id":"revision-1","source_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","control_key":"secret"}`), 0600); err != nil {
		t.Fatal(err)
	}
	code = runArtifactCLI(app, "artifacts", "read-source", "workspace-1", "--source-file", sourcePath)
	if code == 0 || calls.Load() != 1 {
		t.Fatalf("strict SourceRef decoder accepted an unknown secret field: code=%d calls=%d", code, calls.Load())
	}
}

func TestArtifactDownloadPublishesOnlyIntegrityVerifiedRevision(t *testing.T) {
	var truncate atomic.Bool
	var createDestinationDuringDownload atomic.Bool
	var raceDestination string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer runtime-key-do-not-print" || r.URL.Query().Get("artifact_workspace_id") != "workspace-1" {
			t.Errorf("download scope/key missing: %s", r.URL.Redacted())
		}
		if strings.HasSuffix(r.URL.Path, "/content") {
			w.Header().Set("Content-Type", "application/pdf")
			if createDestinationDuringDownload.Load() {
				if err := os.WriteFile(raceDestination, []byte("concurrent file"), 0600); err != nil {
					t.Error(err)
				}
			}
			if truncate.Load() {
				w.Header().Set("Content-Length", "6")
				_, _ = io.WriteString(w, "bad")
				return
			}
			_, _ = io.WriteString(w, "good")
			return
		}
		_, _ = io.WriteString(w, `{"schema_version":"1","id":"revision-1","artifact_id":"artifact-1","content_type":"application/pdf","size_bytes":4,"sha256":"770e607624d689265ca6c44884d0807d9b054d23c473c106c72be9de08b7376c","origin":"upload"}`)
	}))
	defer server.Close()
	app, output, _ := artifactCLIForTest(t, server.URL)
	good := filepath.Join(t.TempDir(), "résultat final.pdf")
	code := runArtifactCLI(app, "artifacts", "download", "workspace-1", "artifact-1", "revision-1", "--api-url", server.URL, "--environment", "draft", "--output-file", good)
	if code != 0 {
		t.Fatalf("download code=%d output=%s", code, output)
	}
	data, err := os.ReadFile(good)
	if err != nil || string(data) != "good" {
		t.Fatalf("download bytes=%q err=%v", data, err)
	}
	truncate.Store(true)
	bad := filepath.Join(t.TempDir(), "incomplete.pdf")
	code = runArtifactCLI(app, "artifacts", "download", "workspace-1", "artifact-1", "revision-1", "--api-url", server.URL, "--environment", "draft", "--output-file", bad)
	if code == 0 {
		t.Fatalf("truncated download reported success: %s", output)
	}
	if _, err := os.Stat(bad); !os.IsNotExist(err) {
		t.Fatalf("incomplete final file exists (stat err=%v)", err)
	}
	raceDestination = filepath.Join(t.TempDir(), "concurrent destination.pdf")
	createDestinationDuringDownload.Store(true)
	code = runArtifactCLI(app, "artifacts", "download", "workspace-1", "artifact-1", "revision-1", "--api-url", server.URL, "--environment", "draft", "--output-file", raceDestination)
	if code == 0 {
		t.Fatal("download replaced a destination created during transfer without --yes")
	}
	data, err = os.ReadFile(raceDestination)
	if err != nil || string(data) != "concurrent file" {
		t.Fatalf("concurrent destination was changed: bytes=%q error=%v", data, err)
	}
}
