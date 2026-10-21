package cli

import (
	"bufio"
	"context"
	"fmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"golang.org/x/term"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"unicode"
)

var packageUUID = regexp.MustCompile(`^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$`)

func packageDestination(path string) (string, error) {
	absolute, err := filepath.Abs(path)
	if err != nil {
		return "", output.New(2, "Invalid export destination")
	}
	if _, err = os.Lstat(absolute); err == nil {
		return "", output.New(2, "Export destination already exists; choose --destination NEW_DIRECTORY")
	} else if !os.IsNotExist(err) {
		return "", output.New(2, "Export destination is unavailable")
	}
	parent, err := os.Stat(filepath.Dir(absolute))
	if err != nil || !parent.IsDir() {
		return "", output.New(2, "Export destination parent must exist")
	}
	return absolute, nil
}

func packageSlug(name string) string {
	var b strings.Builder
	separator := false
	for _, c := range strings.ToLower(name) {
		if unicode.IsLetter(c) || unicode.IsDigit(c) {
			if separator && b.Len() > 0 {
				b.WriteByte('-')
			}
			separator = false
			b.WriteRune(c)
		} else {
			separator = true
		}
		if b.Len() >= 100 {
			break
		}
	}
	slug := b.String()
	if slug == "" {
		slug = "woobe-package"
	}
	switch strings.ToUpper(slug) {
	case "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9":
		slug = "package-" + slug
	}
	return slug
}

func packageList(value any) ([]any, bool) {
	for depth := 0; depth < 5; depth++ {
		if rows, ok := value.([]any); ok {
			return rows, true
		}
		obj, ok := value.(map[string]any)
		if !ok {
			return nil, false
		}
		if complete, exists := obj["complete"]; exists && complete == false {
			return nil, false
		}
		if obj["has_next"] == true || obj["next_cursor"] != nil && obj["next_cursor"] != "" {
			return nil, false
		}
		found := false
		for _, key := range []string{"data", "items", "agents", "networks"} {
			if next, ok := obj[key]; ok {
				value = next
				found = true
				break
			}
		}
		if !found {
			return nil, false
		}
	}
	return nil, false
}

func (a *App) packageTarget(ctx context.Context, client *packageapi.Client, kind, target string) (string, error) {
	if packageUUID.MatchString(target) {
		return target, nil
	}
	path := "/ai/agents"
	query := url.Values{"project_id": {client.ProjectID}}
	if kind == "network" {
		path = "/network/projects/" + url.PathEscape(client.ProjectID) + "/networks"
		query = nil
	}
	value, _, err := client.Control.Request(ctx, "GET", path, query, nil)
	if err != nil {
		return "", err
	}
	rows, complete := packageList(value)
	if !complete {
		return "", output.New(9, "Cannot resolve a name from an incomplete list; use a UUID from woobe "+kind+" list")
	}
	matches := []map[string]any{}
	for _, row := range rows {
		if obj, ok := row.(map[string]any); ok && obj["name"] == target {
			if id, ok := obj["id"].(string); ok && packageUUID.MatchString(id) {
				matches = append(matches, obj)
			}
		}
	}
	if len(matches) == 0 {
		return "", output.New(5, "Resource name not found in selected project; use woobe "+kind+" list or provide its UUID")
	}
	if len(matches) == 1 {
		return matches[0]["id"].(string), nil
	}
	ids := []string{}
	for _, row := range matches {
		ids = append(ids, row["id"].(string))
	}
	f, terminal := a.In.(*os.File)
	if a.NoInput || !terminal || !term.IsTerminal(int(f.Fd())) {
		return "", &output.Error{Code: 2, Message: "Ambiguous resource name; choose a UUID: " + strings.Join(ids, ", ")}
	}
	for i, row := range matches {
		fmt.Fprintf(a.Err, "%d. %q (%s)\n", i+1, target, row["id"])
	}
	fmt.Fprint(a.Err, "Select resource (number or UUID): ")
	line, err := bufio.NewReader(io.LimitReader(a.In, 4096)).ReadString('\n')
	if err != nil {
		return "", output.New(2, "Resource selection cancelled")
	}
	choice := strings.TrimSpace(line)
	if index, err := strconv.Atoi(choice); err == nil && index >= 1 && index <= len(ids) {
		return ids[index-1], nil
	}
	for _, id := range ids {
		if choice == id {
			return id, nil
		}
	}
	return "", output.New(2, "Choose a listed resource number or UUID")
}
