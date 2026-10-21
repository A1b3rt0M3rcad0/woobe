package cli

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/asac"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func asacWorkspace(t *testing.T, api string) (*devworkspace.Config, *devworkspace.State, devworkspace.Resource) {
	t.Helper()
	t.Chdir(t.TempDir())
	c, err := devworkspace.Create(".", ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	data, err := os.ReadFile(filepath.Join(repositoryFixtureRoot(t), "testdata/package/shared/complete.json"))
	if err != nil {
		t.Fatal(err)
	}
	var fixture struct {
		Files map[string]string `json:"files"`
	}
	if err = json.Unmarshal(data, &fixture); err != nil {
		t.Fatal(err)
	}
	for name, value := range fixture.Files {
		file := filepath.Join(c.RootPath(), filepath.FromSlash(name))
		if err = os.MkdirAll(filepath.Dir(file), 0700); err != nil {
			t.Fatal(err)
		}
		if err = os.WriteFile(file, []byte(value), 0600); err != nil {
			t.Fatal(err)
		}
	}
	bundle, err := packagebundle.Load(c.RootPath(), false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	state, err := c.ReadState(api, "workspace", "project")
	if err != nil {
		t.Fatal(err)
	}
	state.Requirements = packagefmt.Object(packagefmt.Object(bundle.Graph.Manifest["spec"])["requires"])
	var resource devworkspace.Resource
	for key, document := range bundle.Graph.Components {
		uid, _ := devworkspace.NewID()
		r := devworkspace.Resource{UID: uid, Kind: packagefmt.Text(document["kind"]), Key: key, Alias: key, Path: bundle.Graph.Paths[key]}
		c.Resources = append(c.Resources, r)
		state.Bindings[uid] = devworkspace.Binding{Base: document}
		if key == "support" {
			resource = r
			state.Bindings[uid] = devworkspace.Binding{Base: document, ResourceID: "01a0a033-5820-770c-854b-902864857273", SnapshotID: "old-release", Revision: 7}
		}
	}
	graph, err := devworkspace.LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	compiled, _, err := graph.Compile(resource.Key, state.Requirements, state.Credentials)
	if err != nil {
		t.Fatal(err)
	}
	bases, err := graph.AcceptedBases(compiled)
	compiled.Close()
	if err != nil {
		t.Fatal(err)
	}
	for uid, base := range bases {
		binding := state.Bindings[uid]
		binding.Supports = base.Supports
		state.Bindings[uid] = binding
	}
	if err = c.Save(); err != nil {
		t.Fatal(err)
	}
	if err = c.WriteState(state); err != nil {
		t.Fatal(err)
	}
	if err = c.BootstrapTracking(resource, state, "production"); err != nil {
		t.Fatal(err)
	}
	return c, state, resource
}

func TestASaCRevisionCommandsAreOfflineAndCloneSafe(t *testing.T) {
	root, err := filepath.Abs("../..")
	if err != nil {
		t.Fatal(err)
	}
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { requests++; t.Error("offline history contacted backend") }))
	defer server.Close()
	c, _, resource := asacWorkspace(t, server.URL)
	flags := []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}
	code, value := invoke(t, append([]string{"agent", "@support", "revision", "create", "--message", "checkpoint"}, flags...), "")
	if code != 0 {
		t.Fatal(value)
	}
	id := value["data"].(map[string]any)["revision_id"].(string)
	if err = os.RemoveAll(filepath.Join(c.RootPath(), ".state")); err != nil {
		t.Fatal(err)
	}
	for _, args := range [][]string{{"agent", "@support", "revision", "show", id}, {"agent", "@support", "checkout", "--revision", id}, {"develop", "agent", "checkout", "@support", "--revision", id}, {"agent", "@support", "history", "verify"}, {"agent", "@support", "heads"}, {"agent", "@support", "history"}, {"agent", "@support", "status"}, {"agent", "@support", "revision", "create", "--message", "fresh-clone"}} {
		code, value = invoke(t, append(args, flags...), "")
		if code != 0 {
			t.Fatal(args, value)
		}
		if args[2] == "status" && value["data"].(map[string]any)["changed"] != false {
			t.Fatal("fresh clone was incorrectly marked modified", value)
		}
	}
	if requests != 0 {
		t.Fatal("offline command made a request")
	}
	records, err := c.Revisions(resource)
	if err != nil || len(records) != 2 {
		t.Fatal(records, err)
	}
}

func repositoryFixtureRoot(t *testing.T) string {
	t.Helper()
	root := os.Getenv("WOOBE_TEST_REPOSITORY")
	if root == "" {
		t.Fatal("missing fixture repository root")
	}
	return root
}

