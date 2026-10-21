package devworkspace

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
)

type localChange struct {
	Remove bool   `json:"remove,omitempty"`
	Path   string `json:"path"`
	Before []byte `json:"before"`
	Exists bool   `json:"exists"`
	After  []byte `json:"after"`
}
type localJournal struct {
	RegistryID string        `json:"registry_id"`
	Changes    []localChange `json:"changes"`
}

// Lock serializes development commands across processes, including recovery.
// Native OS locks are released if the process terminates unexpectedly.
func (c *Config) Lock() (func() error, error) {
	path := filepath.Join(c.RootPath(), ".state", "registry")
	if err := confinedParents(c.RootPath(), path); err != nil {
		return nil, err
	}
	store, err := packagecheckpoint.Open(path)
	if err != nil {
		return nil, err
	}
	if err = c.Recover(); err != nil {
		store.Close()
		return nil, err
	}
	return store.Close, nil
}

func (c *Config) journalPath() string {
	return filepath.Join(c.RootPath(), ".state", "local-transaction.json")
}

func (c *Config) validateWrite(path string) error {
	if filepath.Clean(path) == filepath.Clean(c.File) {
		return confinedParents(filepath.Dir(c.File), path)
	}
	return confinedParents(c.RootPath(), path)
}

// Recover rolls forward only files that still match either their previous or
// intended contents. An external edit remains intact and needs reconciliation.
func (c *Config) Recover() error {
	file := c.journalPath()
	if err := confinedParents(c.RootPath(), file); err != nil {
		return err
	}
	if info, err := os.Lstat(file); err == nil && (!info.Mode().IsRegular() || info.Size() > 512<<20) {
		return fmt.Errorf("invalid local transaction journal")
	}
	data, err := c.ReadOperationalFile(file, 512<<20)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		return err
	}
	var journal localJournal
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if decoder.Decode(&journal) != nil || journal.RegistryID != c.RegistryID {
		return fmt.Errorf("local transaction belongs to another registry")
	}
	for _, change := range journal.Changes {
		if err := c.validateWrite(change.Path); err != nil {
			return err
		}
		current, err := os.ReadFile(change.Path)
		if err != nil && !os.IsNotExist(err) {
			return err
		}
		if (change.Remove && os.IsNotExist(err)) || (!change.Remove && bytes.Equal(current, change.After) && err == nil) {
			continue
		}
		if (change.Exists && (err != nil || !bytes.Equal(current, change.Before))) || (!change.Exists && err == nil) {
			return fmt.Errorf("local transaction conflicts with an external edit: %s", change.Path)
		}
	}
	for _, change := range journal.Changes {
		if change.Remove {
			if _, err := os.Lstat(change.Path); os.IsNotExist(err) {
				continue
			}
			root, err := os.OpenRoot(c.RootPath())
			if err != nil {
				return err
			}
			relative, err := filepath.Rel(c.RootPath(), change.Path)
			if err == nil {
				err = root.Remove(relative)
			}
			root.Close()
			if err != nil {
				return err
			}
			continue
		}
		if err := c.writeTransactionFile(change.Path, change.After); err != nil {
			return err
		}
	}
	return os.Remove(file)
}

func (c *Config) Commit(writes map[string][]byte) error { return c.CommitFiles(writes, nil) }

func (c *Config) CommitFiles(writes map[string][]byte, removals []string) error {
	if err := c.Recover(); err != nil {
		return err
	}
	journal := localJournal{RegistryID: c.RegistryID}
	keys := make([]string, 0, len(writes))
	for key := range writes {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		if err := c.validateWrite(key); err != nil {
			return err
		}
		if info, err := os.Lstat(key); err == nil && !info.Mode().IsRegular() {
			return fmt.Errorf("artifact destination is not a regular file")
		}
		before, err := os.ReadFile(key)
		if err != nil && !os.IsNotExist(err) {
			return err
		}
		journal.Changes = append(journal.Changes, localChange{Path: key, Before: before, Exists: err == nil, After: writes[key]})
	}
	for _, path := range removals {
		if _, exists := writes[path]; exists || filepath.Clean(path) == filepath.Clean(c.File) {
			return fmt.Errorf("transaction cannot remove a write destination or config")
		}
		if err := c.validateWrite(path); err != nil {
			return err
		}
		before, err := c.ReadOperationalFile(path, 128<<20)
		if err != nil {
			return err
		}
		journal.Changes = append(journal.Changes, localChange{Path: path, Before: before, Exists: true, Remove: true})
	}
	data, err := json.Marshal(journal)
	if err != nil {
		return err
	}
	if len(data) > 512<<20 {
		return fmt.Errorf("local transaction exceeds journal limit")
	}
	if err = c.WriteOperationalFile(c.journalPath(), data); err != nil {
		return err
	}
	return c.Recover()
}

func (c *Config) writeTransactionFile(path string, data []byte) error {
	if filepath.Clean(path) == filepath.Clean(c.File) {
		return writeConfined(filepath.Dir(c.File), path, data)
	}
	return c.WriteOperationalFile(path, data)
}
