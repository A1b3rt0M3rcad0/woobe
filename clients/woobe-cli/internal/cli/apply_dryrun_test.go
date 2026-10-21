package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestApplyDryRunNeverCreatesCheckpoint(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "cp")
	out := &bytes.Buffer{}
	a := New(bytes.NewBufferString(`{"schema_version":"1","steps":[{"id":"a","command":"project agent create","body":{}}]}`), out, &bytes.Buffer{})
	code := a.Execute(context.Background(), []string{"manifest", "apply", "--yes", "--dry-run", "--checkpoint", p, "--file", "-", "--config", filepath.Join(dir, "config")})
	if code != 0 {
		t.Fatal(code, out.String())
	}
	var v map[string]any
	json.Unmarshal(out.Bytes(), &v)
	if v["data"].(map[string]any)["executed"] != false {
		t.Fatal(v)
	}
	if _, e := os.Stat(p); !os.IsNotExist(e) {
		t.Fatal(e)
	}
	if _, e := os.Stat(p + ".lock"); !os.IsNotExist(e) {
		t.Fatal(e)
	}
}
