package cli

import "testing"

func TestScopedQueryCannotOverrideContext(t *testing.T) {
	for _, q := range [][]string{{"project_id=other"}, {"project_id=p", "project_id=p"}} {
		a := New(nil, nil, nil)
		a.Query = q
		if a.addScopeQuery("project_id", "p") == nil {
			t.Fatal(q)
		}
	}
	a := New(nil, nil, nil)
	a.Query = []string{"project_id=p"}
	if e := a.addScopeQuery("project_id", "p"); e != nil || len(a.Query) != 1 {
		t.Fatal(a.Query, e)
	}
}
