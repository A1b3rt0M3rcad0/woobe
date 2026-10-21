package devworkspace

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func authorState() *State {
	return &State{Requirements: map[string]any{"credentials": []any{map[string]any{"ref": "primary", "provider": "custom"}}, "project_environment": []any{map[string]any{"key": "PACKAGE_TEST_TOKEN", "kind": "secret"}}, "secrets": []any{map[string]any{"ref": "package-tool-token"}}}, Bindings: map[string]Binding{}}
}

func TestCheckoutRestoresAuthorBytesWithoutChangingOrigin(t *testing.T) {
	c, g := completeGraph(t)
	r := g.Nodes["support"].Resource
	state := authorState()
	file := filepath.Join(c.RootPath(), g.Nodes[r.Key].Descriptor)
	original, err := os.ReadFile(file)
	if err != nil {
		t.Fatal(err)
	}
	original = append([]byte("# preserved author comment\n"), original...)
	if err = os.WriteFile(file, original, 0600); err != nil {
		t.Fatal(err)
	}
	g, err = LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	first, err := g.CreateRevision(r, state, "before", nil)
	if err != nil {
		t.Fatal(err)
	}
	changed := append([]byte("# second comment\n"), original...)
	if err = os.WriteFile(file, changed, 0600); err != nil {
		t.Fatal(err)
	}
	g, err = LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	second, err := g.CreateRevision(r, state, "after", nil)
	if err != nil {
		t.Fatal(err)
	}
	if first.AuthorDigest == second.AuthorDigest || first.DefinitionDigest != second.DefinitionDigest {
		t.Fatal("source comments and executable identities conflated")
	}
	before, err := c.ReadTracking(r)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = g.CheckoutRevision(r, first); err != nil {
		t.Fatal(err)
	}
	got, _ := os.ReadFile(file)
	if string(got) != string(original) {
		t.Fatal("author bytes not restored")
	}
	after, err := c.ReadTracking(r)
	if err != nil || after.Origin != before.Origin || after.Working != first.ID {
		t.Fatal(after, err)
	}
	// Even comment-only edits are protected, without a force bypass.
	if err = os.WriteFile(file, append(got, []byte("\n# uncheckpointed\n")...), 0600); err != nil {
		t.Fatal(err)
	}
	g, err = LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = g.CheckoutRevision(r, second); err == nil || !strings.Contains(err.Error(), "local author edits") {
		t.Fatal("uncheckpointed edits accepted", err)
	}
}

