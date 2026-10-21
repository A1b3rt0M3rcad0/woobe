package cli

import (
	"bytes"
	"os"
	"path/filepath"
	"testing"

	assistantskill "github.com/A1b3rt0M3rcad0/woobe-cli/packages/woobe-cli-skill"
)

func TestAssistantSkillPresetCommandLifecycle(t *testing.T) {
	payload, err := assistantskill.Payload()
	if err != nil {
		t.Fatal(err)
	}
	for _, group := range []string{"skill", "skills"} {
		for agent, preset := range assistantskill.Presets {
			t.Run(group+"/"+agent, func(t *testing.T) {
				root, err := filepath.EvalSymlinks(t.TempDir())
				if err != nil {
					t.Fatal(err)
				}
				target := filepath.Join(root, preset.Project, "woobe-cli")
				call := func(action string, extra ...string) map[string]any {
					t.Helper()
					args := []string{group, action, "--agent", agent, "--project-dir", root, "--output", "json"}
					code, result := invoke(t, append(args, extra...), "")
					if code != 0 || result["success"] != true {
						t.Fatalf("%s: exit %d: %v", action, code, result)
					}
					return result["data"].(map[string]any)
				}
				if call("install", "--dry-run")["executed"] != false {
					t.Fatal("dry-run executed installation")
				}
				if _, err := os.Stat(target); !os.IsNotExist(err) {
					t.Fatal("dry-run created destination", err)
				}
				call("install")
				for name, expected := range payload {
					actual, err := os.ReadFile(filepath.Join(target, filepath.FromSlash(name)))
					if err != nil || !bytes.Equal(actual, expected) {
						t.Fatalf("embedded payload mismatch %s: %v", name, err)
					}
				}
				call("install") // An unchanged managed installation is safely repeatable.
				rows := call("status")["installations"].([]any)
				if len(rows) != 1 || rows[0].(map[string]any)["status"] != "managed" {
					t.Fatal("installation not recognized", rows)
				}
				call("uninstall")
				if _, err := os.Stat(target); !os.IsNotExist(err) {
					t.Fatal("uninstall retained destination", err)
				}
			})
		}
	}
}

func TestEmbeddedAssistantSkillOfflineAliasesAndRuntimeBoundary(t *testing.T) {
	root := t.TempDir()
	for _, action := range []string{"install", "status", "uninstall"} {
		code, v := invoke(t, []string{"skill", action, "--agent", "codex,claude", "--project-dir", root, "--output", "json"}, "")
		if code != 0 || v["success"] != true {
			t.Fatal(action, v)
		}
	}
	if _, err := os.Stat(filepath.Join(root, ".agents/skills/woobe-cli")); !os.IsNotExist(err) {
		t.Fatal("uninstall did not remove skill", err)
	}
	code, v := invoke(t, []string{"--dry-run", "skill", "install", "--project-dir", root, "--dry-run", "--output", "json"}, "")
	if code != 0 || v["data"].(map[string]any)["executed"] != false {
		t.Fatal(v)
	}
	code, v = invoke(t, []string{"skills", "agents", "--output", "json"}, "")
	if code != 0 || len(v["data"].([]any)) != 6 {
		t.Fatal(v)
	}
	code, v = invoke(t, []string{"skill", "install", "--project", "not-a-directory", "--output", "json"}, "")
	if code != 2 {
		t.Fatal("Project ID used for skill install", v)
	}
	// Runtime Skills remain their canonical HTTP operations, never redirected.
	a := New(nil, nil, nil)
	if op, ok := a.operation("project skill list"); !ok || op.Kind != "http" {
		t.Fatal("runtime Skill route changed", op, ok)
	}
}
