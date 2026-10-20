package packagecheckpoint

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"os"
)

// EnsurePrivateDirectory owns only a newly created state directory. Existing
// directories are checked, never silently chmodded or assigned a different ACL.
func EnsurePrivateDirectory(path string) error {
	info, err := os.Lstat(path)
	if err == nil {
		if !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
			return output.New(3, "Package state path must be a private directory")
		}
	} else if !os.IsNotExist(err) {
		return err
	} else {
		if err = os.MkdirAll(path, 0700); err != nil {
			return err
		}
		if err = protectNewDirectory(path); err != nil {
			return err
		}
	}
	root, err := os.OpenRoot(path)
	if err != nil {
		return err
	}
	defer root.Close()
	return checkStateDirectory(root)
}
