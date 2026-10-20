package devworkspace

import (
	"bytes"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"gopkg.in/yaml.v3"
)

type Binding struct {
	Identifiers     map[string]string `json:"identifiers,omitempty"`
	Supports        map[string]string `json:"supports,omitempty"`
	OwnerAgentID    string            `json:"owner_agent_id,omitempty"`
	ExportID        string            `json:"export_id,omitempty"`
	SourceComponent string            `json:"source_component,omitempty"`
	ResourceID      string            `json:"resource_id"`
	Revision        any               `json:"revision"`
	SourceKind      string            `json:"source_kind,omitempty"`
	SnapshotID      string            `json:"snapshot_id,omitempty"`
	Base            map[string]any    `json:"base"`
}
type State struct {
	Pending      map[string]string  `json:"pending,omitempty"`
	Format       string             `json:"format"`
	RegistryID   string             `json:"registry_id"`
	API          string             `json:"api"`
	Workspace    string             `json:"workspace"`
	Project      string             `json:"project"`
	Bindings     map[string]Binding `json:"bindings"`
	Requirements map[string]any     `json:"requirements"`
	Credentials  map[string]string  `json:"credentials"`
}

func (c *Config) StatePath(api, workspace, project string) string {
	digest := sha256.Sum256([]byte(api + "\n" + workspace + "\n" + project))
	return filepath.Join(c.RootPath(), ".state", hex.EncodeToString(digest[:])+".json")
}
func (c *Config) ReadState(api, workspace, project string) (*State, error) {
	file := c.StatePath(api, workspace, project)
	if err := confinedParents(c.RootPath(), file); err != nil {
		return nil, err
	}
	if info, err := os.Lstat(file); err == nil && (!info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0 || info.Size() > 16<<20) {
		return nil, fmt.Errorf("private state must be a bounded regular file")
	}
	data, err := c.ReadOperationalFile(file, 16<<20)
	if os.IsNotExist(err) {
		return &State{Format: "woobe-development-state@1", RegistryID: c.RegistryID, API: api, Workspace: workspace, Project: project, Bindings: map[string]Binding{}, Requirements: map[string]any{}, Credentials: map[string]string{}}, nil
	}
	if err != nil {
		return nil, err
	}
	if len(data) > 16<<20 {
		return nil, fmt.Errorf("private development state exceeds limit")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	decoder.DisallowUnknownFields()
	var state State
	if decoder.Decode(&state) != nil || state.Format != "woobe-development-state@1" || state.RegistryID != c.RegistryID || state.API != api || state.Workspace != workspace || state.Project != project || state.Bindings == nil || state.Requirements == nil || state.Credentials == nil {
		return nil, fmt.Errorf("private state belongs to another registry or destination")
	}
	var trailing any
	if decoder.Decode(&trailing) != io.EOF {
		return nil, fmt.Errorf("private state contains trailing JSON")
	}
	return &state, nil
}
func (c *Config) WriteState(state *State) error {
	if state.RegistryID != c.RegistryID {
		return fmt.Errorf("private state belongs to another registry")
	}
	data, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		return err
	}
	file := c.StatePath(state.API, state.Workspace, state.Project)
	if err := confinedParents(c.RootPath(), file); err != nil {
		return err
	}
	return c.WriteOperationalFile(file, data)
}
func privateWrite(file string, data []byte) error {
	if err := os.MkdirAll(filepath.Dir(file), 0700); err != nil {
		return err
	}
	if info, err := os.Lstat(file); err == nil && (!info.Mode().IsRegular() || info.Mode()&os.ModeSymlink != 0) {
		return fmt.Errorf("destination must be a regular file")
	}
	f, err := os.CreateTemp(filepath.Dir(file), ".woobe-write-")
	if err != nil {
		return err
	}
	defer os.Remove(f.Name())
	if err = f.Chmod(0600); err == nil {
		_, err = f.Write(data)
	}
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	return os.Rename(f.Name(), file)
}

// WriteOperationalFile confines private authoring state to the configured root.
func (c *Config) WriteOperationalFile(file string, data []byte) error {
	if err := confinedParents(c.RootPath(), file); err != nil {
		return err
	}
	return writeConfined(c.RootPath(), file, data)
}

func (c *Config) ReadOperationalFile(file string, limit int64) ([]byte, error) {
	if err := confinedParents(c.RootPath(), file); err != nil {
		return nil, err
	}
	root, err := os.OpenRoot(c.RootPath())
	if err != nil {
		return nil, err
	}
	defer root.Close()
	relative, err := filepath.Rel(c.RootPath(), file)
	if err != nil {
		return nil, err
	}
	if _, err := root.Lstat(relative); err != nil {
		return nil, err
	}
	return packagebundle.ReadConfined(root, filepath.ToSlash(relative), limit)
}

func writeConfined(directory, file string, data []byte) error {
	if err := os.MkdirAll(directory, 0700); err != nil {
		return err
	}
	before, err := os.Lstat(directory)
	if err != nil || !before.IsDir() || before.Mode()&os.ModeSymlink != 0 {
		return fmt.Errorf("write root must be a real directory")
	}
	root, err := os.OpenRoot(directory)
	if err != nil {
		return err
	}
	defer root.Close()
	opened, err := root.Stat(".")
	if err != nil || !os.SameFile(before, opened) {
		return fmt.Errorf("write root changed while opening")
	}
	relative, err := filepath.Rel(directory, file)
	if err != nil {
		return err
	}
	if err = root.MkdirAll(filepath.Dir(relative), 0700); err != nil {
		return err
	}
	if info, err := root.Lstat(relative); err == nil && !info.Mode().IsRegular() {
		return fmt.Errorf("write destination must be a regular file")
	}
	var nonce [16]byte
	if _, err = rand.Read(nonce[:]); err != nil {
		return err
	}
	name := filepath.Join(filepath.Dir(relative), ".woobe-write-"+hex.EncodeToString(nonce[:]))
	f, err := root.OpenFile(name, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	defer root.Remove(name)
	_, err = f.Write(data)
	if err == nil {
		err = f.Sync()
	}
	closeErr := f.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	return root.Rename(name, relative)
}
func (c *Config) Save() error {
	if err := c.Validate(); err != nil {
		return err
	}
	data, err := yaml.Marshal(c)
	if err != nil {
		return err
	}
	return privateWrite(c.File, data)
}
func confinedParents(root, file string) error {
	relative, err := filepath.Rel(root, file)
	if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
		return fmt.Errorf("destination escapes artifact root")
	}
	current := root
	paths := []string{root}
	for _, part := range strings.Split(filepath.Dir(relative), string(filepath.Separator)) {
		if part != "." {
			current = filepath.Join(current, part)
			paths = append(paths, current)
		}
	}
	for _, candidate := range paths {
		info, err := os.Lstat(candidate)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
			return fmt.Errorf("artifact parent must be a real directory")
		}
	}
	return nil
}
