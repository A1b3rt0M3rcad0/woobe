package cli

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
)

func TestLocalDeployChecksOriginScopeAndMissingAncestryBeforeWrites(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	accepted := map[string]*devworkspace.Revision{}
	forge := false
	calls := 0
	var resource devworkspace.Resource
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if r.Method != "GET" {
			t.Error("preflight attempted mutation")
		}
		var data any
		if strings.HasSuffix(r.URL.Path, "/drafts/preflight") {
			data = map[string]any{"schema_version": "1.0", "kind": "Agent", "project_id": deployTestProject, "resource_id": deployTestTarget, "resource_uid": resource.UID, "source_export_id": r.URL.Query().Get("source_export_id"), "valid": true, "executed": false}
			if forge {
				data.(map[string]any)["resource_id"] = "another-target"
			}
		} else {
			record := accepted[strings.TrimPrefix(r.URL.Path, "/projects/project/agents/"+deployTestTarget+"/asac/revisions/")]
			if record == nil {
				w.WriteHeader(404)
				json.NewEncoder(w).Encode(map[string]any{"success": false, "data": map[string]any{"asac_schema_version": "1.0", "diagnostics": []any{map[string]any{"code": "ASAC_REVISION_UNAVAILABLE"}}}})
				return
			}
			copy := *record
			if forge {
				copy.Message = "Forged"
			}
			data = map[string]any{"record": copy, "complete": true}
		}
		json.NewEncoder(w).Encode(map[string]any{"success": true, "data": data})
	}))
	defer server.Close()
	c, state, resource := asacWorkspace(t, server.URL)
	graph, err := devworkspace.LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	chain := []*devworkspace.Revision{}
	for _, name := range []string{"accepted base", "orphan after failed open", "next attempt"} {
		record, err := graph.CreateRevision(resource, state, name, nil)
		if err != nil {
			t.Fatal(err)
		}
		chain = append(chain, record)
	}
	accepted[chain[0].ID] = chain[0]
	// A locally committed revision from this same intent must be reused after
	// a journal-save failure, while a new intent must retain it as an ancestor.
	own := chain[2]
	for _, retained := range []string{"", own.ID} {
		recovered, parents, err := localDeployRevision(c, &resource, own.ID, retained, own.Message, own.ArtifactDigest)
		if err != nil || recovered == nil || recovered.ID != own.ID || len(parents) != 1 || parents[0] != chain[1].ID {
			t.Fatalf("cannot recover original local commit: %v", err)
		}
	}
	recovered, parents, err := localDeployRevision(c, &resource, own.ID, "", "another intent", own.ArtifactDigest)
	if err != nil || recovered != nil || len(parents) != 1 || parents[0] != own.ID {
		t.Fatal("adopted another intent's revision")
	}
	if _, _, err := localDeployRevision(c, &resource, own.ID, own.ID, own.Message, "sha256:changed"); err == nil {
		t.Fatal("accepted changed retained artifact")
	}
	client, _ := controlplane.New(server.URL, "", time.Second)
	cmd := &cobra.Command{}
	cmd.SetContext(context.Background())
	workflow := deployWorkflow{client: client, cmd: cmd, base: "/projects/project/agents/" + deployTestTarget + "/asac", intent: &deployIntent{Kind: "Agent", Project: deployTestProject, Resource: deployTestTarget}}
	if err := workflow.checkLocalOrigin(&resource, deployTestIntent); err != nil {
		t.Fatal(err)
	}
	forge = true
	if err := workflow.checkLocalOrigin(&resource, deployTestIntent); err == nil {
		t.Fatal("accepted wrong target")
	}
	forge = false
	before, _ := c.ReadTracking(resource)
	err = workflow.checkLocalParents(c, &resource, []string{chain[2].ID})
	failure := output.Normalize(err)
	if err == nil || failure.DomainCode != "ASAC_HISTORY_INCOMPLETE" || failure.Outcome != "not_attempted" || !strings.Contains(failure.Message, chain[1].ID+", "+chain[2].ID) {
		t.Fatal(err)
	}
	after, _ := c.ReadTracking(resource)
	if before.Working != after.Working {
		t.Fatal("changed local head")
	}
	// Register exact originals, parents first, then the same preflight succeeds.
	accepted[chain[1].ID], accepted[chain[2].ID] = chain[1], chain[2]
	if err := workflow.checkLocalParents(c, &resource, []string{chain[2].ID}); err != nil {
		t.Fatal(err)
	}
	forge = true
	if err := workflow.checkLocalParents(c, &resource, []string{chain[2].ID}); err == nil {
		t.Fatal("accepted forged remote record")
	}
	if calls == 0 {
		t.Fatal("no authority checks")
	}
}
