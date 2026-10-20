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
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func TestRevisionFetchChecksMetadataWithoutChangingAuthorsOrWorkingHead(t *testing.T) {
	for _, mode := range []string{"normal", "dry-run", "watermark-change", "forged-record"} {
		t.Run(mode, func(t *testing.T) {
			root, _ := filepath.Abs("../..")
			t.Setenv("WOOBE_TEST_REPOSITORY", root)
			var records []devworkspace.Revision
			var uid string
			pages := 0
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method != "GET" {
					t.Error("fetch attempted a remote write", r.Method)
				}
				var data any
				if strings.HasSuffix(r.URL.Path, "/capabilities") {
					data = map[string]any{"package_schema_version": "1.0", "schema_catalog_sha256": packagefmt.CatalogDigest(), "supported_operations": []string{"registry"}, "asac": map[string]any{"revision_catalog": true}}
				} else {
					pages++
					index := 0
					if r.URL.Query().Get("cursor") != "" {
						index = 1
					}
					watermark := "stable"
					if mode == "watermark-change" && index == 1 {
						watermark = "changed"
					}
					record := records[index]
					if mode == "forged-record" {
						record.Message = "forged"
					}
					data = map[string]any{"schema_version": "1.0", "kind": "Agent", "resource_id": "01a0a033-5820-770c-854b-902864857273", "stream": "revisions", "coverage": "authorized_resource_metadata", "watermark": []string{watermark}, "records": []any{map[string]any{"record": record, "author_artifact_status": "declared_not_retained"}}, "has_more": index == 0, "complete": index != 0, "next_cursor": "page-two"}
				}
				_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
			}))
			defer server.Close()
			c, state, resource := asacWorkspace(t, server.URL)
			uid = resource.UID
			graph, err := devworkspace.LoadGraph(c)
			if err != nil {
				t.Fatal(err)
			}
			base, err := graph.CreateRevision(resource, state, "local base", nil)
			if err != nil {
				t.Fatal(err)
			}
			if err := c.StoreRemoteRevision(resource, *base); err != nil {
				t.Fatal("same existing revision was not idempotent", err)
			}
			parent := base.ID
			for i := 0; i < 2; i++ {
				id, _ := devworkspace.NewID()
				record := *base
				record.ID, record.UID, record.Message, record.Parents = "rv_"+id, uid, "Remote metadata", []string{parent}
				record.ArtifactDigest = "sha256:" + strings.Repeat("a", 64)
				record.RecordDigest = ""
				record.RecordDigest, err = asac.Digest("record", record)
				if err != nil {
					t.Fatal(err)
				}
				records = append(records, record)
				parent = record.ID
			}
			author, _ := c.ResourcePath(resource)
			before, _ := os.ReadFile(author)
			// Origin is durable; fetching metadata works without private bindings.
			if err := os.RemoveAll(filepath.Join(c.RootPath(), ".state")); err != nil {
				t.Fatal(err)
			}
			args := []string{"agent", "@support", "history", "fetch", "--revisions", "--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}
			if mode == "dry-run" {
				args = append(args, "--dry-run")
			}
			code, value := invoke(t, args, "")
			if mode == "normal" || mode == "dry-run" {
				if code != 0 || pages != 2 || value["data"].(map[string]any)["metadata_complete"] != true || value["data"].(map[string]any)["objects_available"] != "not_downloaded" {
					t.Fatal(code, value, pages)
				}
			} else if code != 9 {
				t.Fatal("accepted inconsistent metadata", code, value)
			}
			after, _ := os.ReadFile(author)
			if string(after) != string(before) {
				t.Fatal("fetch changed source")
			}
			tracking, err := c.ReadTracking(resource)
			if err != nil || tracking.Working != base.ID {
				t.Fatal("fetch moved working head", tracking, err)
			}
			_, err = c.ReadRevision(resource, records[0].ID)
			if mode == "normal" && err != nil {
				t.Fatal("remote record not retained", err)
			}
			if (mode == "dry-run" || mode == "forged-record") && err == nil {
				t.Fatal("unexpected metadata write")
			}
			if _, err := os.Stat(filepath.Join(c.RootPath(), "objects", "sha256", strings.Repeat("a", 64)+".tar.gz")); !os.IsNotExist(err) {
				t.Fatal("metadata fetch invented object availability", err)
			}
		})
	}
}
