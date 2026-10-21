package manifest

import (
	"encoding/json"
	"testing"
)

func TestCategoryIntentsCannotAssignAuthority(t *testing.T) {
	for _, field := range []string{"grants", "category_id", "project_id", "workspace_id", "status", "revision", "system", "scope"} {
		spec, _ := json.Marshal(map[string]any{field: "value"})
		d := ResourceDocument{SchemaVersion: "2", Workspace: "w", Resources: []Resource{{Key: "c", Kind: "AuthorityCategory", Action: "update", ResourceID: "c", IfMatch: `"category:c:1"`, Spec: spec}}}
		if _, e := d.Compile(); e == nil {
			t.Fatal("accepted", field)
		}
	}
	d := ResourceDocument{SchemaVersion: "2", Workspace: "w", Resources: []Resource{{Key: "c", Kind: "AuthorityCategory", Action: "update", ResourceID: "c", Spec: []byte(`{"name":"reader"}`)}}}
	if _, e := d.Compile(); e == nil {
		t.Fatal("update without ETag")
	}
}
