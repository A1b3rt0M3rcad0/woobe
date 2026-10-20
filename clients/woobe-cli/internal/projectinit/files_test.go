package projectinit

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestProjectInitManagedBlockPreservesCustomText(t *testing.T) {
	for _, newline := range []string{"\n", "\r\n"} {
		prefix := "# Local rules" + newline + "Keep these instructions." + newline
		f := File{Path: filepath.Join(t.TempDir(), "AGENTS.md"), Before: []byte(prefix), Exists: true, Mode: 0644}
		managed, err := Manage(f, "First instruction\nSecond instruction\n", "<!--", []string{"claude", "codex"}, false)
		if err != nil {
			t.Fatal(err)
		}
		original := append(managed.After, []byte("User footer"+newline)...)
		managed.Before = original
		changed, err := Manage(managed, "Updated instruction", "<!--", []string{"codex"}, false)
		if err != nil {
			t.Fatal(err)
		}
		if !bytes.HasPrefix(changed.After, []byte(prefix)) || !bytes.HasSuffix(changed.After, []byte("User footer"+newline)) {
			t.Fatal("custom text changed")
		}
		tampered := bytes.ReplaceAll(original, []byte("Second instruction"), []byte("User edit"))
		managed.Before = tampered
		if _, err := Manage(managed, "Replacement", "<!--", nil, false); err == nil {
			t.Fatal("local edit overwritten")
		}
	}
}

func TestProjectInitFileDriftAndInvalidInput(t *testing.T) {
	directory, err := filepath.EvalSymlinks(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(directory, "AGENTS.md")
	if err := os.WriteFile(path, []byte("Original\n"), 0600); err != nil {
		t.Fatal(err)
	}
	f, err := Read(path)
	if err != nil {
		t.Fatal(err)
	}
	f, err = Manage(f, "Instructions", "<!--", nil, false)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("Concurrent edit\n"), 0600); err != nil {
		t.Fatal(err)
	}
	if f.Apply() == nil {
		t.Fatal("concurrent edits overwritten")
	}
	got, _ := os.ReadFile(path)
	if string(got) != "Concurrent edit\n" {
		t.Fatal("concurrent edits changed")
	}
	for _, invalid := range [][]byte{{0xff}, {'a', 0}, bytes.Repeat([]byte("x"), maxFile+1)} {
		if err := os.WriteFile(path, invalid, 0600); err != nil {
			t.Fatal(err)
		}
		if _, err := Read(path); err == nil {
			t.Fatal("invalid input accepted")
		}
	}
}

func TestProjectInitDuplicateAndIncompleteBlocks(t *testing.T) {
	f, err := Manage(File{}, "Instructions", "#", nil, true)
	if err != nil {
		t.Fatal(err)
	}
	for _, invalid := range []string{string(f.After) + string(f.After), strings.ReplaceAll(string(f.After), "# /woobe-cli:init", ""), "# woobe-cli:init:v1"} {
		f.Before = []byte(invalid)
		if _, err := Manage(f, "Replacement", "#", nil, true); err == nil {
			t.Fatal("malformed block accepted")
		}
	}
}
