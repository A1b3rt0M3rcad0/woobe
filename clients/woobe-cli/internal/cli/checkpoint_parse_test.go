package cli

import "testing"

func TestCheckpointRejectsAmbiguity(t *testing.T) {
	for _, s := range []string{`{"steps":{"a":"done"}}`, `{"steps":{},"extra":1}`, `{"steps":{"a":"unknown","a":"committed"}}`} {
		if _, e := parseCheckpoint([]byte(s)); e == nil {
			t.Fatal(s)
		}
	}
}
