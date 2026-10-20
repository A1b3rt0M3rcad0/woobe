package credentials

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

var valid = regexp.MustCompile(`^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,100}$`)

type Store struct{ Dir string }

func (s Store) path(name string) (string, error) {
	if !valid.MatchString(name) {
		return "", output.New(2, "invalid credential reference")
	}
	return filepath.Join(s.Dir, name+".json"), nil
}
func (s Store) Get(name string) (string, error) {
	p, e := s.path(name)
	if e != nil {
		return "", e
	}
	if nativeStore {
		return s.nativeGet(name)
	}
	info, e := os.Lstat(p)
	if e != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 {
		return "", output.New(3, "credential file must be regular and private")
	}
	f, e := os.Open(p)
	if e != nil {
		return "", output.New(3, "credential unavailable")
	}
	defer f.Close()
	opened, e := f.Stat()
	if e != nil || !os.SameFile(info, opened) || !opened.Mode().IsRegular() || opened.Mode().Perm()&0077 != 0 || opened.Size() > 64<<10 {
		return "", output.New(3, "credential file must be bounded regular and private")
	}
	b, e := io.ReadAll(io.LimitReader(f, 64<<10+1))
	if e != nil {
		return "", output.New(3, "credential unavailable")
	}
	v := strings.TrimSpace(string(b))
	if len(b) > 64<<10 || v == "" {
		return "", output.New(3, "credential unavailable")
	}
	return v, nil
}
func (s Store) Put(name, value string) error {
	p, e := s.path(name)
	if e != nil {
		return e
	}
	if strings.TrimSpace(value) == "" || len(value) > 64<<10 {
		return output.New(2, "credential must contain 1 to 65536 bytes")
	}
	if nativeStore {
		return s.nativePut(name, value)
	}
	return config.AtomicWrite(p, []byte(value), 0600)
}
func (s Store) Remove(name string) error {
	p, e := s.path(name)
	if e != nil {
		return e
	}
	if nativeStore {
		return s.nativeRemove(name)
	}
	err := os.Remove(p)
	if os.IsNotExist(err) {
		return nil
	}
	return err
}
func (s Store) List() ([]string, error) {
	if nativeStore {
		return s.nativeList()
	}
	es, e := os.ReadDir(s.Dir)
	if os.IsNotExist(e) {
		return []string{}, nil
	}
	if e != nil {
		return nil, e
	}
	out := []string{}
	for _, v := range es {
		if !v.IsDir() && strings.HasSuffix(v.Name(), ".json") {
			out = append(out, strings.TrimSuffix(v.Name(), ".json"))
		}
	}
	return out, nil
}
