package devworkspace

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"
)

func editAuthor(t *testing.T, c *Config, g *Graph, key string, edit func(map[string]any)) *Graph {
	t.Helper()
	node := g.Nodes[key]
	document := clone(node.Document)
	edit(document)
	raw, err := Encode(document)
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(filepath.Join(c.RootPath(), node.Descriptor), raw, 0600); err != nil {
		t.Fatal(err)
	}
	next, err := LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	return next
}

func TestRebaseMergesIndependentEditsAndKeepsOldRevisions(t *testing.T) {
	c, g := completeGraph(t)
	r := g.Nodes["support"].Resource
	state := authorState()
	base, err := g.CreateRevision(r, state, "base", nil)
	if err != nil {
		t.Fatal(err)
	}
	g = editAuthor(t, c, g, r.Key, func(doc map[string]any) { doc["metadata"].(map[string]any)["description"] = "local description" })
	local, err := g.CreateRevision(r, state, "local", nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = g.CheckoutRevision(r, base); err != nil {
		t.Fatal(err)
	}
	g, err = LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	g = editAuthor(t, c, g, r.Key, func(doc map[string]any) { doc["metadata"].(map[string]any)["name"] = "Remote support name" })
	remote, err := g.CreateRevision(r, state, "remote", nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = g.CheckoutRevision(r, local); err != nil {
		t.Fatal(err)
	}
	g, err = LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	result, err := g.RebaseRevision(r, remote.ID, "", "resolve independent branches")
	if err != nil {
		t.Fatal(err)
	}
	revision := result["revision"].(*Revision)
	if revision.ID == local.ID || !reflect.DeepEqual(revision.Parents, []string{remote.ID}) || result["remote_changed"] != false {
		t.Fatal(result)
	}
	g, err = LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	metadata := g.Nodes[r.Key].Document["metadata"].(map[string]any)
	if metadata["name"] != "Remote support name" || metadata["description"] != "local description" {
		t.Fatal(metadata)
	}
	preserved, err := c.ReadRevision(r, local.ID)
	if err != nil || preserved.RecordDigest != local.RecordDigest {
		t.Fatal("old revision rewritten", err)
	}
	if _, err = g.CheckoutRevision(r, base); err != nil {
		t.Fatal("rebased author object cannot restore its base", err)
	}
}

func TestRebaseConflictDoesNotModifyFilesOrHistory(t *testing.T) {
	c, g := completeGraph(t)
	r := g.Nodes["support"].Resource
	state := authorState()
	base, err := g.CreateRevision(r, state, "base", nil)
	if err != nil {
		t.Fatal(err)
	}
	g = editAuthor(t, c, g, r.Key, func(doc map[string]any) { doc["metadata"].(map[string]any)["name"] = "Local name" })
	local, err := g.CreateRevision(r, state, "local", nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = g.CheckoutRevision(r, base); err != nil {
		t.Fatal(err)
	}
	g, err = LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	g = editAuthor(t, c, g, r.Key, func(doc map[string]any) { doc["metadata"].(map[string]any)["name"] = "Remote name" })
	remote, err := g.CreateRevision(r, state, "remote", nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = g.CheckoutRevision(r, local); err != nil {
		t.Fatal(err)
	}
	g, err = LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	file := filepath.Join(c.RootPath(), g.Nodes[r.Key].Descriptor)
	before, _ := os.ReadFile(file)
	result, err := g.RebaseRevision(r, remote.ID, "", "conflict")
	if err == nil || !strings.Contains(err.Error(), "ASAC_REBASE_CONFLICT") || len(result["conflicts"].([]Conflict)) != 1 {
		t.Fatal(result, err)
	}
	after, _ := os.ReadFile(file)
	records, readErr := c.Revisions(r)
	if string(before) != string(after) || readErr != nil || len(records) != 3 {
		t.Fatal("conflict changed files or history", readErr)
	}
}

func TestRebaseFormattingPreservesSurvivingCommentsAndJSON(t *testing.T) {
	raw, err := EncodeWithComments(map[string]any{"metadata": map[string]any{"name": "changed", "description": "new"}}, "agent.yaml", "# root note\nmetadata:\n  # name note\n  name: original\n")
	if err != nil || !strings.Contains(string(raw), "# root note") || !strings.Contains(string(raw), "# name note") {
		t.Fatal(string(raw), err)
	}
	raw, err = EncodeWithComments(map[string]any{"metadata": map[string]any{"name": "changed"}}, "agent.json", `{"metadata":{"name":"old"}}`)
	if err != nil || !strings.HasPrefix(string(raw), "{") {
		t.Fatal(string(raw), err)
	}
}

func TestRebaseCarriesCommentOnlyRemoteEditAndRejectsCompetingNotes(t *testing.T) {
	c, g := completeGraph(t)
	r := g.Nodes["support"].Resource
	state := authorState()
	base, err := g.CreateRevision(r, state, "base", nil)
	if err != nil {
		t.Fatal(err)
	}
	file := filepath.Join(c.RootPath(), g.Nodes[r.Key].Descriptor)
	original, _ := os.ReadFile(file)
	if err = os.WriteFile(file, append([]byte("# remote note\n"), original...), 0600); err != nil {
		t.Fatal(err)
	}
	g, err = LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	remote, err := g.CreateRevision(r, state, "remote note", nil)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = g.CheckoutRevision(r, base); err != nil {
		t.Fatal(err)
	}
	g, err = LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = g.RebaseRevision(r, remote.ID, "", ""); err != nil {
		t.Fatal(err)
	}
	got, _ := os.ReadFile(file)
	if !strings.Contains(string(got), "# remote note") {
		t.Fatal("comment-only remote edit lost")
	}
	if _, err = g.CheckoutRevision(r, base); err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(file, append([]byte("# local note\n"), original...), 0600); err != nil {
		t.Fatal(err)
	}
	g, err = LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = g.CreateRevision(r, state, "local note", nil); err != nil {
		t.Fatal(err)
	}
	result, err := g.RebaseRevision(r, remote.ID, "", "")
	if err == nil || len(result["conflicts"].([]Conflict)) != 1 || !strings.Contains(result["conflicts"].([]Conflict)[0].Path, "author_comments") {
		t.Fatal("competing notes silently replaced", result, err)
	}
}
