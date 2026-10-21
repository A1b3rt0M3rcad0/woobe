package devworkspace

import (
	"errors"
	"fmt"
	"os"

	"gopkg.in/yaml.v3"
)

// PruneMissing explicitly unregisters absent descriptors after validating the
// remaining graph. Invalid, unreadable or linked files are never missing.
// Author files and native bindings remain untouched.
func (c *Config) PruneMissing(dryRun bool) ([]Resource, error) {
	if err := c.Validate(); err != nil {
		return nil, err
	}
	info, err := os.Lstat(c.RootPath())
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		return nil, err
	}
	var root *os.Root
	if err == nil {
		if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
			return nil, fmt.Errorf("artifact root must be a real directory")
		}
		root, err = os.OpenRoot(c.RootPath())
		if err != nil {
			return nil, err
		}
		defer root.Close()
	}
	next := *c
	next.Resources = []Resource{}
	missing := []Resource{}
	for _, resource := range c.Resources {
		err := os.ErrNotExist
		if root != nil {
			_, err = readConfined(root, descriptor(resource))
		}
		if errors.Is(err, os.ErrNotExist) {
			missing = append(missing, resource)
		} else if err != nil {
			return nil, descriptorReadError(resource, err)
		} else {
			next.Resources = append(next.Resources, resource)
		}
	}
	if _, err := LoadGraph(&next); err != nil {
		return nil, fmt.Errorf("cannot prune missing artifacts: %w; restore missing dependencies or remove their references first", err)
	}
	if dryRun || len(missing) == 0 {
		return missing, nil
	}
	data, err := yaml.Marshal(&next)
	if err != nil {
		return nil, err
	}
	if err := c.Commit(map[string][]byte{c.File: data}); err != nil {
		return nil, err
	}
	*c = next
	return missing, nil
}
