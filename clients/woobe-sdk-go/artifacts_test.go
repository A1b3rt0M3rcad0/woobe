package woobe

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
)

const artifactProjectID = "project-123"

func newArtifactsTestClient(t *testing.T, handler http.Handler) (*ArtifactsClient, *httptest.Server) {
	t.Helper()
	server := httptest.NewServer(handler)
	client, err := New(WithBaseURL(server.URL), WithHTTPClient(server.Client()))
	if err != nil {
		server.Close()
		t.Fatal(err)
	}
	artifacts, err := client.Artifacts(artifactProjectID, "runtime-secret", ArtifactStaging)
	if err != nil {
		server.Close()
		t.Fatal(err)
	}
	t.Cleanup(server.Close)
	return artifacts, server
}

func TestArtifactsClientRequiresExplicitRuntimeScope(t *testing.T) {
	client, err := New(WithBaseURL("http://example.invalid"))
	if err != nil {
		t.Fatal(err)
	}
	for _, tc := range []struct {
		projectID string
		key       string
		env       ArtifactEnvironment
	}{
		{"", "rk", ArtifactStaging},
		{artifactProjectID, "", ArtifactStaging},
		{artifactProjectID, "rk", "production-like"},
		{"not/a/project", "rk", ArtifactStaging},
	} {
		if _, err := client.Artifacts(tc.projectID, tc.key, tc.env); err == nil {
			t.Fatalf("Artifacts(%q, %q, %q) unexpectedly succeeded", tc.projectID, tc.key, tc.env)
		}
	}
}

