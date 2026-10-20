//go:build linux || darwin

package packagecheckpoint

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"os"
)

func checkStateDirectory(root *os.Root) error {
	info, err := root.Stat(".")
	if err != nil {
		return err
	}
	if info.Mode().Perm()&0077 != 0 {
		return output.New(3, "Package state directory must be private (0700)")
	}
	return nil
}

func protectNewDirectory(path string) error { return nil }
