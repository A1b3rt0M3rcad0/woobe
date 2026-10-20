package manifest

import "testing"

func TestTypedParentReference(t *testing.T) {
	for _, kind := range []string{"Network", "AgentPrompt"} {
		parents := `{}`
		if kind == "AgentPrompt" {
			parents = `{"agent":"a"}`
		}
		b := `{"schema_version":"2","project_id":"p","resources":[{"key":"x","kind":"` + kind + `","action":"create","parents":` + parents + `,"spec":{}},{"key":"prompt","kind":"AgentPrompt","action":"create","parents":{"agent":"${resources.x.id}"},"depends_on":["x"],"spec":{}}]}`
		if _, e := Parse([]byte(b)); e == nil {
			t.Fatal(kind)
		}
	}
}
