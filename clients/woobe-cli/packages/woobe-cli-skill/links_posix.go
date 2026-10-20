//go:build !windows

package assistantskill

import (
	"os"
	"syscall"
)

func singleLink(_ *os.File, info os.FileInfo) bool {
	stat, ok := info.Sys().(*syscall.Stat_t)
	return ok && stat.Nlink == 1
}
