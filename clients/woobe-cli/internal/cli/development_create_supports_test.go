package cli

import (
	"os"
	"path/filepath"
	"testing"
)

func TestPackageLocalCreateCopiesDeclaredSkillSupportFiles(t *testing.T) {
	t.Chdir(t.TempDir())
	if code, result := invoke(t, []string{"init"}, ""); code != 0 {
		t.Fatal(code, result)
	}
	if err := os.MkdirAll("author/references", 0700); err != nil {
		t.Fatal(err)
	}
	files := map[string]string{
		"author/skill.yaml":              "format: woobe-package\nschema_version: '1.0'\nkind: Skill\nmetadata: {key: original, name: Procedure}\nspec:\n  version: '1.0.0'\n  package:\n    manifest: SKILL.md\n    resources: [references/checklist.md]\n",
		"author/SKILL.md":                "---\nname: procedure\ndescription: Follow the procedure\n---\nHelp customers.\n",
		"author/references/checklist.md": "Check the customer's request.\n",
	}
	for path, body := range files {
		if err := os.WriteFile(path, []byte(body), 0600); err != nil {
			t.Fatal(err)
		}
	}
	if code, result := invoke(t, []string{"resources", "create", "skill", "procedure", "--file", "author/skill.yaml"}, ""); code != 0 {
		t.Fatal(code, result)
	}
	for _, relative := range []string{"SKILL.md", "references/checklist.md"} {
		data, err := os.ReadFile(filepath.Join(".woobe", "skills", "procedure", relative))
		if err != nil || string(data) != files["author/"+relative] {
			t.Fatal("support file not copied", relative, err)
		}
	}
}
