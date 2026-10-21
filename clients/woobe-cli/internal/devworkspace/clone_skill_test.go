package devworkspace

import (
	"strings"
	"testing"
)

func TestSkillCloneRewritesNativeNamespaceAndRetainsInstructions(t *testing.T) {
	document := map[string]any{"spec": map[string]any{"package": map[string]any{"manifest": "SKILL.md"}}}
	original := "---\nname: original\ndescription: Support customers\n---\nFollow the procedure.\n"
	supports := map[string][]byte{"SKILL.md": []byte(original), "references/checklist.md": []byte("Keep this")}
	if err := cloneSkillManifest(document, supports, "new-skill"); err != nil {
		t.Fatal(err)
	}
	text := string(supports["SKILL.md"])
	if !strings.Contains(text, "name: new-skill") || !strings.HasSuffix(text, "Follow the procedure.\n") || string(supports["references/checklist.md"]) != "Keep this" {
		t.Fatal(text)
	}
	if err := cloneSkillManifest(document, supports, "invalid_name"); err == nil {
		t.Fatal("invalid native Skill name accepted")
	}
}
