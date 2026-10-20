//go:build darwin

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
	err = unix.RenameatxNp(int(parent.Fd()), filepath.Base(source), int(parent.Fd()), filepath.Base(destination), unix.RENAME_EXCL)
	if errors.Is(err, unix.ENOSYS) || errors.Is(err, unix.ENOTSUP) || errors.Is(err, unix.EINVAL) {
		return failure("PACKAGE_UNSUPPORTED", "Filesystem does not support exclusive directory publication", "")
	}
	return err
}
