package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"strings"
	"unicode"
	"unicode/utf8"
)

func resourceID(id string) error {
	if id == "" || id == "." || id == ".." || !utf8.ValidString(id) || strings.ContainsAny(id, "/\\?#%") || strings.IndexFunc(id, func(r rune) bool { return unicode.IsSpace(r) || unicode.IsControl(r) }) >= 0 {
		return output.New(2, "resource ID must be an unambiguous single path segment")
	}
	return nil
}
