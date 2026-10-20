package controlplane

import (
	"testing"
	"time"
)

func TestAmbiguousPaths(t *testing.T) {
	for _, p := range []string{"/x/..", "/x/%2e%2e", "/x/%2Fother", "/x/%5cother", "/x/%252e", "/x/%00", "/x/%xx", "/x/\x7f"} {
		if ValidatePath(p) == nil {
			t.Fatal(p)
		}
	}
	for _, p := range []string{"/ai/agents/a", "/x/hello%20world", "/x/%C3%A9"} {
		if e := ValidatePath(p); e != nil {
			t.Fatal(p, e)
		}
	}
	if _, e := New("https://host/base/../other", "", time.Second); e == nil {
		t.Fatal("base path")
	}
}
