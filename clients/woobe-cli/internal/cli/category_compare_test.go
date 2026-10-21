package cli

import "testing"

func TestCategoryComparisonUsesSetsButPreservesRestrictions(t *testing.T) {
	current := map[string]any{"permissions": []any{"agent:write", "agent:read"}, "conditions": map[string]any{"interfaces": []any{"stream", "http"}}}
	desired := map[string]any{"permissions": []any{"agent:read", "agent:write", "agent:read"}, "conditions": map[string]any{"interfaces": []any{"http", "stream"}}}
	changes, e := categoryChanges(current, desired)
	if e != nil || len(changes) != 0 {
		t.Fatal(changes, e)
	}
	desired["conditions"] = map[string]any{}
	changes, e = categoryChanges(current, desired)
	if e != nil || len(changes) != 1 {
		t.Fatal(changes, e)
	}
	// An empty restriction differs from an absent restriction.
	desired["conditions"] = map[string]any{"interfaces": []any{}}
	changes, e = categoryChanges(current, desired)
	if e != nil || len(changes) != 1 {
		t.Fatal(changes, e)
	}
	desired["conditions"] = map[string]any{"future": []any{}}
	if _, e = categoryChanges(current, desired); e == nil {
		t.Fatal("unknown condition accepted")
	}
}
