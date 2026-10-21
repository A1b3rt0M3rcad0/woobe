package packageapi

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
)

func TestExportDownloadRequiresReceiptTransportAndCompleteInventory(t *testing.T) {
	root := t.TempDir()
	files := map[string]string{
		"woobe.yaml": `{"format":"woobe-package","schema_version":"1.0","kind":"Package","metadata":{"name":"test","version":"1"},"spec":{"entrypoint":{"kind":"Agent","ref":"agent"},"resources":["agent.yaml","model.yaml"],"requires":{"credentials":[{"ref":"primary","provider":"openai"}]}}}`,
		"agent.yaml": `{"format":"woobe-package","schema_version":"1.0","kind":"Agent","metadata":{"key":"agent","name":"test"},"spec":{"legacy_system_prompt":"Help","model":{"primary":{"ref":"model"}}}}`,
		"model.yaml": `{"format":"woobe-package","schema_version":"1.0","kind":"Model","metadata":{"key":"model","name":"test"},"spec":{"provider":"openai","model":"test","credential":{"ref":"primary"}}}`,
	}
	for path, content := range files {
		if err := os.WriteFile(filepath.Join(root, path), []byte(content), 0600); err != nil {
			t.Fatal(err)
		}
	}
	bundle, err := packagebundle.Load(root, false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	var archive bytes.Buffer
	if err = bundle.Archive(&archive, true); err != nil {
		t.Fatal(err)
	}
	hash := sha256.Sum256(archive.Bytes())
	digest := hex.EncodeToString(hash[:])
	receipt := ExportReceipt{PackageSchemaVersion: "1.0", ExportID: "export-1", ProjectID: evidenceProjectUUID, ArtifactDigest: bundle.ArtifactDigest, TransportDigest: digest, SizeBytes: int64(archive.Len()), Inventory: bundle.Inventory, ClosureComplete: true, SelfContained: true, Knowledge: "portable", ExpiresAt: time.Now().Add(time.Hour).Format(time.RFC3339)}
	for _, mode := range []string{"valid", "uppercase-project", "tamper", "inventory", "incomplete"} {
		t.Run(mode, func(t *testing.T) {
			server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				if r.URL.Path != "/projects/"+receipt.ProjectID+"/packages/exports/export-1/artifact" || r.Header.Get("Authorization") != "Bearer private-test-control-key" {
					t.Error("download scope or authentication differs")
				}
				w.Header().Set("Content-Length", fmt.Sprint(receipt.SizeBytes))
				w.Header().Set("X-Woobe-Transport-Sha256", digest)
				w.Header().Set("X-Woobe-Artifact-Digest", bundle.ArtifactDigest)
				body := append([]byte(nil), archive.Bytes()...)
				if mode == "tamper" {
					body[0] ^= 1
				}
				_, _ = w.Write(body)
			}))
			defer server.Close()
			control, _ := controlplane.New(server.URL, "private-test-control-key", time.Second)
			projectInput := receipt.ProjectID
			if mode == "uppercase-project" {
				projectInput = strings.ToUpper(projectInput)
			}
			client, _ := New(control, projectInput)
			candidate := receipt
			if mode == "inventory" {
				candidate.Inventory = nil
			}
			if mode == "incomplete" {
				candidate.ClosureComplete = false
			}
			result, err := client.Download(context.Background(), candidate)
			if mode != "valid" && mode != "uppercase-project" {
				if result != nil {
					result.Close()
					t.Fatal("unverified bytes accepted")
				}
				if err == nil {
					t.Fatal("expected integrity or closure error")
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			result.Close()
		})
	}
}
