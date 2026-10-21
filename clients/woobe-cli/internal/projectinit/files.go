// Package projectinit prepares bounded, managed additions to project-owned files.
package projectinit

import (
	"bytes"
	"crypto/sha256"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"unicode/utf8"
)

const maxFile = 1 << 20
const marker = "woobe-cli:init:v1"

type File struct {
	Path          string
	Before, After []byte
	Exists        bool
	Mode          os.FileMode
}

// SafeDirectory rejects links and files in every existing ancestor, including junctions.
func SafeDirectory(path string) error {
	absolute, err := filepath.Abs(path)
	if err != nil {
		return err
	}
	for p := absolute; ; p = filepath.Dir(p) {
		info, e := os.Lstat(p)
		if e != nil && !os.IsNotExist(e) {
			return e
		}
		if e == nil && (!info.IsDir() || info.Mode()&os.ModeSymlink != 0) {
			return fmt.Errorf("setup directory must be a real directory: %s", p)
		}
		if p == filepath.Dir(p) {
			break
		}
	}
	return nil
}

func Read(path string) (File, error) {
	f := File{Path: path, Mode: 0644}
	if err := SafeDirectory(filepath.Dir(path)); err != nil {
		return f, err
	}
	info, err := os.Lstat(path)
	if os.IsNotExist(err) {
		return f, nil
	}
	if err != nil {
		return f, err
	}
	if !info.Mode().IsRegular() || info.Size() > maxFile {
		return f, fmt.Errorf("setup file must be a regular UTF-8 file below 1 MiB: %s", path)
	}
	handle, err := os.Open(path)
	if err != nil {
		return f, err
	}
	defer handle.Close()
	opened, err := handle.Stat()
	if err != nil {
		return f, err
	}
	if !os.SameFile(info, opened) || !opened.Mode().IsRegular() {
		return f, fmt.Errorf("setup file changed while reading: %s", path)
	}
	data, err := io.ReadAll(io.LimitReader(handle, maxFile+1))
	if err != nil {
		return f, err
	}
	if len(data) > maxFile || !utf8.Valid(data) || bytes.IndexByte(data, 0) >= 0 {
		return f, fmt.Errorf("setup file must be UTF-8 below 1 MiB: %s", path)
	}
	f.Before, f.Exists, f.Mode = data, true, info.Mode().Perm()
	return f, nil
}

func digest(s string) string {
	return fmt.Sprintf("%x", sha256.Sum256([]byte(strings.ReplaceAll(s, "\r\n", "\n"))))
}

var header = regexp.MustCompile(`^(?:<!-- |# )woobe-cli:init:v1 sha256=([a-f0-9]{64})(?: agents=([a-z,-]+))?(?: -->)?$`)

type block struct {
	start, end int
	agents     []string
}

func inspect(data []byte, comment string) (block, error) {
	s := string(data)
	b := block{start: -1}
	if !strings.Contains(s, "woobe-cli:init") {
		return b, nil
	}
	prefix := comment + " " + marker
	start := strings.Index(s, prefix)
	if start < 0 || start > 0 && s[start-1] != '\n' {
		return b, fmt.Errorf("invalid managed setup block")
	}
	lineEnd := strings.IndexByte(s[start:], '\n')
	if lineEnd < 0 {
		return b, fmt.Errorf("incomplete managed setup block")
	}
	lineEnd += start
	fields := header.FindStringSubmatch(strings.TrimSuffix(s[start:lineEnd], "\r"))
	if fields == nil {
		return b, fmt.Errorf("invalid managed setup header")
	}
	footer := comment + " /woobe-cli:init"
	if comment == "<!--" {
		footer += " -->"
	}
	bodyStart := lineEnd + 1
	end := strings.Index(s[bodyStart:], footer)
	if end < 0 {
		return b, fmt.Errorf("missing managed setup footer")
	}
	end += bodyStart
	if end > bodyStart && s[end-1] != '\n' {
		return b, fmt.Errorf("invalid managed setup footer")
	}
	if digest(s[bodyStart:end]) != fields[1] {
		return b, fmt.Errorf("managed Woobe instructions were edited; move custom notes outside the managed block before retrying")
	}
	stop := end + len(footer)
	if stop < len(s) && s[stop] == '\r' {
		stop++
	}
	if stop < len(s) && s[stop] == '\n' {
		stop++
	} else if stop < len(s) {
		return b, fmt.Errorf("invalid managed setup footer")
	}
	outside := s[:start] + s[stop:]
	if strings.Contains(outside, "woobe-cli:init") {
		return b, fmt.Errorf("duplicate managed setup blocks")
	}
	b.start, b.end = start, stop
	if fields[2] != "" {
		b.agents = strings.Split(fields[2], ",")
	}
	return b, nil
}

