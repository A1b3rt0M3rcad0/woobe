package devworkspace

import (
	"fmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"gopkg.in/yaml.v3"
	"regexp"
	"strings"
)

// A cloned Skill gets a new native namespace in its authoritative manifest.
// Copying only descriptor metadata would silently resolve the original Skill.
func cloneSkillManifest(document map[string]any, supports map[string][]byte, alias string) error {
	if len(alias) > 64 || !regexp.MustCompile(`^[a-z0-9]+(?:-[a-z0-9]+)*$`).MatchString(alias) {
		return fmt.Errorf("Skill clone alias must be a valid Skill name (lowercase letters, numbers, single hyphens; max 64)")
	}
	manifest, _ := packagefmt.Object(packagefmt.Object(document["spec"])["package"])["manifest"].(string)
	data := strings.ReplaceAll(strings.TrimPrefix(string(supports[manifest]), "\ufeff"), "\r\n", "\n")
	if !strings.HasPrefix(data, "---\n") {
		return fmt.Errorf("Skill manifest requires YAML frontmatter")
	}
	parts := strings.SplitN(strings.TrimPrefix(data, "---\n"), "\n---\n", 2)
	if len(parts) != 2 {
		return fmt.Errorf("Skill manifest requires Markdown instructions")
	}
	var metadata map[string]any
	if yaml.Unmarshal([]byte(parts[0]), &metadata) != nil || metadata == nil {
		return fmt.Errorf("Skill manifest has invalid frontmatter")
	}
	metadata["name"] = alias
	frontmatter, err := yaml.Marshal(metadata)
	if err != nil {
		return err
	}
	supports[manifest] = []byte("---\n" + string(frontmatter) + "---\n" + parts[1])
	return nil
}
