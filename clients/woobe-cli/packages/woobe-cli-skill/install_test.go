package assistantskill

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func privateTemp(t *testing.T) string {
	t.Helper()
	root, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	return root
}

func testOptions(t *testing.T) Options {
	t.Helper()
	return Options{ProjectDir: privateTemp(t), Version: "1.2.3", Commit: strings.Repeat("a", 40)}
}
func installed(t *testing.T, o Options, action string) Result {
	t.Helper()
	r, err := Run(action, o)
	if err != nil {
		t.Fatal(err)
	}
	return r
}
func TestAllDestinationsUpdateAndRemove(t *testing.T) {
	o := testOptions(t)
	o.Agents = []string{"codex", "codex-legacy", "claude", "copilot", "cursor", "agents"}
	r := installed(t, o, "install")
	if len(r.Installations) != 5 {
		t.Fatal(r)
	}
	source, err := Payload()
	if err != nil {
		t.Fatal(err)
	}
	for _, row := range r.Installations {
		status, err := Inspect(row.Target)
		if err != nil || status.Status != "managed" {
			t.Fatal(status, err)
		}
		for name, data := range source {
			actual, err := os.ReadFile(filepath.Join(row.Target, filepath.FromSlash(name)))
			if err != nil || string(actual) != string(data) {
				t.Fatal(name, err)
			}
		}
	}
	o.Version = "1.2.4"
	installed(t, o, "install")
	status, err := Inspect(r.Installations[0].Target)
	if err != nil || status.Version != "1.2.4" {
		t.Fatal(status, err)
	}
	sibling := filepath.Join(filepath.Dir(r.Installations[0].Target), "other")
	if err := os.Mkdir(sibling, 0755); err != nil {
		t.Fatal(err)
	}
	installed(t, o, "uninstall")
	installed(t, o, "uninstall")
	if _, err := os.Stat(sibling); err != nil {
		t.Fatal("other skill removed", err)
	}
}
func TestReadOnlyAndConflictingOptions(t *testing.T) {
	o := testOptions(t)
	o.DryRun = true
	installed(t, o, "install")
	installed(t, o, "status")
	entries, err := os.ReadDir(o.ProjectDir)
	if err != nil || len(entries) != 0 {
		t.Fatal(entries, err)
	}
	for _, invalid := range []Options{{Scope: "all"}, {Agents: []string{"missing"}}, {Path: "root", Agents: []string{"codex"}}, {Scope: "user", ProjectDir: o.ProjectDir}} {
		if _, err := Run("install", invalid); err == nil {
			t.Fatal("invalid options accepted", invalid)
		}
	}
	root := privateTemp(t)
	custom := Options{Path: root, Version: "1"}
	r := installed(t, custom, "install")
	if r.Installations[0].Target != filepath.Join(root, "woobe-cli") {
		t.Fatal(r)
	}
}
func TestPreserveDriftAndPreflightEveryDestination(t *testing.T) {
	o := testOptions(t)
	o.Agents = []string{"claude"}
	r := installed(t, o, "install")
	file := filepath.Join(r.Installations[0].Target, "SKILL.md")
	if err := os.WriteFile(file, []byte("custom"), 0644); err != nil {
		t.Fatal(err)
	}
	o.Agents = []string{"codex", "claude"}
	for _, action := range []string{"install", "uninstall"} {
		if _, err := Run(action, o); err == nil || !strings.Contains(err.Error(), "modified") {
			t.Fatal(err)
		}
	}
	if _, err := os.Stat(filepath.Join(o.ProjectDir, ".agents")); !os.IsNotExist(err) {
		t.Fatal("preflight wrote first destination", err)
	}
	r = installed(t, o, "status")
	if r.Installations[1].Status != "modified" {
		t.Fatal(r)
	}
}
func TestUnmanagedReceiptExtraAndLocks(t *testing.T) {
	o := testOptions(t)
	r := installed(t, o, "install")
	target := r.Installations[0].Target
	receiptPath := filepath.Join(target, marker)
	original, err := os.ReadFile(receiptPath)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(receiptPath); err != nil {
		t.Fatal(err)
	}
	if _, err := Run("install", o); err == nil || !strings.Contains(err.Error(), "unmanaged") {
		t.Fatal(err)
	}
	for _, bytes := range [][]byte{[]byte("{"), []byte(`{"schema_version":1,"package":"woobe-cli-skill","version":"1","files":{"SKILL.md":"` + strings.Repeat("a", 64) + `","../outside":"` + strings.Repeat("b", 64) + `"}}`)} {
		if err := os.WriteFile(receiptPath, bytes, 0644); err != nil {
			t.Fatal(err)
		}
		if _, err := Run("install", o); err == nil {
			t.Fatal("bad receipt accepted")
		}
	}
	if err := os.WriteFile(receiptPath, original, 0644); err != nil {
		t.Fatal(err)
	}
	extra := filepath.Join(target, "extra.md")
	if err := os.WriteFile(extra, []byte("custom"), 0644); err != nil {
		t.Fatal(err)
	}
	if _, err := Run("uninstall", o); err == nil {
		t.Fatal("extra deleted")
	}
	if err := os.Remove(extra); err != nil {
		t.Fatal(err)
	}
	lock := filepath.Join(filepath.Dir(target), ".woobe-cli.install.lock")
	if err := os.WriteFile(lock, []byte("locked"), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := Run("install", o); err == nil {
		t.Fatal("lock ignored")
	}
	bytes, err := os.ReadFile(lock)
	if err != nil || string(bytes) != "locked" {
		t.Fatal("lock removed", err)
	}
}
func TestHardlinksOversizedAndPayloadReceipt(t *testing.T) {
	o := testOptions(t)
	r := installed(t, o, "install")
	target := r.Installations[0].Target
	file := filepath.Join(target, "SKILL.md")
	linked := filepath.Join(o.ProjectDir, "hard.md")
	if err := os.Link(file, linked); err != nil {
		t.Fatal(err)
	}
	if _, err := Inspect(target); err == nil {
		t.Fatal("hardlink accepted")
	}
	if err := os.Remove(linked); err != nil {
		t.Fatal(err)
	}
	huge := filepath.Join(target, "huge")
	if err := os.WriteFile(huge, make([]byte, (1<<20)+1), 0644); err != nil {
		t.Fatal(err)
	}
	if _, err := Inspect(target); err == nil {
		t.Fatal("oversized file accepted")
	}
	if err := os.Remove(huge); err != nil {
		t.Fatal(err)
	}
	bytes, err := os.ReadFile(filepath.Join(target, marker))
	if err != nil {
		t.Fatal(err)
	}
	var receipt receipt
	if json.Unmarshal(bytes, &receipt) != nil || receipt.Commit != o.Commit || receipt.Package != Package {
		t.Fatal(receipt)
	}
}
func TestUserScopeAndLegacyCodexHome(t *testing.T) {
	root := privateTemp(t)
	t.Setenv("HOME", root)
	t.Setenv("USERPROFILE", root)
	t.Setenv("CODEX_HOME", filepath.Join(root, "codex-custom"))
	o := Options{Scope: "user", Agents: []string{"claude", "codex-legacy"}, Version: "1"}
	r := installed(t, o, "install")
	if r.Installations[0].Target != filepath.Join(root, ".claude/skills/woobe-cli") || r.Installations[1].Target != filepath.Join(root, "codex-custom/skills/woobe-cli") {
		t.Fatal(r)
	}
}

func TestRollbackRestoresPreviousInstallation(t *testing.T) {
	o := testOptions(t)
	o.Agents = []string{"codex"}
	r := installed(t, o, "install")
	target := r.Installations[0].Target
	previous, err := os.ReadFile(filepath.Join(target, marker))
	if err != nil {
		t.Fatal(err)
	}
	original := renamePath
	defer func() { renamePath = original }()
	renamePath = func(source, destination string) error {
		if strings.Contains(destination, ".claude") {
			return os.ErrPermission
		}
		return original(source, destination)
	}
	o.Agents = []string{"codex", "claude"}
	o.Version = "2"
	if _, err := Run("install", o); err == nil {
		t.Fatal("injected failure ignored")
	}
	actual, err := os.ReadFile(filepath.Join(target, marker))
	if err != nil || string(actual) != string(previous) {
		t.Fatal("rollback lost original receipt", err)
	}
	if _, err := os.Stat(filepath.Join(filepath.Dir(target), ".woobe-cli.install.lock")); !os.IsNotExist(err) {
		t.Fatal("lock retained", err)
	}
}
func TestRollbackPreservesConcurrentEdits(t *testing.T) {
	o := testOptions(t)
	r := installed(t, o, "install")
	target := r.Installations[0].Target
	original := renamePath
	defer func() { renamePath = original }()
	renamePath = func(source, destination string) error {
		if strings.Contains(destination, ".claude") {
			if err := os.WriteFile(filepath.Join(target, "SKILL.md"), []byte("concurrent edit"), 0644); err != nil {
				return err
			}
			return os.ErrPermission
		}
		return original(source, destination)
	}
	o.Agents = []string{"codex", "claude"}
	if _, err := Run("install", o); err == nil || !strings.Contains(err.Error(), "rollback preserved") {
		t.Fatal(err)
	}
	bytes, err := os.ReadFile(filepath.Join(target, "SKILL.md"))
	if err != nil || string(bytes) != "concurrent edit" {
		t.Fatal("concurrent edit deleted", err)
	}
}
