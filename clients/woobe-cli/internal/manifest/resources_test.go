package manifest

import (
	"strings"
	"testing"
)

func TestResourceManifestCompilesConfiguration(t *testing.T) {
	d, e := Parse([]byte(`{"schema_version":"2","project_id":"p","resources":[{"key":"a","kind":"Agent","action":"create","spec":{"name":"A","counter":9007199254740993}},{"key":"prompt","kind":"AgentPrompt","action":"create","parents":{"agent":"${resources.a.id}"},"depends_on":["a"],"spec":{"content":"Teach"}},{"key":"n","kind":"Network","action":"update","resource_id":"n","spec":{"description":null},"if_match":"rev"}]}`))
	if e != nil {
		t.Fatal(e)
	}
	if d.SourceVersion != "2" || d.Steps[1].Args[0] != "${steps.a.id}" || d.Steps[2].Command != "project network update" || !strings.Contains(string(d.Steps[0].Body), "9007199254740993") || !strings.Contains(string(d.Steps[0].Body), `"project_id":"p"`) {
		t.Fatal(d)
	}
}
func TestResourceManifestRejectsImplicitOrUnsafeChanges(t *testing.T) {
	for _, r := range []string{`{"key":"a","kind":"Agent","action":"upsert","spec":{}}`, `{"key":"a","kind":"Agent","action":"update","spec":{}}`, `{"key":"a","kind":"Agent","action":"create","resource_id":"a","spec":{}}`, `{"key":"a","kind":"AgentPrompt","action":"update","resource_id":"x","parents":{"agent":"a"},"spec":{}}`, `{"key":"a","kind":"Agent","action":"create","spec":{"project_id":"other"}}`, `{"key":"a","kind":"Network","action":"create","spec":{"description":"prefix ${resources.x.id}"}}`, `{"key":"a","kind":"Agent","action":"create","spec":{"password":"secret"}}`, `{"key":"a","kind":"AgentPrompt","action":"create","parents":{"agent":"${resources.b.id}"},"spec":{}}`, `{"key":"a","kind":"Unknown","action":"create","spec":{}}`} {
		b := `{"schema_version":"2","project_id":"p","resources":[` + r + `]}`
		if _, e := Parse([]byte(b)); e == nil {
			t.Fatal(b)
		}
	}
}
