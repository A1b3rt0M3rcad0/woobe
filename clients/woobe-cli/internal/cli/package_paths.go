package cli

import (
	"path/filepath"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
)

func excludePackageOperationalFiles(source string, bundle *packagebundle.Bundle, paths ...string) error {
	if strings.HasSuffix(source, ".tar.gz") || strings.HasSuffix(source, ".tgz") {
		return nil
	}
	root, err := filepath.Abs(source)
	if err != nil {
		return output.New(2, "Invalid Package source")
	}
	if filepath.Base(root) == "woobe.yaml" {
		root = filepath.Dir(root)
	}
	for _, operational := range paths {
		if operational == "" {
			continue
		}
		absolute, err := filepath.Abs(operational)
		if err != nil {
			return output.New(2, "Invalid Package operational path")
		}
		relative, err := filepath.Rel(root, absolute)
		if err != nil {
			continue
		}
		for _, item := range bundle.Inventory {
			if filepath.ToSlash(relative) == item.Path {
				return output.New(2, "Bindings, plan and checkpoint files cannot belong to the portable closure")
			}
		}
	}
	return nil
}
