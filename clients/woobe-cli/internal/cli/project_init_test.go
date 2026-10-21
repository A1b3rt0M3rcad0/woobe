package cli

import (
	"bytes"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	assistantskill "github.com/A1b3rt0M3rcad0/woobe-cli/packages/woobe-cli-skill"
)

func setupCall(t *testing.T, args ...string) map[string]any {
	t.Helper()
	code, r := invoke(t, append([]string{"init"}, args...), "")
	if code != 0 {
		t.Fatalf("init failed (%d): %v", code, r)
	}
	return r["data"].(map[string]any)
}
func TestProjectInitAssistantPresetsAndRepeat(t *testing.T) {
	for name, layout := range assistantskill.Presets {
		t.Run(name, func(t *testing.T) {
			t.Chdir(t.TempDir())
			original := []byte("# Existing project\r\n\r\nKeep this instruction.\r\n")
			os.WriteFile("AGENTS.md", original, 0644)
			first := setupCall(t, "--agents", name)
			configBefore, _ := os.ReadFile(".woobe-config")
			instructions, _ := os.ReadFile("AGENTS.md")
			if !bytes.HasPrefix(instructions, original) || !bytes.Contains(instructions, []byte(layout.Project+"/woobe-cli/SKILL.md")) {
				t.Fatal("existing instructions or skill reference lost")
			}
			status, e := assistantskill.Inspect(filepath.Join(filepath.Dir(first["config"].(string)), layout.Project, "woobe-cli"))
			if e != nil || status.Status != "managed" {
				t.Fatal(status, e)
			}
			if name == "claude" {
				data, e := os.ReadFile("CLAUDE.md")
				if e != nil || !bytes.Contains(data, []byte("AGENTS.md")) {
					t.Fatal("missing Claude entry point", e)
				}
			}
			if name == "copilot" {
				if _, e := os.Stat(".github/copilot-instructions.md"); e != nil {
					t.Fatal(e)
				}
			}
			again := setupCall(t, "--agents", name)
			configAfter, _ := os.ReadFile(".woobe-config")
			after, _ := os.ReadFile("AGENTS.md")
			if first["registry_id"] != again["registry_id"] || !bytes.Equal(configBefore, configAfter) || !bytes.Equal(instructions, after) {
				t.Fatal("repeat changed registry or duplicated instructions")
			}
			if _, e := os.Stat(".woobe-init.lock"); !os.IsNotExist(e) {
				t.Fatal("lock retained", e)
			}
		})
	}
}
func TestProjectInitDryRunConflictsAndExistingContext(t *testing.T) {
	t.Chdir(t.TempDir())
	plan := setupCall(t, "--agents", "codex,claude", "--dry-run")
	if plan["executed"] != false {
		t.Fatal(plan)
	}
	entries, _ := os.ReadDir(".")
	if len(entries) != 0 {
		t.Fatal("dry-run wrote files")
	}
	for _, args := range [][]string{{"--agents", "invalid"}, {"--agents", ""}, {"--root", ""}, {"--root", ".git/source"}, {"--root", ".woobe-lab"}, {"--root", "AGENTS.md"}, {"--agents", "codex", "--root", ".agents/skills/woobe-cli"}} {
		code, _ := invoke(t, append([]string{"init"}, args...), "")
		if code != 2 {
			t.Fatal(args, code)
		}
		entries, _ := os.ReadDir(".")
		if len(entries) != 0 {
			t.Fatal("invalid init left project files", args, entries)
		}
	}
	setupCall(t, "--root", "definitions [local]")
	before, _ := os.ReadFile(".woobe-config")
	setupCall(t, "--agents", "codex")
	after, _ := os.ReadFile(".woobe-config")
	if !bytes.Equal(before, after) {
		t.Fatal("adding agent changed root/identity")
	}
	for _, args := range [][]string{{"--root", "other"}, {"--context", "different"}} {
		code, _ := invoke(t, append([]string{"init"}, args...), "")
		if code != 2 {
			t.Fatal("changed existing binding", args)
		}
	}
	setupCall(t, "--agents", "claude,codex-legacy")
	data, _ := os.ReadFile("AGENTS.md")
	for _, layout := range []string{".agents/skills", ".codex/skills", ".claude/skills"} {
		if !bytes.Contains(data, []byte(layout)) {
			t.Fatal("lost previous assistant", layout)
		}
	}
	os.Mkdir("nested", 0755)
	t.Chdir("nested")
	code, _ := invoke(t, []string{"init", "--agents", "codex"}, "")
	if code != 2 {
		t.Fatal("created nested registry")
	}
}
func TestProjectInitPreservesEditedFilesAndRejectsLinks(t *testing.T) {
	for _, target := range []string{"AGENTS.md", "CLAUDE.md", ".gitignore", ".claude/skills/woobe-cli/SKILL.md"} {
		t.Run(target, func(t *testing.T) {
			t.Chdir(t.TempDir())
			setupCall(t, "--agents", "claude")
			before, _ := os.ReadFile(target)
			changed := append([]byte{}, before...)
			if strings.HasSuffix(target, "SKILL.md") {
				changed = append(changed, []byte("\nCustom edit\n")...)
			} else {
				changed = bytes.Replace(changed, []byte("woobe-cli:init:v1 sha256="), []byte("woobe-cli:init:v1 sha256=0"), 1)
			}
			os.WriteFile(target, changed, 0644)
			code, _ := invoke(t, []string{"init", "--agents", "claude,codex"}, "")
			if code != 2 {
				t.Fatal("overwrote modified setup")
			}
			actual, _ := os.ReadFile(target)
			if !bytes.Equal(actual, changed) {
				t.Fatal("lost local edits")
			}
			if _, err := os.Stat(".agents/skills/woobe-cli"); !os.IsNotExist(err) {
				t.Fatal("installed skill before conflict validation")
			}
		})
	}
	t.Run("symlink", func(t *testing.T) {
		t.Chdir(t.TempDir())
		outside := filepath.Join(t.TempDir(), "instructions")
		os.WriteFile(outside, []byte("keep"), 0644)
		if e := os.Symlink(outside, "AGENTS.md"); e != nil {
			t.Skip(e)
		}
		code, _ := invoke(t, []string{"init", "--agents", "codex"}, "")
		if code != 2 {
			t.Fatal("followed instruction link")
		}
		data, _ := os.ReadFile(outside)
		if string(data) != "keep" {
			t.Fatal("overwrote link target")
		}
		if _, err := os.Stat(".woobe-config"); !os.IsNotExist(err) {
			t.Fatal("created registry before link validation")
		}
	})
}
func TestProjectInitGitIgnoreKeepsAuthorFilesVersionable(t *testing.T) {
	for _, root := range []string{".woobe", "definitions [local]", "."} {
		t.Run(root, func(t *testing.T) {
			t.Chdir(t.TempDir())
			if out, e := exec.Command("git", "init", "--quiet").CombinedOutput(); e != nil {
				t.Fatal(string(out), e)
			}
			os.WriteFile(".gitignore", []byte("# User rules\n*.log\n!.woobe-lab/\n"), 0644)
			setupCall(t, "--root", root, "--agents", "codex")
			// Later exceptions must not override the init-managed protection after re-init.
			f, _ := os.OpenFile(".gitignore", os.O_APPEND|os.O_WRONLY, 0644)
			f.WriteString("!.woobe-lab/\n")
			f.Close()
			setupCall(t, "--agents", "codex")
			for _, path := range []string{".woobe-lab/report.json", filepath.ToSlash(filepath.Join(root, ".state/private.json"))} {
				if out, e := exec.Command("git", "check-ignore", "--no-index", path).CombinedOutput(); e != nil {
					t.Fatal("private path not ignored", path, string(out), e)
				}
			}
			for _, path := range []string{".woobe-config", "AGENTS.md", ".agents/skills/woobe-cli/SKILL.md", filepath.ToSlash(filepath.Join(root, "agents/support/agent.yaml"))} {
				if exec.Command("git", "check-ignore", "--no-index", path).Run() == nil {
					t.Fatal("author source unexpectedly ignored", path)
				}
			}
			data, _ := os.ReadFile(".gitignore")
			if !bytes.Contains(data, []byte("# User rules\n*.log\n")) {
				t.Fatal("lost user ignore rules")
			}
		})
	}
}

