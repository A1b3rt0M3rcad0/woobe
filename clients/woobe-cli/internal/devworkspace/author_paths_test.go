package devworkspace

import (
	"os"
	"path/filepath"
	"testing"
)

func TestAuthorResourcePathsRejectPrivateAndNonportableNames(t *testing.T) {
	for _, path := range []string{".STATE/tool", "tools/.Woobe-Config", "tools/.GIT/file", "tools/CON", "tools/NUL.txt", "tools/trailing.", "tools/trailing ", "tools/stream:private", "tools/control\nname"} {
		t.Run(path, func(t *testing.T) {
			c, err := Create(t.TempDir(), ".woobe", "")
			if err != nil {
				t.Fatal(err)
			}
			uid, err := NewID()
			if err != nil {
				t.Fatal(err)
			}
			c.Resources = []Resource{{UID: uid, Kind: "Tool", Key: "lookup", Alias: "lookup", Path: path}}
			if err := c.Validate(); err == nil {
				t.Fatal("unsafe author path accepted", path)
			}
		})
	}
}

func TestSkillCreationCannotWritePrivateOperationalFiles(t *testing.T) {
	c, err := Create(t.TempDir(), ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	before, err := os.ReadFile(c.File)
	if err != nil {
		t.Fatal(err)
	}
	document := map[string]any{"kind": "Skill", "metadata": map[string]any{"name": "Procedure"}, "spec": map[string]any{"package": map[string]any{"manifest": "../../.state/private.md"}}}
	_, err = c.Add("Skill", "procedure", "", document, map[string][]byte{"../../.state/private.md": []byte("private material")}, false)
	if err == nil {
		t.Fatal("Skill created a file in private operational state")
	}
	after, err := os.ReadFile(c.File)
	if err != nil || string(before) != string(after) {
		t.Fatal("rejected creation changed registry", err)
	}
	if _, err := os.Stat(filepath.Join(c.RootPath(), ".state", "private.md")); !os.IsNotExist(err) {
		t.Fatal("rejected creation wrote private support", err)
	}
}
