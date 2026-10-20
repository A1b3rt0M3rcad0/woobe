package cli

import (
	"runtime"
	"testing"
)

func TestVersionIncludesBuildIdentity(t *testing.T) {
	code, v := invoke(t, []string{"version"}, "")
	data := v["data"].(map[string]any)
	if code != 0 || data["commit"] != Commit || data["go_version"] != runtime.Version() || data["os"] != runtime.GOOS {
		t.Fatal(v)
	}
}
