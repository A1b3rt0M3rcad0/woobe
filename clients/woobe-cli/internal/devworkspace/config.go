// Package devworkspace owns optional repository-local authoring configuration.
// Ordinary control-plane and runtime commands never load this configuration.
package devworkspace

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/requestinput"
	"gopkg.in/yaml.v3"
)

const Filename = ".woobe-config"

type Defaults struct {
	PullEnvironment string `json:"pull_environment" yaml:"pull_environment"`
}
type Resource struct {
	SnapshotID string `json:"snapshot_id,omitempty" yaml:"snapshot_id,omitempty"`
	Frozen     bool   `json:"frozen,omitempty" yaml:"frozen,omitempty"`
	UID        string `json:"uid" yaml:"uid"`
	Kind       string `json:"kind" yaml:"kind"`
	Key        string `json:"key" yaml:"key"`
	Alias      string `json:"alias" yaml:"alias"`
	Path       string `json:"path" yaml:"path"`
}
type Config struct {
	SchemaVersion int        `json:"schema_version" yaml:"schema_version"`
	RegistryID    string     `json:"registry_id" yaml:"registry_id"`
	Context       string     `json:"context" yaml:"context"`
	Root          string     `json:"root" yaml:"root"`
	Defaults      Defaults   `json:"defaults" yaml:"defaults"`
	Resources     []Resource `json:"resources" yaml:"resources"`
	File          string     `json:"-" yaml:"-"`
}