func TestCheckoutRejectsTamperedSourceBeforeWriting(t *testing.T) {
	c, g := completeGraph(t)
	r := g.Nodes["support"].Resource
	record, err := g.CreateRevision(r, authorState(), "before", nil)
	if err != nil {
		t.Fatal(err)
	}
	file := filepath.Join(c.RootPath(), "objects", "author", strings.TrimPrefix(record.AuthorDigest, "sha256:")+".json")
	if err = os.WriteFile(file, []byte(`{}`), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = g.CheckoutRevision(r, record); err == nil {
		t.Fatal("tampered author object accepted")
	}
}

func TestNetworkCheckoutRestoresEntireClosedAuthorGraph(t *testing.T) {
	c, g := completeGraph(t)
	r := g.Nodes["support-network"].Resource
	state := authorState()
	first, err := g.CreateRevision(r, state, "network original", nil)
	if err != nil {
		t.Fatal(err)
	}
	node := g.Nodes["support"]
	file := filepath.Join(c.RootPath(), node.Descriptor)
	original, err := os.ReadFile(file)
	if err != nil {
		t.Fatal(err)
	}
	changed := append([]byte("# network dependency edit\n"), original...)
	if err = os.WriteFile(file, changed, 0600); err != nil {
		t.Fatal(err)
	}
	g, err = LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = g.CreateRevision(r, state, "network dependency", nil); err != nil {
		t.Fatal(err)
	}
	if _, err = g.CheckoutRevision(r, first); err != nil {
		t.Fatal(err)
	}
	got, _ := os.ReadFile(file)
	if string(got) != string(original) {
		t.Fatal("Network dependency source not restored")
	}
}

func TestHistoryDistinguishesMissingAuthorFromMissingExecutable(t *testing.T) {
	c, g := completeGraph(t)
	r := g.Nodes["support"].Resource
	record, err := g.CreateRevision(r, authorState(), "source", nil)
	if err != nil {
		t.Fatal(err)
	}
	file := filepath.Join(c.RootPath(), "objects", "author", strings.TrimPrefix(record.AuthorDigest, "sha256:")+".json")
	if err = os.Remove(file); err != nil {
		t.Fatal(err)
	}
	report, err := c.VerifyHistory(r)
	if err != nil {
		t.Fatal(err)
	}
	if report["objects_available"] != true || report["author_sources_available"] != false || len(report["missing_author_objects"].([]string)) != 1 {
		t.Fatal(report)
	}
}

func TestCheckoutProtectsNewlyReferencedUnregisteredSupport(t *testing.T) {
	c, g := completeGraph(t)
	r := g.Nodes["support"].Resource
	state := authorState()
	first, err := g.CreateRevision(r, state, "with support", nil)
	if err != nil {
		t.Fatal(err)
	}
	g = editAuthor(t, c, g, "support-skill", func(doc map[string]any) {
		doc["spec"].(map[string]any)["package"].(map[string]any)["resources"] = []any{}
	})
	if _, err = g.CreateRevision(r, state, "without support", nil); err != nil {
		t.Fatal(err)
	}
	target := filepath.Join(c.RootPath(), "references", "checklist.md")
	if err = os.WriteFile(target, []byte("unregistered local notes\n"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err = g.CheckoutRevision(r, first); err == nil || !strings.Contains(err.Error(), "unregistered support") {
		t.Fatal("unregistered support overwritten", err)
	}
	got, _ := os.ReadFile(target)
	if string(got) != "unregistered local notes\n" {
		t.Fatal("local notes changed")
	}
}

func TestRetainedAuthorCompilationRejectsSourceDisagreementBeforePublication(t *testing.T) {
	c, g := completeGraph(t)
	resource := g.Nodes["support"].Resource
	state := authorState()
	record, err := g.CreateRevision(resource, state, "Retained author", nil)
	if err != nil {
		t.Fatal(err)
	}
	object, err := c.ReadAuthorObject(resource, record)
	if err != nil {
		t.Fatal(err)
	}
	bundle, _, err := g.Compile(resource.Key, state.Requirements, nil)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	raw, err := json.Marshal(object)
	if err != nil {
		t.Fatal(err)
	}
	if err = c.ValidateRetainedAuthor(resource, record, raw, state.Requirements, bundle); err != nil {
		t.Fatal(err)
	}
	item := object.Components[resource.UID]
	// Keep source YAML and decoded descriptor consistent, but contradict the
	// executable definition. A matching source hash alone cannot authorize it.
	item.Document["metadata"].(map[string]any)["name"] = "Different source behavior"
	encoded, err := Encode(item.Document)
	if err != nil {
		t.Fatal(err)
	}
	item.Raw = string(encoded)
	object.Components[resource.UID] = item
	changed := *record
	changed.AuthorDigest, err = authorDigest(object)
	if err != nil {
		t.Fatal(err)
	}
	raw, err = json.Marshal(object)
	if err != nil {
		t.Fatal(err)
	}
	if _, err = ValidateAuthorObject(resource, &changed, raw); err != nil {
		t.Fatal("source shape should be valid", err)
	}
	if err = c.ValidateRetainedAuthor(resource, &changed, raw, state.Requirements, bundle); err == nil {
		t.Fatal("source hash accepted without sealed definition agreement")
	}
	path := filepath.Join(c.RootPath(), "objects", "author", strings.TrimPrefix(changed.AuthorDigest, "sha256:")+".json")
	if _, err = os.Stat(path); !os.IsNotExist(err) {
		t.Fatal("failed compilation published source", err)
	}
}
