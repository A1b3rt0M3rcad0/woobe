package config

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func loadText(t *testing.T, s string) (Config, error) {
	t.Helper()
	p := filepath.Join(t.TempDir(), "config.json")
	if e := os.WriteFile(p, []byte(s), 0600); e != nil {
		t.Fatal(e)
	}
	return Load(p)
}
func TestRejectAmbiguousConfig(t *testing.T) {
	for _, s := range []string{`{"version":1,"version":1}`, `{"version":1,"contexts":{"a":{"api_url":"http://localhost","api_url":"http://other"}}}`, `{"version":1} {}`} {
		if _, e := loadText(t, s); e == nil {
			t.Fatal(s)
		}
	}
}

func TestConfigSizeLimit(t *testing.T) {
	if _, e := loadText(t, strings.Repeat(" ", 1<<20+1)); e == nil {
		t.Fatal("oversize accepted")
	}
}

func TestUnknownConfigFields(t *testing.T) {
	for _, s := range []string{`{"version":1,"credentail":"wrong"}`, `{"version":1,"contexts":{"a":{"api_url":"http://localhost","project":"wrong"}}}`} {
		if _, e := loadText(t, s); e == nil {
			t.Fatal(s)
		}
	}
}

func TestSaveInvalidVersionPreservesConfig(t *testing.T) {
	p := filepath.Join(t.TempDir(), "c.json")
	c := Config{Version: 1}
	if e := Save(p, c); e != nil {
		t.Fatal(e)
	}
	before, _ := os.ReadFile(p)
	c.Version = 2
	if Save(p, c) == nil {
		t.Fatal("version")
	}
	after, _ := os.ReadFile(p)
	if string(before) != string(after) {
		t.Fatal("config replaced")
	}
}

func TestDanglingActiveContext(t *testing.T) {
	if _, e := loadText(t, `{"version":1,"current":"missing","contexts":{}}`); e == nil {
		t.Fatal("dangling current")
	}
	c, e := Load(filepath.Join(t.TempDir(), "missing"))
	if e != nil || c.Version != 1 || c.Contexts == nil {
		t.Fatal(c, e)
	}
}

func TestContextNames(t *testing.T) {
	for _, name := range []string{"", "../dev", "has space"} {
		if Validate(Config{Version: 1, Contexts: map[string]Context{name: {APIURL: "http://localhost"}}}) == nil {
			t.Fatal(name)
		}
	}
}

func TestContextOrigins(t *testing.T) {
	for _, u := range []string{"", "file:///tmp", "https://user:secret@host", "https://host/?q=1", "https://host/#x"} {
		if Validate(Config{Version: 1, Contexts: map[string]Context{"dev": {APIURL: u}}}) == nil {
			t.Fatal(u)
		}
	}
}
