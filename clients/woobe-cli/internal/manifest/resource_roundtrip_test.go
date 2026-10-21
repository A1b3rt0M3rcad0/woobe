package manifest

import (
	"encoding/json"
	"testing"
)

func TestCompiledResourceDocumentHasStableExecutionIdentity(t *testing.T) {
	d, e := Parse([]byte(`{"schema_version":"2","project_id":"p","resources":[{"key":"agent","kind":"Agent","action":"create","spec":{"name":"A"}}]}`))
	if e != nil {
		t.Fatal(e)
	}
	b, e := json.Marshal(d)
	if e != nil {
		t.Fatal(e)
	}
	steps, e := Parse(b)
	if e != nil || d.Hash() != steps.Hash() {
		t.Fatal(e, string(b))
	}
}
func TestAllResourceKindsCompileExplicitActions(t *testing.T) {
	for _, k := range Kinds() {
		for _, action := range []string{"create", "update"} {
			r := Resource{Key: "x", Kind: k.Name, Action: action, Parents: map[string]string{}, Spec: []byte(`{}`)}
			for _, p := range k.Parents {
				r.Parents[p] = "parent"
			}
			if action == "update" {
				r.ResourceID = "existing"
				r.IfMatch = "revision"
				if k.Name == "Project" {
					r.ResourceID = "p"
				}
			}
			d := ResourceDocument{SchemaVersion: "2", Workspace: "w", Project: "p", Resources: []Resource{r}}
			_, e := d.Compile()
			supported := action == "create" && k.Create != "" || action == "update" && k.Update != ""
			if (e == nil) != supported {
				t.Fatal(k.Name, action, e)
			}
		}
	}
}
