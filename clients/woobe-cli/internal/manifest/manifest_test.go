package manifest

import "testing"

func TestOrderAndCycles(t *testing.T) {
	d := Document{Steps: []Step{{ID: "network", Command: "x", DependsOn: []string{"agent"}}, {ID: "agent", Command: "x"}}}
	steps, e := d.Order()
	if e != nil || steps[0].ID != "agent" {
		t.Fatal(steps, e)
	}
	d.Steps[1].DependsOn = []string{"network"}
	if _, e = d.Order(); e == nil {
		t.Fatal("cycle accepted")
	}
	d.Steps[1].DependsOn = []string{"missing"}
	if _, e = d.Order(); e == nil {
		t.Fatal("missing dependency accepted")
	}
}
func TestStrictDocument(t *testing.T) {
	for _, b := range []string{`{"schema_version":"2","steps":[]}`, `{"schema_version":"1","steps":[],"typo":true}`, `{} {}`, `{"schema_version":"1","steps":[{"id":"a","command":"x"},{"id":"a","command":"y"}]}`} {
		if _, e := Parse([]byte(b)); e == nil {
			t.Fatal(b)
		}
	}
}
func TestReferenceResolution(t *testing.T) {
	s := Step{Args: []string{"${steps.agent.id}"}, Body: []byte(`{"nodes":[{"agent_id":"${steps.agent.id}"}]}`)}
	got, e := ResolveStep(s, map[string]any{"agent": map[string]any{"id": "a"}})
	if e != nil || got.Args[0] != "a" {
		t.Fatal(got, e)
	}
	if _, e = ResolveStep(s, map[string]any{}); e == nil {
		t.Fatal("missing reference accepted")
	}
}
func TestReferencesMustDeclareDependencies(t *testing.T) {
	s := Step{ID: "prompt", Command: "x", Args: []string{"${steps.agent.id}"}}
	if ValidateReferences(s) == nil {
		t.Fatal("implicit dependency accepted")
	}
	s.DependsOn = []string{"agent"}
	if e := ValidateReferences(s); e != nil {
		t.Fatal(e)
	}
}