func TestArtifactsRequestsCarryOnlyRuntimeKeyAndFixedProjectEnvironment(t *testing.T) {
	artifacts, _ := newArtifactsTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/artifact-workspaces/ws-1" {
			t.Errorf("path = %q", r.URL.Path)
		}
		if r.URL.Query().Get("project_id") != artifactProjectID || r.URL.Query().Get("environment") != "staging" {
			t.Errorf("scope query = %v", r.URL.Query())
		}
		if r.URL.Query().Has("runtimeKey") || strings.Contains(r.URL.RawQuery, "runtime-secret") {
			t.Errorf("credential leaked into query: %q", r.URL.RawQuery)
		}
		if got := r.Header.Get("Authorization"); got != "Bearer runtime-secret" {
			t.Errorf("authorization = %q", got)
		}
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{"schema_version":"1","id":"ws-1","project_id":"project-123","environment":"staging","external_namespace":"team","external_key":"student-1","name":"Study","status":"active","storage_profile":"local","quota_bytes":10,"used_bytes":0,"reserved_bytes":0,"retention_days":30,"version":1,"catalog_version":0,"labels":{}}`)
	}))
	workspace, err := artifacts.GetWorkspace(context.Background(), "ws-1")
	if err != nil {
		t.Fatal(err)
	}
	if workspace.ID != "ws-1" || workspace.Environment != ArtifactStaging || workspace.ExternalKey != "student-1" {
		t.Fatalf("workspace = %#v", workspace)
	}
}

func TestArtifactsUploadStreamsBoundedPartsAndFinalizesOnce(t *testing.T) {
	data := []byte("abcdefgh")
	digest := sha256.Sum256(data)
	var offsets []int64
	var partBodies []string
	var finalizeCalls atomic.Int32
	artifacts, _ := newArtifactsTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("project_id") != artifactProjectID || r.URL.Query().Get("environment") != "staging" {
			t.Errorf("scope query = %v", r.URL.Query())
		}
		w.Header().Set("Content-Type", "application/json")
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/v1/artifact-capabilities":
			fmt.Fprint(w, `{"schema_version":"1","max_upload_bytes":100,"max_upload_part_bytes":3,"max_upload_parts":4}`)
		case r.Method == http.MethodPost && r.URL.Path == "/v1/artifact-workspaces/ws-1/uploads":
			if got := r.Header.Get("Idempotency-Key"); got != "operation-1" {
				t.Errorf("begin idempotency key = %q", got)
			}
			fmt.Fprint(w, `{"schema_version":"1","id":"upload-1","workspace_id":"ws-1","operation_id":"operation-1","expected_size":8,"offset":0,"status":"created","expires_at":"2026-10-20T00:00:00Z"}`)
		case r.Method == http.MethodPut && strings.HasSuffix(r.URL.Path, "/parts"):
			offset := int64(0)
			if _, err := fmt.Sscan(r.URL.Query().Get("offset"), &offset); err != nil {
				t.Errorf("offset: %v", err)
			}
			body, _ := io.ReadAll(r.Body)
			offsets = append(offsets, offset)
			partBodies = append(partBodies, string(body))
			if int64(len(body)) != r.ContentLength || int64(len(body)) > 3 {
				t.Errorf("part size = %d, Content-Length = %d", len(body), r.ContentLength)
			}
			if r.Header.Get("Idempotency-Key") != "" {
				t.Error("part unexpectedly has operation idempotency header")
			}
			fmt.Fprintf(w, `{"schema_version":"1","id":"upload-1","workspace_id":"ws-1","operation_id":"operation-1","expected_size":8,"offset":%d,"status":"uploading","expires_at":"2026-10-20T00:00:00Z"}`, offset+int64(len(body)))
		case r.Method == http.MethodPost && strings.HasSuffix(r.URL.Path, "/finalize"):
			finalizeCalls.Add(1)
			fmt.Fprint(w, `{"schema_version":"1","id":"upload-1","workspace_id":"ws-1","operation_id":"operation-1","expected_size":8,"offset":8,"status":"committed","expires_at":"2026-10-20T00:00:00Z","receipt":{"artifact_id":"artifact-1","revision_id":"revision-1"}}`)
		default:
			t.Errorf("unexpected request %s %s", r.Method, r.URL)
			http.NotFound(w, r)
		}
	}))

	result, err := artifacts.Upload(context.Background(), "ws-1", BeginArtifactUploadRequest{
		OperationID: "operation-1", Path: "notes/a.txt", SizeBytes: int64(len(data)),
		SHA256: hex.EncodeToString(digest[:]), ContentType: "text/plain",
	}, bytes.NewReader(data))
	if err != nil {
		t.Fatal(err)
	}
	if got := fmt.Sprint(offsets); got != "[0 3 6]" {
		t.Fatalf("part offsets = %s", got)
	}
	if got := fmt.Sprint(partBodies); got != "[abc def gh]" {
		t.Fatalf("part bodies = %s", got)
	}
	if finalizeCalls.Load() != 1 || result.Status != "committed" || result.Receipt == nil || result.Receipt.RevisionID != "revision-1" {
		t.Fatalf("finalized result = %#v, calls=%d", result, finalizeCalls.Load())
	}
}

func TestArtifactsUploadHashMismatchDoesNotFinalize(t *testing.T) {
	var finalized, aborted atomic.Int32
	artifacts, _ := newArtifactsTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case r.URL.Path == "/v1/artifact-capabilities":
			fmt.Fprint(w, `{"max_upload_bytes":100,"max_upload_part_bytes":8,"max_upload_parts":4}`)
		case strings.HasSuffix(r.URL.Path, "/uploads") && r.Method == http.MethodPost:
			fmt.Fprint(w, `{"id":"upload-1","expected_size":3,"offset":0,"status":"created"}`)
		case strings.HasSuffix(r.URL.Path, "/parts"):
			_, _ = io.Copy(io.Discard, r.Body)
			fmt.Fprint(w, `{"id":"upload-1","expected_size":3,"offset":3,"status":"uploading"}`)
		case strings.HasSuffix(r.URL.Path, "/finalize"):
			finalized.Add(1)
			t.Error("mismatched source was finalized")
		case r.Method == http.MethodDelete && strings.HasSuffix(r.URL.Path, "/uploads/upload-1"):
			aborted.Add(1)
			fmt.Fprint(w, `{"id":"upload-1","expected_size":3,"offset":3,"status":"aborted"}`)
		default:
			t.Errorf("unexpected request %s %s", r.Method, r.URL)
		}
	}))
	_, err := artifacts.Upload(context.Background(), "ws-1", BeginArtifactUploadRequest{
		OperationID: "operation-1", Path: "notes/a.txt", SizeBytes: 3,
		SHA256: strings.Repeat("0", 64), ContentType: "text/plain",
	}, strings.NewReader("abc"))
	if err == nil || finalized.Load() != 0 || aborted.Load() != 1 {
		t.Fatalf("error=%v finalized=%d aborted=%d", err, finalized.Load(), aborted.Load())
	}
}

func TestArtifactMutationDoesNotFollowRedirectOrRetry(t *testing.T) {
	var calls atomic.Int32
	artifacts, _ := newArtifactsTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		if got := r.Header.Get("Idempotency-Key"); got != "operation-1" {
			t.Errorf("idempotency key = %q", got)
		}
		http.Redirect(w, r, "https://elsewhere.invalid/collect", http.StatusTemporaryRedirect)
	}))
	_, err := artifacts.CreateText(context.Background(), "ws-1", "operation-1", "a.txt", "hello")
	requestErr, ok := err.(*RequestError)
	if !ok || requestErr.StatusCode != http.StatusTemporaryRedirect || calls.Load() != 1 {
		t.Fatalf("error=%#v calls=%d", err, calls.Load())
	}
}

func TestArtifactDownloadStreamsExactRevisionRange(t *testing.T) {
	artifacts, _ := newArtifactsTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/v1/artifacts/artifact-1/revisions/revision-1/content" || r.URL.Query().Get("artifact_workspace_id") != "ws-1" {
			t.Errorf("download request = %s?%s", r.URL.Path, r.URL.RawQuery)
		}
		if got := r.Header.Get("Range"); got != "bytes=2-4" {
			t.Errorf("range = %q", got)
		}
		w.Header().Set("Content-Type", "text/plain")
		w.Header().Set("Content-Range", "bytes 2-4/8")
		w.Header().Set("ETag", `"abc"`)
		w.Header().Set("X-Woobe-Source-Sha256", strings.Repeat("a", 64))
		w.WriteHeader(http.StatusPartialContent)
		_, _ = io.WriteString(w, "cde")
	}))
	downloader, err := artifacts.Download(context.Background(), "ws-1", "artifact-1", "revision-1", "bytes=2-4")
	if err != nil {
		t.Fatal(err)
	}
	defer downloader.Body.Close()
	body, err := io.ReadAll(downloader.Body)
	if err != nil {
		t.Fatal(err)
	}
	if string(body) != "cde" || downloader.StatusCode != http.StatusPartialContent || downloader.ContentRange != "bytes 2-4/8" || downloader.ETag != `"abc"` {
		t.Fatalf("download metadata/body = %#v, %q", downloader, body)
	}
}

func TestArtifactSearchSourceReadAndDocumentTreeKeepExactSources(t *testing.T) {
	const digest = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
	artifacts, _ := newArtifactsTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Query().Get("project_id") != artifactProjectID || r.URL.Query().Get("environment") != "staging" {
			t.Errorf("scope query = %v", r.URL.Query())
		}
		w.Header().Set("Content-Type", "application/json")
		switch {
		case r.Method == http.MethodGet && strings.HasSuffix(r.URL.Path, "/search"):
			if r.URL.Query().Get("query") != "retention" || r.URL.Query().Get("mode") != "literal" || r.URL.Query().Get("cursor") != "cursor-2" {
				t.Errorf("search query = %v", r.URL.Query())
			}
			fmt.Fprintf(w, `{"schema_version":"1","query":"retention","mode":"literal","catalog_version":7,"items":[{"artifact_id":"artifact-1","revision_id":"revision-2","path":"policy.pdf","kind":"file","match_location":"content","snippet":"Keep for one year","coverage":"complete","source":{"artifact_id":"artifact-1","revision_id":"revision-2","source_sha256":"%s","document_index_id":"index-1","node_id":"node-1","locator":{"page_index":2,"page_number":3}}}],"has_more":true,"next_cursor":"cursor-3"}`, digest)
		case r.Method == http.MethodPost && r.URL.Path == "/v1/artifact-sources/read":
			if r.URL.Query().Get("artifact_workspace_id") != "ws-1" {
				t.Errorf("source-read workspace = %v", r.URL.Query())
			}
			var request ArtifactSourceReadRequest
			if err := json.NewDecoder(r.Body).Decode(&request); err != nil {
				t.Errorf("decode source request: %v", err)
			}
			if request.Source.ArtifactID != "artifact-1" || request.Source.RevisionID != "revision-2" || request.Offset != 4 || request.MaxChars != 200 {
				t.Errorf("source request = %#v", request)
			}
			fmt.Fprintf(w, `{"schema_version":"1","source":{"artifact_id":"artifact-1","revision_id":"revision-2","source_sha256":"%s","document_index_id":"index-1","node_id":"node-1","locator":{"page_index":2,"page_number":3}},"text":"Keep for one year","offset":4,"next_offset":22,"truncated":false,"coverage":"complete","page_label":"iii"}`, digest)
		case r.Method == http.MethodGet && strings.HasSuffix(r.URL.Path, "/nodes"):
			if r.URL.Query().Get("artifact_workspace_id") != "ws-1" {
				t.Errorf("document-tree workspace = %v", r.URL.Query())
			}
			if r.URL.Query().Get("parent_id") != "node-1" || r.URL.Query().Get("limit") != "5" {
				t.Errorf("tree query = %v", r.URL.Query())
			}
			fmt.Fprintf(w, `{"schema_version":"1","items":[{"id":"node-2","document_index_id":"index-1","representation_set_id":"set-1","parent_id":"node-1","title":"Retention","kind":"section","ordinal":1,"depth":1,"children_count":0,"source_ranges":[[4,22]],"source":{"artifact_id":"artifact-1","revision_id":"revision-2","source_sha256":"%s","document_index_id":"index-1","node_id":"node-2"},"has_own_text":true,"inferred":false}],"has_more":false}`, digest)
		default:
			t.Errorf("unexpected request %s %s", r.Method, r.URL)
		}
	}))

	page, err := artifacts.Search(context.Background(), "ws-1", "retention", "literal", "cursor-2", 8)
	if err != nil {
		t.Fatal(err)
	}
	if len(page.Items) != 1 || page.Items[0].Source.RevisionID != "revision-2" || page.Items[0].Source.Locator.PageNumber == nil || *page.Items[0].Source.Locator.PageNumber != 3 {
		t.Fatalf("search page lost exact source identity: %#v", page)
	}
	read, err := artifacts.ReadSource(context.Background(), "ws-1", ArtifactSourceReadRequest{
		Source: page.Items[0].Source, Offset: 4, MaxChars: 200,
	})
	if err != nil {
		t.Fatal(err)
	}
	if read.Text != "Keep for one year" || read.NextOffset == nil || *read.NextOffset != 22 || read.PageLabel == nil || *read.PageLabel != "iii" {
		t.Fatalf("source read = %#v", read)
	}
	nodes, err := artifacts.ListDocumentNodes(context.Background(), "ws-1", "index-1", "node-1", "", 5)
	if err != nil {
		t.Fatal(err)
	}
	if len(nodes.Items) != 1 || nodes.Items[0].Title != "Retention" || nodes.Items[0].Source == nil || nodes.Items[0].Source.RevisionID != "revision-2" {
		t.Fatalf("document nodes = %#v", nodes)
	}
}

func TestArtifactProcessingUsesExactRevisionAndExplicitOperationIdentity(t *testing.T) {
	var calls atomic.Int32
	artifacts, _ := newArtifactsTestClient(t, http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		if r.URL.Query().Get("project_id") != artifactProjectID || r.URL.Query().Get("environment") != "staging" || r.URL.Query().Get("artifact_workspace_id") != "ws-1" {
			t.Errorf("scope query = %v", r.URL.Query())
		}
		w.Header().Set("Content-Type", "application/json")
		switch r.URL.Path {
		case "/v1/artifacts/artifact-1/processing":
			if r.Method != http.MethodPost || r.Header.Get("Idempotency-Key") != "process-1" {
				t.Errorf("processing request = %s, idempotency=%q", r.Method, r.Header.Get("Idempotency-Key"))
			}
			var input ArtifactProcessingRequest
			if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
				t.Errorf("decode processing request: %v", err)
			}
			if input.RevisionID != "revision-2" || input.OperationID != "process-1" {
				t.Errorf("processing request body = %#v", input)
			}
			fmt.Fprint(w, `{"schema_version":"1","id":"job-1","workspace_id":"ws-1","operation_id":"process-1","source":{"artifact_id":"artifact-1","revision_id":"revision-2"},"recipe_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","status":"queued","attempt":0,"completed_stages":[],"retryable":false}`)
		case "/v1/artifacts/artifact-1/processing/job-1":
			if r.Method != http.MethodGet {
				t.Errorf("status method = %s", r.Method)
			}
			fmt.Fprint(w, `{"schema_version":"1","id":"job-1","workspace_id":"ws-1","operation_id":"process-1","source":{"artifact_id":"artifact-1","revision_id":"revision-2"},"recipe_fingerprint":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","status":"succeeded","attempt":1,"completed_stages":["extract","index"],"result":{"mode":"extract_index","processing_performed":true,"source_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","coverage":"complete","document_index_id":"index-1","block_count":8,"page_count":2,"diagnostics":[]},"retryable":false}`)
		default:
			t.Errorf("unexpected request %s %s", r.Method, r.URL)
		}
	}))
	job, err := artifacts.RequestProcessing(context.Background(), "ws-1", "artifact-1", ArtifactProcessingRequest{
		OperationID: "process-1", RevisionID: "revision-2",
	})
	if err != nil {
		t.Fatal(err)
	}
	if job.ID != "job-1" || job.Source.RevisionID != "revision-2" {
		t.Fatalf("queued job = %#v", job)
	}
	status, err := artifacts.ProcessingJob(context.Background(), "ws-1", "artifact-1", job.ID)
	if err != nil {
		t.Fatal(err)
	}
	if status.Status != "succeeded" || status.Result == nil || status.Result.DocumentIndexID == nil || *status.Result.DocumentIndexID != "index-1" || calls.Load() != 2 {
		t.Fatalf("job status = %#v, calls=%d", status, calls.Load())
	}
}
