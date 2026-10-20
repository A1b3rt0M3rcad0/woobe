//go:build linux || darwin

package packagebundle

import (
	"os"
	"syscall"
)

func nativeSingleLink(info os.FileInfo) bool {
	stat, ok := info.Sys().(*syscall.Stat_t)
	return ok && stat.Nlink == 1
}
