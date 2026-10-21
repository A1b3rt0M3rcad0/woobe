//go:build linux || darwin

package packagebundle

import (
	"golang.org/x/sys/unix"
	"os"
)

func openRegular(root *os.Root, name string) (*os.File, error) {
	return root.OpenFile(name, os.O_RDONLY|unix.O_NOFOLLOW|unix.O_NONBLOCK|unix.O_CLOEXEC, 0)
}
func singleLink(info os.FileInfo) bool { return nativeSingleLink(info) }

func fileSingleLink(file *os.File) bool {
	info, err := file.Stat()
	return err == nil && singleLink(info)
}