func Agents(f File) ([]string, error) { b, e := inspect(f.Before, "<!--"); return b.agents, e }

func Manage(f File, body, comment string, agents []string, last bool) (File, error) {
	b, err := inspect(f.Before, comment)
	if err != nil {
		return f, fmt.Errorf("%s: %w", f.Path, err)
	}
	newline := "\n"
	if bytes.Contains(f.Before, []byte("\r\n")) {
		newline = "\r\n"
	}
	body = strings.TrimRight(strings.ReplaceAll(body, "\r\n", "\n"), "\n") + "\n"
	h := comment + " " + marker + " sha256=" + digest(body)
	if len(agents) > 0 {
		sort.Strings(agents)
		h += " agents=" + strings.Join(agents, ",")
	}
	footer := comment + " /woobe-cli:init"
	if comment == "<!--" {
		h += " -->"
		footer += " -->"
	}
	generated := strings.ReplaceAll(h+"\n"+body+footer+"\n", "\n", newline)
	old := string(f.Before)
	if b.start >= 0 && !last {
		f.After = []byte(old[:b.start] + generated + old[b.end:])
		if len(f.After) > maxFile {
			return f, fmt.Errorf("setup file exceeds 1 MiB: %s", f.Path)
		}
		return f, nil
	}
	if b.start >= 0 {
		old = old[:b.start] + old[b.end:]
	}
	if old != "" && !strings.HasSuffix(old, "\n") {
		old += newline
	}
	f.After = []byte(old + generated)
	if len(f.After) > maxFile {
		return f, fmt.Errorf("setup file exceeds 1 MiB: %s", f.Path)
	}
	return f, nil
}

func (f File) Changed() bool { return !f.Exists || !bytes.Equal(f.Before, f.After) }
func (f File) Apply() error {
	if !f.Changed() {
		return nil
	}
	if err := SafeDirectory(filepath.Dir(f.Path)); err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(f.Path), 0755); err != nil {
		return err
	}
	current, err := Read(f.Path)
	if err != nil {
		return err
	}
	if current.Exists != f.Exists || !bytes.Equal(current.Before, f.Before) {
		return fmt.Errorf("setup file changed; rerun init after reviewing %s", f.Path)
	}
	staged, err := os.CreateTemp(filepath.Dir(f.Path), ".woobe-init-")
	if err != nil {
		return err
	}
	name := staged.Name()
	defer os.Remove(name)
	if err = staged.Chmod(f.Mode); err == nil {
		_, err = staged.Write(f.After)
	}
	if err == nil {
		err = staged.Sync()
	}
	closeErr := staged.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	// New files use exclusive creation, so a concurrent user file is never replaced.
	if !f.Exists {
		out, e := os.OpenFile(f.Path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, f.Mode)
		if e != nil {
			return e
		}
		_, e = out.Write(f.After)
		if e == nil {
			e = out.Sync()
		}
		ce := out.Close()
		if e != nil {
			return e
		}
		return ce
	}
	current, err = Read(f.Path)
	if err != nil {
		return err
	}
	if !bytes.Equal(current.Before, f.Before) {
		return fmt.Errorf("setup file changed; rerun init after reviewing %s", f.Path)
	}
	return os.Rename(name, f.Path)
}

// EscapeIgnore anchors a literal relative directory, even when names contain glob characters.
func EscapeIgnore(relative string) string {
	s := filepath.ToSlash(relative)
	replacer := strings.NewReplacer("\\", "\\\\", "*", "\\*", "?", "\\?", "[", "\\[", "]", "\\]", " ", "\\ ", "!", "\\!", "#", "\\#")
	return "/" + replacer.Replace(s) + "/"
}
