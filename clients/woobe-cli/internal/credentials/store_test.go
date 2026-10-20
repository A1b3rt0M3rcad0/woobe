package credentials

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestPrivateReferences(t *testing.T) {
	s := Store{Dir: t.TempDir()}
	for _, n := range []string{"../other", "/absolute", "a/b", ""} {
		if s.Put(n, "secret") == nil {
			t.Fatal(n)
		}
	}
	if e := s.Put("fixture", "secret"); e != nil {
		t.Fatal(e)
	}
	info, e := os.Stat(filepath.Join(s.Dir, "fixture.json"))
	if !nativeStore && (e != nil || info.Mode().Perm() != 0600) {
		t.Fatal(info, e)
	}
	t.Cleanup(func() { _ = s.Remove("fixture") })
	v, e := s.Get("fixture")
	if e != nil || v != "secret" {
		t.Fatal(v, e)
	}
}
func TestCredentialBounds(t *testing.T) {
	s := Store{Dir: t.TempDir()}
	for _, value := range []string{"", "  ", strings.Repeat("x", 65537)} {
		if s.Put("bad", value) == nil {
			t.Fatal("accepted invalid credential")
		}
		if e := os.WriteFile(filepath.Join(s.Dir, "bad.json"), []byte(value), 0600); e != nil {
			t.Fatal(e)
		}
		if _, e := s.Get("bad"); e == nil {
			t.Fatal("read invalid credential")
		}
	}
}
func TestSymlinkAndPublicFilesRejected(t *testing.T) {
	dir := t.TempDir()
	s := Store{Dir: dir}
	p := filepath.Join(dir, "public.json")
	_ = os.WriteFile(p, []byte("secret"), 0644)
	_ = os.Chmod(p, 0644)
	if _, e := s.Get("public"); e == nil {
		t.Fatal("public credential accepted")
	}
	_ = os.Symlink(p, filepath.Join(dir, "link.json"))
	if _, e := s.Get("link"); e == nil {
		t.Fatal("symlink accepted")
	}
}
