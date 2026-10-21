package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"testing"
)

func TestLocalWriteFailureHasNotAttemptedOutcome(t *testing.T) {
	code, v := invoke(t, []string{"project", "agent", "create"}, "")
	if code != 2 || v["error"].(map[string]any)["write_outcome"] != "not_attempted" {
		t.Fatal(code, v)
	}
	e := output.New(4, "denied")
	n := notAttempted(e).(*output.Error)
	if n.Outcome != "not_attempted" || e.Outcome != "" {
		t.Fatal(n, e)
	}
}
