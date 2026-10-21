package devworkspace

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"gopkg.in/yaml.v3"
)

func writeConfig(t *testing.T, c *Config) {
	t.Helper()
	data, err := yaml.Marshal(c)
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(c.File, data, 0600); err != nil {
		t.Fatal(err)
	}
}
func TestConfigDiscoveryRootAndIsolation(t *testing.T) {
	parent := t.TempDir()
	repository := filepath.Join(parent, "repo")
	nested := filepath.Join(repository, "sub", "dir")
	os.MkdirAll(nested, 0700)
	os.MkdirAll(filepath.Join(repository, ".git"), 0700)
	outer, err := Create(parent, "outside", "other")
	if err != nil {
		t.Fatal(err)
	}
	if path, err := Discover(nested, "", false); err != nil || path != "" {
		t.Fatal("crossed Git boundary", path, err)
	}
	c, err := Create(repository, "artifacts", "local")
	if err != nil {
		t.Fatal(err)
	}
	path, err := Discover(nested, "", false)
	if err != nil || path != c.File {
		t.Fatal(path, err)
	}
	loaded, err := Load(path)
	if err != nil || loaded.RootPath() != filepath.Join(repository, "artifacts") {
		t.Fatal(loaded, err)
	}
	if path, err := Discover(nested, outer.File, false); err != nil || path != outer.File {
		t.Fatal(path, err)
	}
	if path, err := Discover(nested, "", true); err != nil || path != "" {
		t.Fatal(path, err)
	}
	if _, err := Discover(nested, c.File, true); err == nil {
		t.Fatal("conflicting flags accepted")
	}
	if _, err := Create(repository, ".woobe", "local"); err == nil {
		t.Fatal("overwrote config")
	}
}

func TestRegistryRefusesAmbiguousOrUnsafeIdentity(t *testing.T) {
	for _, change := range []string{"duplicate uid", "duplicate alias", "duplicate key", "duplicate path", "traversal", "windows path", "unknown kind"} {
		t.Run(change, func(t *testing.T) {
			c, _ := Create(t.TempDir(), ".woobe", "")
			id, _ := NewID()
			id2, _ := NewID()
			c.Resources = []Resource{{UID: id, Kind: "Agent", Key: "a", Alias: "a", Path: "agents/a"}, {UID: id2, Kind: "Agent", Key: "b", Alias: "b", Path: "agents/b"}}
			switch change {
			case "duplicate uid":
				c.Resources[1].UID = id
			case "duplicate alias":
				c.Resources[1].Alias = "a"
			case "duplicate key":
				c.Resources[1].Key = "a"
			case "duplicate path":
				c.Resources[1].Path = "AGENTS/A"
			case "traversal":
				c.Resources[1].Path = "../b"
			case "windows path":
				c.Resources[1].Path = `C:\bad`
			case "unknown kind":
				c.Resources[1].Kind = "Script"
			}
			if err := c.Validate(); err == nil {
				t.Fatal("unsafe registry accepted")
			}
		})
	}
	for _, input := range []string{"schema_version: 1\nschema_version: 2", "schema_version: 1\nsecret: do-not-store", "x: &a 1\ny: *a"} {
		path := filepath.Join(t.TempDir(), Filename)
		os.WriteFile(path, []byte(input), 0600)
		if _, err := Load(path); err == nil {
			t.Fatal("invalid config accepted")
		}
	}
}

func graphFixture(t *testing.T) *Config {
	t.Helper()
	c, _ := Create(t.TempDir(), ".woobe", "")
	os.MkdirAll(c.RootPath(), 0700)
	documents := []struct{ kind, key, body string }{
		{"Provider", "provider", "provider: openai\n  credential_ref: primary"},
		{"Model", "chat", "provider_ref: provider\n  model: chat"},
		{"Model", "embedding", "provider_ref: provider\n  model: embedding"},
		{"Knowledge", "knowledge", "embedding:\n    model_ref: embedding"},
		{"Agent", "agent", "model:\n    primary:\n      ref: chat\n  knowledge:\n    source:\n      ref: knowledge"},
		{"Network", "network", "nodes:\n    - key: first\n      agent_ref: agent\n    - key: second\n      agent_ref: agent"},
	}
	for _, d := range documents {
		id, _ := NewID()
		path := KindDirectory(d.kind) + "/" + d.key
		r := Resource{UID: id, Kind: d.kind, Key: d.key, Alias: d.key, Path: path}
		c.Resources = append(c.Resources, r)
		os.MkdirAll(filepath.Join(c.RootPath(), path), 0700)
		os.WriteFile(filepath.Join(c.RootPath(), descriptor(r)), []byte("kind: "+d.kind+"\nmetadata:\n  key: "+d.key+"\nspec:\n  "+d.body+"\n"), 0600)
	}
	writeConfig(t, c)
	return c
}

func TestGraphIncludesProviderAndEmbeddingConsumersOnce(t *testing.T) {
	c := graphFixture(t)
	g, err := LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	closure, err := g.Closure("network")
	if err != nil || len(closure) != 6 {
		t.Fatal(len(closure), err)
	}
	consumers := g.UsedBy("provider")
	if len(consumers) != 5 {
		t.Fatal(consumers)
	}
	resource, err := c.Resolve("agent", "@agent")
	if err != nil || resource.Key != "agent" {
		t.Fatal(resource, err)
	}
	if _, err := c.Resolve("agent", "network"); err == nil {
		t.Fatal("cross-kind resolution")
	}
}

func TestGraphRejectsMissingAndWrongKindDependencies(t *testing.T) {
	c := graphFixture(t)
	path := filepath.Join(c.RootPath(), descriptor(c.Resources[1]))
	raw, _ := os.ReadFile(path)
	os.WriteFile(path, []byte(strings.ReplaceAll(string(raw), "provider_ref: provider", "provider_ref: missing")), 0600)
	if _, err := LoadGraph(c); err == nil {
		t.Fatal("missing provider accepted")
	}
	os.WriteFile(path, []byte(strings.ReplaceAll(string(raw), "provider_ref: provider", "provider_ref: embedding")), 0600)
	if _, err := LoadGraph(c); err == nil {
		t.Fatal("Model accepted as Provider")
	}
}

func TestProviderFilesRejectSecretsAndCredentialURLs(t *testing.T) {
	for _, field := range []string{"api_key: private", "metadata:\n    token: private", "base_url: https://user:secret@example.com", "base_url: https://example.com?token=private"} {
		t.Run(field, func(t *testing.T) {
			c := graphFixture(t)
			path := filepath.Join(c.RootPath(), descriptor(c.Resources[0]))
			raw, _ := os.ReadFile(path)
			os.WriteFile(path, append(raw, []byte("  "+field+"\n")...), 0600)
			if _, err := LoadGraph(c); err == nil {
				t.Fatal("credential-bearing Provider accepted")
			}
		})
	}
}
