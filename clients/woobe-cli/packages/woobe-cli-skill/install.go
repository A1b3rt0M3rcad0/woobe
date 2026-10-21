// Package assistantskill installs the same portable payload shipped by npm.
package assistantskill

import (
	"crypto/sha256"
	"embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

//go:embed skills/woobe-cli
var payload embed.FS

const marker = ".woobe-skill-install.json"
const Package = "woobe-cli-skill"

var renamePath = os.Rename

type Layout struct {
	Project string `json:"project"`
	User    string `json:"user"`
}

var Presets = map[string]Layout{
	"codex": {".agents/skills", ".agents/skills"}, "codex-legacy": {".codex/skills", ".codex/skills"},
	"claude": {".claude/skills", ".claude/skills"}, "copilot": {".github/skills", ".copilot/skills"},
	"cursor": {".cursor/skills", ".cursor/skills"}, "agents": {".agents/skills", ".agents/skills"},
}

type Options struct {
	Agents                                   []string
	Scope, ProjectDir, Path, Version, Commit string
	DryRun                                   bool
}
type Installation struct {
	Target  string   `json:"target"`
	Status  string   `json:"status"`
	Version string   `json:"version,omitempty"`
	Changed []string `json:"changed,omitempty"`
	Extra   []string `json:"extra,omitempty"`
}
type Result struct {
	Action        string         `json:"action"`
	Executed      bool           `json:"executed"`
	Package       string         `json:"package"`
	Version       string         `json:"version"`
	Installations []Installation `json:"installations"`
}
type receipt struct {
	Schema  int               `json:"schema_version"`
	Package string            `json:"package"`
	Version string            `json:"version"`
	Commit  string            `json:"source_commit"`
	Files   map[string]string `json:"files"`
}

func hash(data []byte) string { digest := sha256.Sum256(data); return hex.EncodeToString(digest[:]) }
func Payload() (map[string][]byte, error) {
	result := map[string][]byte{}
	err := fs.WalkDir(payload, "skills/woobe-cli", func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if entry.IsDir() {
			return nil
		}
		data, err := payload.ReadFile(path)
		if err != nil {
			return err
		}
		result[strings.TrimPrefix(path, "skills/woobe-cli/")] = data
		return nil
	})
	return result, err
}
func Targets(o Options) ([]string, error) {
	if o.Scope != "" && o.Scope != "project" && o.Scope != "user" {
		return nil, errors.New("--scope must be project or user")
	}
	if o.Path != "" && (len(o.Agents) > 0 || o.Scope != "" || o.ProjectDir != "") {
		return nil, errors.New("--path cannot be combined with --agent, --scope or --project-dir")
	}
	if o.Scope == "user" && o.ProjectDir != "" {
		return nil, errors.New("--project-dir cannot be used with user scope")
	}
	cwd, err := os.Getwd()
	if err != nil {
		return nil, err
	}
	cwd, err = filepath.EvalSymlinks(cwd)
	if err != nil {
		return nil, err
	}
	if o.Path != "" {
		root := o.Path
		if !filepath.IsAbs(root) {
			root = filepath.Join(cwd, root)
		}
		return []string{filepath.Join(root, "woobe-cli")}, nil
	}
	root := cwd
	if o.Scope == "user" {
		root, err = os.UserHomeDir()
	} else if o.ProjectDir != "" {
		root = o.ProjectDir
		if !filepath.IsAbs(root) {
			root = filepath.Join(cwd, root)
		}
	}
	if err != nil {
		return nil, err
	}
	root, err = filepath.EvalSymlinks(root)
	if err != nil {
		return nil, err
	}
	agents := o.Agents
	if len(agents) == 0 {
		agents = []string{"codex"}
	}
	seen := map[string]bool{}
	result := []string{}
	for _, agent := range agents {
		layout, ok := Presets[agent]
		if !ok {
			return nil, fmt.Errorf("unknown agent %q; see woobe skills agents", agent)
		}
		base := filepath.Join(root, filepath.FromSlash(layout.Project))
		if o.Scope == "user" {
			base = filepath.Join(root, filepath.FromSlash(layout.User))
			if agent == "codex-legacy" && os.Getenv("CODEX_HOME") != "" {
				base = filepath.Join(os.Getenv("CODEX_HOME"), "skills")
			}
		}
		target, err := filepath.Abs(filepath.Join(base, "woobe-cli"))
		if err != nil {
			return nil, err
		}
		key := target
		if !seen[key] {
			result = append(result, target)
			seen[key] = true
		}
	}
	return result, nil
}
func safeParents(target string) error {
	target, err := filepath.Abs(target)
	if err != nil {
		return err
	}
	for current := target; ; current = filepath.Dir(current) {
		info, err := os.Lstat(current)
		if err == nil && (!info.IsDir() || info.Mode()&os.ModeSymlink != 0) {
			return fmt.Errorf("installation directory must be a real directory: %s", current)
		}
		if err != nil && !errors.Is(err, os.ErrNotExist) {
			return err
		}
		if current == filepath.Dir(current) {
			break
		}
	}
	return nil
}
func inventory(root string) (map[string][]byte, error) {
	result := map[string][]byte{}
	count := 0
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		count++
		if count > 256 {
			return errors.New("skill directory entry count exceeds 256")
		}
		if entry.IsDir() {
			return nil
		}
		info, err := os.Lstat(path)
		if err != nil {
			return err
		}
		if !info.Mode().IsRegular() || info.Size() > 1<<20 {
			return fmt.Errorf("unsafe or oversized skill file: %s", path)
		}
		stream, err := os.Open(path)
		if err != nil {
			return err
		}
		defer stream.Close()
		opened, err := stream.Stat()
		if err != nil {
			return err
		}
		if !os.SameFile(info, opened) || !opened.Mode().IsRegular() || opened.Size() > 1<<20 || !singleLink(stream, opened) {
			return fmt.Errorf("unsafe or linked skill file: %s", path)
		}
		data := make([]byte, opened.Size())
		n, err := stream.ReadAt(data, 0)
		if err != nil && n != len(data) {
			return err
		}
		relative, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		result[filepath.ToSlash(relative)] = data
		if len(result) > 64 {
			return errors.New("skill file count exceeds 64")
		}
		return nil
	})
	return result, err
}

