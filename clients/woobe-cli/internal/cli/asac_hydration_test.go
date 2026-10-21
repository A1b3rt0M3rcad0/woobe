package cli

import (
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func TestRetainedHydrationVerifiesBytesAndPreservesWorkingFiles(t *testing.T) {
	for _, mode := range []string{"valid", "dry-run", "tamper", "wrong-record", "unsupported", "source-valid", "source-dry", "source-tamper", "source-wrong-record"} {
		t.Run(mode, func(t *testing.T) {
			root, _ := filepath.Abs("../..")
			t.Setenv("WOOBE_TEST_REPOSITORY", root)
			var receipt map[string]any
			var archive []byte
			var digest string
			var authorContent []byte
			var authorReceipt map[string]any
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.Method != "GET" {
					t.Error("hydration attempted write", r.Method)
				}
				if strings.HasSuffix(r.URL.Path, "/capabilities") {
					_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"package_schema_version": "1.0", "schema_catalog_sha256": packagefmt.CatalogDigest(), "supported_operations": []string{"registry"}, "asac": map[string]any{"retained_object_hydration": mode != "unsupported", "author_source_retention": strings.HasPrefix(mode, "source-")}}})
					return
				}
				if strings.Contains(r.URL.Path, "/author") {
					if strings.HasSuffix(r.URL.Path, "/receipt") {
						value := map[string]any{}
						for k, v := range authorReceipt {
							value[k] = v
						}
						if mode == "source-wrong-record" {
							value["record_digest"] = "sha256:" + strings.Repeat("f", 64)
						}
						_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": value})
						return
					}
					w.Header().Set("Content-Length", fmt.Sprint(len(authorContent)))
					w.Header().Set("X-Woobe-Transport-Sha256", authorReceipt["transport_digest"].(string))
					w.Header().Set("X-Woobe-Author-Digest", authorReceipt["author_digest"].(string))
					w.Header().Set("X-Woobe-Record-Digest", authorReceipt["record_digest"].(string))
					content := append([]byte(nil), authorContent...)
					if mode == "source-tamper" {
						content[0] ^= 1
					}
					_, _ = w.Write(content)
					return
				}
				if strings.HasSuffix(r.URL.Path, "/receipt") {
					value := map[string]any{}
					for k, v := range receipt {
						value[k] = v
					}
					if mode == "wrong-record" {
						value["record_digest"] = "sha256:" + strings.Repeat("f", 64)
					}
					_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": value})
					return
				}
				w.Header().Set("Content-Length", fmt.Sprint(len(archive)))
				w.Header().Set("X-Woobe-Transport-Sha256", digest)
				w.Header().Set("X-Woobe-Artifact-Digest", strings.TrimPrefix(receipt["artifact_digest"].(string), "sha256:"))
				w.Header().Set("X-Woobe-Record-Digest", receipt["record_digest"].(string))
				content := append([]byte(nil), archive...)
				if mode == "tamper" {
					content[0] ^= 1
				}
				_, _ = w.Write(content)
			}))
			defer server.Close()
			c, state, resource := asacWorkspace(t, server.URL)
			graph, err := devworkspace.LoadGraph(c)
			if err != nil {
				t.Fatal(err)
			}
			record, err := graph.CreateRevision(resource, state, "Exact hydration", nil)
			if err != nil {
				t.Fatal(err)
			}
			bundle, _, err := graph.Compile(resource.Key, state.Requirements, state.Credentials)
			if err != nil {
				t.Fatal(err)
			}
			defer bundle.Close()
			var encoded bytes.Buffer
			if err := bundle.Archive(&encoded, true); err != nil {
				t.Fatal(err)
			}
			archive = encoded.Bytes()
			hash := sha256.Sum256(archive)
			digest = hex.EncodeToString(hash[:])
			receipt = map[string]any{"package_schema_version": "1.0", "schema_version": "1.0", "kind": resource.Kind, "project_id": "project", "resource_id": "01a0a033-5820-770c-854b-902864857273", "resource_uid": resource.UID, "revision_id": record.ID, "record_digest": record.RecordDigest, "artifact_digest": record.ArtifactDigest, "definition_digest": record.DefinitionDigest, "transport_digest": digest, "size_bytes": len(archive), "inventory": bundle.Inventory, "author_artifact_status": "declared_not_retained", "complete": true}
			sourcePath := filepath.Join(c.RootPath(), "objects", "author", strings.TrimPrefix(record.AuthorDigest, "sha256:")+".json")
			if strings.HasPrefix(mode, "source-") {
				raw, err := os.ReadFile(sourcePath)
				if err != nil {
					t.Fatal(err)
				}
				var compressed bytes.Buffer
				stream := gzip.NewWriter(&compressed)
				_, _ = stream.Write(raw)
				_ = stream.Close()
				authorContent = compressed.Bytes()
				authorHash := sha256.Sum256(authorContent)
				authorReceipt = map[string]any{"package_schema_version": "1.0", "schema_version": "1.0", "project_id": "project", "kind": resource.Kind, "resource_id": receipt["resource_id"], "resource_uid": resource.UID, "revision_id": record.ID, "record_digest": record.RecordDigest, "author_digest": record.AuthorDigest, "transport_digest": hex.EncodeToString(authorHash[:]), "size_bytes": len(authorContent), "verification": "canonical_source_custody", "complete": true}
				receipt["author_artifact_status"] = "retained_custody"
				if err := os.Remove(sourcePath); err != nil {
					t.Fatal(err)
				}
			}
			object := filepath.Join(c.RootPath(), "objects", "sha256", bundle.ArtifactDigest+".tar.gz")
			if err := os.Remove(object); err != nil {
				t.Fatal(err)
			}
			if err := os.RemoveAll(filepath.Join(c.RootPath(), ".state")); err != nil {
				t.Fatal(err)
			}
			author, _ := c.ResourcePath(resource)
			before, _ := os.ReadFile(author)
			args := []string{"agent", "@support", "revision", "hydrate", record.ID, "--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}
			if mode == "dry-run" || mode == "source-dry" {
				args = append(args, "--dry-run")
			}
			code, response := invoke(t, args, "")
			if mode == "valid" || mode == "dry-run" || mode == "source-valid" || mode == "source-dry" {
				if code != 0 || response["data"].(map[string]any)["executable_object"] != "verified" || response["data"].(map[string]any)["bindings_restored"] != false {
					t.Fatal(code, response)
				}
			} else if code != 9 {
				t.Fatal("accepted invalid hydration", code, response)
			}
			if strings.HasPrefix(mode, "source-") {
				_, readErr := os.Stat(sourcePath)
				if mode == "source-valid" {
					if readErr != nil || response["data"].(map[string]any)["author_object"] != "verified_source_and_compilation" {
						t.Fatal("verified source missing", readErr, response)
					}
				} else if !os.IsNotExist(readErr) {
					t.Fatal("dry or invalid source was published", readErr)
				}
			}
			after, _ := os.ReadFile(author)
			if string(after) != string(before) {
				t.Fatal("hydration changed source")
			}
			tracking, err := c.ReadTracking(resource)
			if err != nil || tracking.Working != record.ID {
				t.Fatal("hydration moved head", tracking, err)
			}
			_, err = os.Stat(object)
			if mode == "valid" || mode == "source-valid" {
				if err != nil {
					t.Fatal("verified object missing", err)
				}
				code, response = invoke(t, args, "")
				if code != 0 {
					t.Fatal("non-idempotent hydration", code, response)
				}
			} else if !os.IsNotExist(err) {
				t.Fatal("unverified/dry object published", err)
			}
		})
	}
}
