package manifest

import "testing"

func TestDuplicateDependency(t *testing.T) {
	if ValidateReferences(Step{ID: "a", DependsOn: []string{"b", "b"}}) == nil {
		t.Fatal("duplicate")
	}
	if ValidateReferences(Step{ID: "a", DependsOn: []string{"a"}}) == nil {
		t.Fatal("self")
	}
}
