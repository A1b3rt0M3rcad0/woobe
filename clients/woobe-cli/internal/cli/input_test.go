package cli

import "testing"

func TestDuplicateInputRejectedBeforeDryRun(t *testing.T) {
	code, _ := invoke(t, []string{"project", "agent", "create", "--project", "p", "--file", "-", "--dry-run"}, `{"name":"a","name":"b"}`)
	if code != 2 {
		t.Fatal(code)
	}
}