func TestProjectInitKeepsAuthorFilesAndPendingState(t *testing.T) {
	t.Chdir(t.TempDir())
	setupCall(t)
	author := `{"kind":"Agent","metadata":{"name":"Support"},"spec":{"instructions":"Keep exact author content"}}`
	if err := os.WriteFile("author.json", []byte(author), 0644); err != nil {
		t.Fatal(err)
	}
	code, result := invoke(t, []string{"resources", "create", "agent", "support", "--file", "author.json"}, "")
	if code != 0 {
		t.Fatal(code, result)
	}
	files := []string{".woobe-config", ".woobe/agents/support/agent.yaml", ".woobe/.state/pending-example"}
	if err := os.WriteFile(files[2], []byte("Retain pending operation evidence"), 0600); err != nil {
		t.Fatal(err)
	}
	before := map[string][]byte{}
	for _, path := range files {
		data, err := os.ReadFile(path)
		if err != nil {
			t.Fatal(err)
		}
		before[path] = data
	}
	setupCall(t, "--agents", "codex")
	setupCall(t, "--agents", "claude", "--dry-run")
	for path, data := range before {
		after, err := os.ReadFile(path)
		if err != nil || !bytes.Equal(data, after) {
			t.Fatal("existing development state changed", path, err)
		}
	}
	if err := os.WriteFile(".woobe-init.lock", []byte(""), 0600); err != nil {
		t.Fatal(err)
	}
	code, _ = invoke(t, []string{"init", "--agents", "claude"}, "")
	if code != 2 {
		t.Fatal("concurrent setup not blocked")
	}
	if _, err := os.Stat(".claude"); !os.IsNotExist(err) {
		t.Fatal("blocked setup installed skill")
	}
	if _, err := os.Stat(".woobe-init.lock"); err != nil {
		t.Fatal("removed another process lock")
	}
}