var portable = regexp.MustCompile(`^[A-Za-z0-9_.-]+(/[A-Za-z0-9_.-]+)*$`)
var digestPattern = regexp.MustCompile(`^[a-f0-9]{64}$`)

func Inspect(target string) (Installation, error) {
	row := Installation{Target: target, Status: "absent"}
	if err := safeParents(target); err != nil {
		return row, err
	}
	if _, err := os.Lstat(target); errors.Is(err, os.ErrNotExist) {
		return row, nil
	} else if err != nil {
		return row, err
	}
	files, err := inventory(target)
	if err != nil {
		return row, err
	}
	data, ok := files[marker]
	if !ok {
		row.Status = "unmanaged"
		return row, nil
	}
	var recorded receipt
	if json.Unmarshal(data, &recorded) != nil || recorded.Schema != 1 || recorded.Package != Package || recorded.Version == "" || recorded.Files["SKILL.md"] == "" || len(recorded.Files) > 64 {
		return row, fmt.Errorf("invalid installation receipt: %s", target)
	}
	for name, digest := range recorded.Files {
		if !portable.MatchString(name) || !digestPattern.MatchString(digest) {
			return row, errors.New("invalid receipt inventory")
		}
		for _, part := range strings.Split(name, "/") {
			if part == "." || part == ".." {
				return row, errors.New("invalid receipt inventory")
			}
		}
		if data, ok := files[name]; !ok || hash(data) != digest {
			row.Changed = append(row.Changed, name)
		}
	}
	for name := range files {
		if name != marker && recorded.Files[name] == "" {
			row.Extra = append(row.Extra, name)
		}
	}
	sort.Strings(row.Changed)
	sort.Strings(row.Extra)
	row.Version = recorded.Version
	row.Status = "managed"
	if len(row.Changed)+len(row.Extra) > 0 {
		row.Status = "modified"
	}
	return row, nil
}
func preflight(action string, targets []string) ([]Installation, error) {
	rows := []Installation{}
	for _, target := range targets {
		row, err := Inspect(target)
		if err != nil {
			return nil, err
		}
		if action != "status" && (row.Status == "unmanaged" || row.Status == "modified") {
			return nil, fmt.Errorf("refusing to %s %s skill at %s; preserve or move your local files before retrying", action, row.Status, target)
		}
		rows = append(rows, row)
	}
	return rows, nil
}

type change struct {
	target, stage, backup string
	installed             bool
}

