//go:build linux || darwin

package packagecheckpoint

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"golang.org/x/sys/unix"
	"os"
)

func supportedProtection() error { return nil }

func lockCheckpoint(root *os.Root, name string) (*os.File, error) {
	file, err := root.OpenFile(name, os.O_RDWR|os.O_CREATE|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC, 0600)
	if err != nil {
		return nil, output.New(3, "package checkpoint lock is unavailable")
	}
	fd := int(file.Fd())
	info, err := file.Stat()
	if err != nil || !info.Mode().IsRegular() || info.Mode().Perm()&0077 != 0 {
		file.Close()
		return nil, output.New(3, "package checkpoint lock must be private and regular")
	}
	if err = checkPrivateFile(file); err != nil {
		file.Close()
		return nil, err
	}
	if err = unix.Flock(fd, unix.LOCK_EX|unix.LOCK_NB); err != nil {
		file.Close()
		return nil, output.New(2, "package checkpoint is in use by another command")
	}
	return file, nil
}

func openPrivateRead(path string) (*os.File, error) {
	fd, err := unix.Open(path, unix.O_RDONLY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC, 0)
	if err != nil {
		return nil, err
	}
	return os.NewFile(uintptr(fd), path), nil
}

func openConfinedRead(root *os.Root, name string) (*os.File, error) {
	return root.OpenFile(name, os.O_RDONLY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC, 0)
}

func privateMode(info os.FileInfo) bool {
	return info.Mode().IsRegular() && info.Mode().Perm()&0077 == 0
}
func checkPrivateFile(file *os.File) error {
	info, err := file.Stat()
	if err != nil {
		return err
	}
	if !privateMode(info) {
		return output.New(3, "Package operational file must be private and regular")
	}
	var identity unix.Stat_t
	if err = unix.Fstat(int(file.Fd()), &identity); err != nil {
		return err
	}
	if identity.Nlink != 1 {
		return output.New(3, "Package operational file must not have hard links")
	}
	return nil
}
func checkPrivateParent(root *os.Root) error { return nil }
func syncParent(file *os.File) error         { return file.Sync() }

func protectNewPrivateFile(file *os.File) error { return file.Chmod(0600) }

func checkPublicationParent(root *os.Root) error {
	parent, err := root.Open(".")
	if err != nil {
		return err
	}
	defer parent.Close()
	info, err := parent.Stat()
	if err != nil {
		return err
	}
	if info.Mode().Perm()&0022 != 0 && info.Mode()&os.ModeSticky == 0 {
		return output.New(3, "Secret destination parent grants other accounts write access; use an owner-controlled directory")
	}
	return nil
}
