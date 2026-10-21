package manifest

import "testing"

func TestKindsDeclareScope(t *testing.T) {
	for _, k := range Kinds() {
		if k.Scope != "project" && !(k.Name == "AuthorityCategory" && k.Scope == "workspace") {
			t.Fatalf("unexpected scope for %s: %s", k.Name, k.Scope)
		}
	}
}

func TestCategoryWorkspaceResourceScope(t *testing.T) {
	raw := `{"schema_version":"2","workspace_id":"w","resources":[{"key":"reader","kind":"AuthorityCategory","action":"create","spec":{"name":"reader","permissions":["agent:read"]}}]}`
	d, e := Parse([]byte(raw))
	if e != nil || d.Project != "" || d.Steps[0].Command != "workspace authority category create" {
		t.Fatal(d, e)
	}
	for _, b := range []string{`{"schema_version":"2","project_id":"p","resources":[{"key":"r","kind":"AuthorityCategory","action":"create","spec":{}}]}`, `{"schema_version":"2","workspace_id":"w","resources":[{"key":"a","kind":"Agent","action":"create","spec":{}}]}`} {
		if _, e := Parse([]byte(b)); e == nil {
			t.Fatal("missing owning scope accepted")
		}
	}
}