func Run(action string, o Options) (result Result, err error) {
	if action != "install" && action != "status" && action != "uninstall" {
		return result, errors.New("unknown skill action")
	}
	targets, err := Targets(o)
	if err != nil {
		return result, err
	}
	rows, err := preflight(action, targets)
	if err != nil {
		return result, err
	}
	result = Result{Action: action, Package: Package, Version: o.Version, Installations: rows}
	if action == "status" || o.DryRun {
		return result, nil
	}
	locks := []string{}
	changes := []change{}
	defer func() {
		for _, lock := range locks {
			if e := os.Remove(lock); e != nil {
				err = errors.Join(err, e)
			}
		}
	}()
	for _, row := range rows {
		if action == "uninstall" && row.Status == "absent" {
			continue
		}
		parent := filepath.Dir(row.Target)
		if err = safeParents(parent); err != nil {
			return result, err
		}
		if err = os.MkdirAll(parent, 0755); err != nil {
			return result, err
		}
		lock := filepath.Join(parent, ".woobe-cli.install.lock")
		handle, e := os.OpenFile(lock, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
		if e != nil {
			return result, e
		}
		locks = append(locks, lock)
		if err = handle.Close(); err != nil {
			return result, err
		}
	}
	rows, err = preflight(action, targets)
	if err != nil {
		return result, err
	}
	data, err := Payload()
	if err != nil {
		return result, err
	}
	hashes := map[string]string{}
	for name, bytes := range data {
		hashes[name] = hash(bytes)
	}
	defer func() {
		if err == nil {
			return
		}
		for i := len(changes) - 1; i >= 0; i-- {
			c := changes[i]
			if c.installed {
				current, e := Inspect(c.target)
				if e != nil || current.Status != "managed" {
					err = fmt.Errorf("rollback preserved changed installation at %s; original backup: %s; original error: %w", c.target, c.backup, err)
					return
				}
				if e = os.RemoveAll(c.target); e != nil {
					err = errors.Join(err, e)
					return
				}
			}
			if c.backup != "" {
				if e := renamePath(c.backup, c.target); e != nil {
					err = errors.Join(err, e)
					return
				}
			}
			if e := os.RemoveAll(c.stage); e != nil {
				err = errors.Join(err, e)
			}
		}
	}()
	for _, row := range rows {
		if action == "uninstall" && row.Status == "absent" {
			continue
		}
		stage, e := os.MkdirTemp(filepath.Dir(row.Target), ".woobe-cli-stage-")
		if e != nil {
			return result, e
		}
		changes = append(changes, change{target: row.Target, stage: stage})
		c := &changes[len(changes)-1]
		if action == "install" {
			for relative, bytes := range data {
				file := filepath.Join(stage, filepath.FromSlash(relative))
				if err = os.MkdirAll(filepath.Dir(file), 0755); err != nil {
					return result, err
				}
				if err = os.WriteFile(file, bytes, 0644); err != nil {
					return result, err
				}
			}
			receiptBytes, e := json.MarshalIndent(receipt{1, Package, o.Version, o.Commit, hashes}, "", "  ")
			if e != nil {
				return result, e
			}
			if err = os.WriteFile(filepath.Join(stage, marker), append(receiptBytes, '\n'), 0644); err != nil {
				return result, err
			}
		}
		current, e := Inspect(row.Target)
		if e != nil {
			return result, e
		}
		if current.Status != row.Status || current.Version != row.Version {
			return result, fmt.Errorf("skill changed during installation: %s", row.Target)
		}
		if row.Status != "absent" {
			backup := stage + "-previous"
			if err = renamePath(row.Target, backup); err != nil {
				return result, err
			}
			c.backup = backup
		}
		if action == "install" {
			if err = renamePath(stage, row.Target); err != nil {
				return result, err
			}
			c.installed = true
		}
	}
	// Swaps committed. Cleanup failure must not trigger destructive rollback.
	committed := changes
	changes = nil
	for _, c := range committed {
		if c.backup != "" {
			if err = os.RemoveAll(c.backup); err != nil {
				return result, err
			}
		}
		if err = os.RemoveAll(c.stage); err != nil {
			return result, err
		}
	}
	result.Executed = true
	for i := range result.Installations {
		result.Installations[i].Status = "absent"
		result.Installations[i].Version = ""
		if action == "install" {
			result.Installations[i].Status = "installed"
		}
	}
	return result, nil
}
