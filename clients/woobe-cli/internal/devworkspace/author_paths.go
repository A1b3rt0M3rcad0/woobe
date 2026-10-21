package devworkspace

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
)

// Author files cannot share paths with private development state, on any OS.
func validateAuthorPath(value string) error {
	for _, part := range strings.Split(value, "/") {
		if strings.EqualFold(part, ".state") || strings.EqualFold(part, Filename) || strings.EqualFold(part, ".git") {
			return fmt.Errorf("author path uses private operational metadata")
		}
	}
	_, err := packagebundle.PortablePath(value, "")
	return err
}

func authorSupportPaths(document map[string]any, descriptor string) ([]string, error) {
	paths, err := packagebundle.SupportPaths(document, descriptor)
	if err != nil {
		return nil, err
	}
	for _, path := range paths {
		if err := validateAuthorPath(path); err != nil {
			return nil, err
		}
	}
	return paths, nil
}

func (c *Config) validateAuthorWrite(file string) error {
	relative, err := filepath.Rel(c.RootPath(), file)
	if err != nil {
		return err
	}
	if err := validateAuthorPath(filepath.ToSlash(relative)); err != nil {
		return err
	}
	return c.validateWrite(file)
}

// ReadAuthorSupports copies only declared files confined to the input folder.
// It excludes operational metadata and uses the same limits as portable bundles.
func ReadAuthorSupports(document map[string]any, file string) (map[string][]byte, error) {
	paths, err := authorSupportPaths(document, filepath.Base(file))
	if err != nil {
		return nil, err
	}
	if len(paths) > packagebundle.MaxFiles-1 {
		return nil, fmt.Errorf("too many declared support files")
	}
	root, err := os.OpenRoot(filepath.Dir(file))
	if err != nil {
		return nil, err
	}
	defer root.Close()
	supports := map[string][]byte{}
	var total int64
	for _, path := range paths {
		data, err := packagebundle.ReadConfined(root, path, packagebundle.MaxFileBytes)
		if err != nil {
			return nil, fmt.Errorf("declared support file is unavailable or unsafe: %s", path)
		}
		total += int64(len(data))
		if total > packagebundle.MaxBundleBytes {
			return nil, fmt.Errorf("declared support files exceed bundle limit")
		}
		supports[path] = data
	}
	return supports, nil
}
