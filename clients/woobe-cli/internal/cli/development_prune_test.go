package cli

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
)

func TestPackageRegistryPruneRequiresExplicitExecutionAndRetainsFiles(t *testing.T) {
	t.Chdir(t.TempDir())
	code, result := invoke(t, []string{"init"}, "")
	if code != 0 {
		t.Fatal(code, result)
	}
	c, err := devworkspace.Load(".woobe-config")
	if err != nil {
		t.Fatal(err)
	}
	a, err := c.Add("Agent", "deleted", "", map[string]any{"kind": "Agent", "metadata": map[string]any{"name": "Deleted"}, "spec": map[string]any{}}, nil, false)
	if err != nil {
		t.Fatal(err)
	}
	descriptor := filepath.Join(c.RootPath(), a.Path, "agent.yaml")
	if err := os.Remove(descriptor); err != nil {
		t.Fatal(err)
	}
	before, _ := os.ReadFile(c.File)
	for _, args := range [][]string{{"resources", "prune"}, {"resources", "prune", "--yes", "--query", "x=y"}} {
		code, result = invoke(t, args, "")
		if code != 2 {
			t.Fatal("unsafe invocation accepted", code, result)
		}
	}
	code, result = invoke(t, []string{"resources", "prune", "--dry-run"}, "")
	if code != 0 || result["data"].(map[string]any)["executed"] != false {
		t.Fatal(code, result)
	}
	after, _ := os.ReadFile(c.File)
	if !bytes.Equal(before, after) {
		t.Fatal("preview changed config")
	}
	code, result = invoke(t, []string{"resources", "prune", "--yes"}, "")
	if code != 0 {
		t.Fatal(code, result)
	}
	data := result["data"].(map[string]any)
	if data["executed"] != true || data["remote_deleted"] != false || data["bindings_retained"] != true {
		t.Fatal(data)
	}
	code, result = invoke(t, []string{"config", "check"}, "")
	if code != 0 || result["data"].(map[string]any)["resources"] != float64(0) {
		t.Fatal(code, result)
	}
	if _, err := os.Stat(filepath.Join(c.RootPath(), ".state")); err != nil {
		t.Fatal("private state deleted", err)
	}
}
