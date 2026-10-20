package cli

import "testing"

func TestForeignPathPreviewRejected(t *testing.T) {
	code, _ := invoke(t, []string{"request", "POST", "//foreign.invalid/x", "--dry-run"}, "")
	if code != 2 {
		t.Fatal(code)
	}
}
