package cli

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/spf13/cobra"
)

func TestEveryCommandGroupRejectsUnresolvedArguments(t *testing.T) {
	app := New(strings.NewReader(""), nil, nil)
	var groups [][]string
	var walk func(*cobra.Command, []string)
	walk = func(cmd *cobra.Command, path []string) {
		if cmd.HasSubCommands() && !cmd.DisableFlagParsing && (cmd.Args != nil) {
			groups = append(groups, append([]string{}, path...))
		}
		for _, child := range cmd.Commands() {
			walk(child, append(append([]string{}, path...), child.Name()))
		}
	}
	walk(app.Root, nil)
	for _, path := range groups {
		for _, mode := range []string{"json", "compact"} {
			t.Run(strings.Join(path, "/")+"/"+mode, func(t *testing.T) {
				args := append(append([]string{}, path...), "nonexistent-audit-command", "--output", mode, "--no-input")
				code, text := outputInvoke(t, args)
				var result map[string]any
				if code != 2 || json.Unmarshal([]byte(text), &result) != nil || result["error"] == nil {
					t.Fatal(code, text)
				}
				if mode == "json" && result["success"] != false {
					t.Fatal(text)
				}
			})
		}
	}
	for _, path := range [][]string{{"project", "knowledge"}, {"project", "knowledge", "--help"}, {"version", "--help"}} {
		if code, text := outputInvoke(t, path); code != 0 || !strings.Contains(text, "Usage:") {
			t.Fatal(code, text)
		}
	}
	if code, text := outputInvoke(t, []string{"version", "extra", "--output", "json"}); code != 2 {
		t.Fatal(code, text)
	}
}
