package cli

import "testing"

func TestSingleSegmentResourceIDs(t *testing.T) {
	for _, id := range []string{"../a", "a/b", "a%2fb", "a?b", "a#b", "a b", "a\\b", "a\x00b"} {
		code, v := invoke(t, []string{"project", "agent", "get", id, "--dry-run"}, "")
		if code != 2 {
			t.Fatal(id, code, v)
		}
	}
	code, v := invoke(t, []string{"project", "agent", "get", "a-b_1", "--dry-run"}, "")
	if code != 0 {
		t.Fatal(code, v)
	}
}
