package manifest

import "testing"

func TestReferenceAddressableIDs(t *testing.T) {
	for _, id := range []string{"a.b", "a b", "${steps.x.id}"} {
		if _, e := (Document{Steps: []Step{{ID: id, Command: "x"}}}).Order(); e == nil {
			t.Fatal(id)
		}
	}
}