var uuidPattern = regexp.MustCompile(`^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$`)
var keyPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$`)
var kinds = map[string]string{"Agent": "agents", "Network": "networks", "Provider": "providers", "Model": "models", "Tool": "tools", "Skill": "skills", "Knowledge": "knowledge", "Prompt": "prompts", "Contract": "contracts", "Surface": "surfaces"}

func NewID() (string, error) {
	var id [16]byte
	if _, err := rand.Read(id[:]); err != nil {
		return "", err
	}
	id[6] = (id[6] & 15) | 64
	id[8] = (id[8] & 63) | 128
	encoded := hex.EncodeToString(id[:])
	return encoded[:8] + "-" + encoded[8:12] + "-" + encoded[12:16] + "-" + encoded[16:20] + "-" + encoded[20:], nil
}

func Discover(start, explicit string, disabled bool) (string, error) {
	if disabled {
		if explicit != "" {
			return "", fmt.Errorf("project-config conflicts with no-project-config")
		}
		return "", nil
	}
	if explicit != "" {
		return filepath.Abs(explicit)
	}
	directory, err := filepath.Abs(start)
	if err != nil {
		return "", err
	}
	for {
		candidate := filepath.Join(directory, Filename)
		if _, err := os.Lstat(candidate); err == nil {
			return candidate, nil
		} else if !os.IsNotExist(err) {
			return "", err
		}
		if _, err := os.Lstat(filepath.Join(directory, ".git")); err == nil {
			return "", nil
		}
		parent := filepath.Dir(directory)
		if parent == directory {
			return "", nil
		}
		directory = parent
	}
}

func Load(file string) (*Config, error) {
	info, err := os.Lstat(file)
	if err != nil {
		return nil, err
	}
	if !info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 || info.Size() > 1<<20 {
		return nil, fmt.Errorf("project config must be a regular file below 1 MiB")
	}
	raw, err := os.ReadFile(file)
	if err != nil {
		return nil, err
	}
	data, err := requestinput.Decode(raw, file, "yaml")
	if err != nil {
		return nil, err
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	var config Config
	if err := decoder.Decode(&config); err != nil {
		return nil, fmt.Errorf("invalid project config fields")
	}
	config.File, err = filepath.Abs(file)
	if err != nil {
		return nil, err
	}
	if err := config.Validate(); err != nil {
		return nil, err
	}
	return &config, nil
}

func (c *Config) RootPath() string {
	if filepath.IsAbs(c.Root) {
		return filepath.Clean(c.Root)
	}
	return filepath.Join(filepath.Dir(c.File), c.Root)
}

func (c *Config) Validate() error {
	if c.SchemaVersion != 1 || !uuidPattern.MatchString(c.RegistryID) || strings.TrimSpace(c.Root) == "" {
		return fmt.Errorf("project config requires schema_version 1, registry_id UUID and root")
	}
	if c.Defaults.PullEnvironment == "" {
		c.Defaults.PullEnvironment = "draft"
	}
	if c.Defaults.PullEnvironment != "draft" && c.Defaults.PullEnvironment != "staging" && c.Defaults.PullEnvironment != "production" {
		return fmt.Errorf("default pull environment must be draft, staging or production; releases require explicit versions")
	}
	if len(c.Resources) > 1000 {
		return fmt.Errorf("project resource limit exceeded")
	}
	seen := map[string]bool{}
	for _, resource := range c.Resources {
		if resource.SnapshotID != "" && (!resource.Frozen || resource.Kind != "Agent" || !uuidPattern.MatchString(resource.SnapshotID)) {
			return fmt.Errorf("snapshot_id requires a frozen Agent and exact snapshot UUID")
		}
		if !uuidPattern.MatchString(resource.UID) || kinds[resource.Kind] == "" || !keyPattern.MatchString(resource.Key) || !keyPattern.MatchString(resource.Alias) {
			return fmt.Errorf("invalid resource identity, kind, key or alias")
		}
		if _, err := c.ResourcePath(resource); err != nil {
			return err
		}
		for _, key := range []string{"uid:" + strings.ToLower(resource.UID), "key:" + resource.Key, "alias:" + resource.Kind + ":" + resource.Alias, "path:" + strings.ToLower(filepath.Clean(resource.Path))} {
			if seen[key] {
				return fmt.Errorf("duplicate resource UID, key, alias or path")
			}
			seen[key] = true
		}
	}
	return nil
}

func (c *Config) ResourcePath(resource Resource) (string, error) {
	if filepath.IsAbs(resource.Path) || strings.Contains(resource.Path, "\\") {
		return "", fmt.Errorf("resource path must be relative to the configured root using forward slashes")
	}
	if err := validateAuthorPath(resource.Path); err != nil {
		return "", err
	}
	path := filepath.Join(c.RootPath(), filepath.FromSlash(resource.Path))
	relative, err := filepath.Rel(c.RootPath(), path)
	if err != nil || relative == "." || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		return "", fmt.Errorf("resource path escapes configured root")
	}
	return path, nil
}

func (c *Config) Resolve(kind, reference string) (*Resource, error) {
	var result *Resource
	for i := range c.Resources {
		r := &c.Resources[i]
		if kind != "" && !strings.EqualFold(r.Kind, kind) {
			continue
		}
		if strings.EqualFold(r.UID, reference) || r.Key == reference || "@"+r.Alias == reference || r.Path == reference {
			if result != nil {
				return nil, fmt.Errorf("resource reference is ambiguous")
			}
			result = r
		}
	}
	if result == nil {
		return nil, fmt.Errorf("resource is not registered; use a UUID and explicit path or register it with pull")
	}
	return result, nil
}

func Create(directory, root, context string) (*Config, error) {
	id, err := NewID()
	if err != nil {
		return nil, err
	}
	file, err := filepath.Abs(filepath.Join(directory, Filename))
	if err != nil {
		return nil, err
	}
	c := &Config{SchemaVersion: 1, RegistryID: id, Root: root, Context: context, Defaults: Defaults{PullEnvironment: "draft"}, Resources: []Resource{}, File: file}
	if err := c.Validate(); err != nil {
		return nil, err
	}
	data, err := yaml.Marshal(c)
	if err != nil {
		return nil, err
	}
	f, err := os.OpenFile(file, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return nil, fmt.Errorf("project config already exists or cannot be created")
	}
	if _, err = f.Write(data); err != nil {
		f.Close()
		return nil, err
	}
	if err = f.Close(); err != nil {
		return nil, err
	}
	return c, nil
}

func KindDirectory(kind string) string { return kinds[kind] }
