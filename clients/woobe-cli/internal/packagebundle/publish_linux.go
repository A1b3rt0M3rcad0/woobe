//go:build linux

package packagebundle

import (
	"errors"
	"golang.org/x/sys/unix"
	"os"
	"path/filepath"
)

func renameNoReplace(source, destination string) error {
	parent, err := os.Open(filepath.Dir(destination))
	if err != nil {
		return err
	}
	defer parent.Close()
	err = unix.Renameat2(int(parent.Fd()), filepath.Base(source), int(parent.Fd()), filepath.Base(destination), unix.RENAME_NOREPLACE)
	if errors.Is(err, unix.ENOSYS) || errors.Is(err, unix.EOPNOTSUPP) || errors.Is(err, unix.EINVAL) {
		return failure("PACKAGE_UNSUPPORTED", "Filesystem does not support exclusive directory publication", "")
	}
	return err
}
