package cli

import (
	"os"
	"path/filepath"
	"testing"
)

func TestCheckpointStatusOffline(t *testing.T) {
	p := filepath.Join(t.TempDir(), "cp")
	_ = os.WriteFile(p, []byte(`{"steps":{"a":"unknown","b":"committed"}}`), 0600)
	code, v := invoke(t, []string{"manifest", "status", "--checkpoint", p}, "")
	if code != 0 || v["data"].(map[string]any)["resume_requires_reconciliation"] != true {
		t.Fatal(v)
	}
}