func TestASaCRemoteStatusDetectsTrackedChange(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		if r.Method != "GET" {
			t.Fatal("status mutated backend")
		}
		env := r.URL.Query().Get("environment")
		_ = json.NewEncoder(w).Encode(map[string]any{"data": map[string]any{"schema_version": "1.0", "resource_id": "01a0a033-5820-770c-854b-902864857273", "environment": env, "snapshot_id": "new-release", "draft_generation": 8}})
	}))
	defer server.Close()
	asacWorkspace(t, server.URL)
	args := []string{"agent", "@support", "status", "--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}
	code, value := invoke(t, args, "")
	if code != 0 || requests != 0 || value["data"].(map[string]any)["remote_status"] != "unverified" {
		t.Fatal(value, requests)
	}
	code, value = invoke(t, append(args, "--remote"), "")
	if code != 0 || requests != 2 {
		t.Fatal(value, requests)
	}
	codes := value["data"].(map[string]any)["status_codes"].([]any)
	if len(codes) != 2 || codes[0] != "draft_changed" || codes[1] != "tracked_ref_changed" {
		t.Fatal(codes)
	}
}

func TestASaCHistoryFetchAppendsReceiptsWithoutEditingAuthor(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		stream := r.URL.Query().Get("stream")
		record := map[string]any{"format": "woobe-history-receipt", "schema_version": "1.0", "project_id": "project", "kind": "Agent", "resource_id": "01a0a033-5820-770c-854b-902864857273", "stream": stream, "id": "01a00d4a-fa75-7629-a2c6-773c25c6e2ef", "version": "v1"}
		record["record_digest"], _ = asac.Digest("history-receipt", record)
		_ = json.NewEncoder(w).Encode(map[string]any{"data": map[string]any{"schema_version": "1.0", "resource_id": record["resource_id"], "stream": stream, "records": []any{record}, "watermark": []any{"stable"}, "has_more": false, "complete": true}})
	}))
	defer server.Close()
	c, _, resource := asacWorkspace(t, server.URL)
	file, _ := c.ResourcePath(resource)
	before, _ := os.ReadFile(file)
	args := []string{"agent", "@support", "history", "fetch", "--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}
	for i := 0; i < 2; i++ {
		code, value := invoke(t, args, "")
		if code != 0 || value["data"].(map[string]any)["author_files_changed"] != false {
			t.Fatal(value)
		}
	}
	after, _ := os.ReadFile(file)
	if string(before) != string(after) || requests != 4 {
		t.Fatal("fetch modified author or made unexpected requests")
	}
}

func TestASaCRejectsAmbiguousArgumentsWithoutHTTP(t *testing.T) {
	for _, args := range [][]string{
		{"agent", "01a0a033-5820-770c-854b-902864857273", "current", "--remote=false"},
		{"agent", "@support", "heads", "ignored"},
		{"agent", "@support", "history", "--message", "ignored"},
		{"agent", "@support", "revision", "show", "rv_00000000-0000-0000-0000-000000000000", "--parent", "ignored"},
	} {
		code, value := invoke(t, args, "")
		if code != 2 {
			t.Fatal(args, code, value)
		}
	}
}

func TestASaCRebaseAndResolvedMergeAreOffline(t *testing.T) {
	root, _ := filepath.Abs("../..")
	t.Setenv("WOOBE_TEST_REPOSITORY", root)
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
		t.Error("local reconciliation contacted backend")
	}))
	defer server.Close()
	c, _, resource := asacWorkspace(t, server.URL)
	flags := []string{"--api-url", server.URL, "--workspace", "workspace", "--project", "project", "--output", "json"}
	run := func(args ...string) map[string]any {
		t.Helper()
		code, value := invoke(t, append(args, flags...), "")
		if code != 0 {
			t.Fatal(args, value)
		}
		return value["data"].(map[string]any)
	}
	create := func(message string) string {
		return run("agent", "@support", "revision", "create", "--message", message)["revision_id"].(string)
	}
	edit := func(field, value string) {
		t.Helper()
		graph, err := devworkspace.LoadGraph(c)
		if err != nil {
			t.Fatal(err)
		}
		node := graph.Nodes[resource.Key]
		node.Document["metadata"].(map[string]any)[field] = value
		raw, err := devworkspace.EncodeFile(node.Document, node.Descriptor)
		if err != nil {
			t.Fatal(err)
		}
		if err = os.WriteFile(filepath.Join(c.RootPath(), node.Descriptor), raw, 0600); err != nil {
			t.Fatal(err)
		}
	}
	base := create("base")
	edit("description", "local branch")
	local := create("local")
	run("agent", "@support", "checkout", "--revision", base)
	edit("name", "remote branch")
	onto := create("onto")
	run("agent", "@support", "checkout", "--revision", local)
	if err := os.RemoveAll(filepath.Join(c.RootPath(), ".state")); err != nil {
		t.Fatal(err)
	}
	rebased := run("agent", "@support", "rebase", "--onto", onto)
	revision := rebased["revision"].(map[string]any)
	newID := revision["revision_id"].(string)
	if rebased["rebased_from"] != local || rebased["remote_changed"] != false || revision["parents"].([]any)[0] != onto {
		t.Fatal(rebased)
	}
	merged := run("agent", "@support", "revision", "merge", local, newID, "--message", "Resolved content")
	parents := merged["parents"].([]any)
	if len(parents) != 2 || parents[0] != local || parents[1] != newID || requests != 0 {
		t.Fatal(merged, requests)
	}
}
