//go:build windows

package packagebundle

import (
	"golang.org/x/sys/windows"
	"os"
)

func openRegular(root *os.Root, name string) (*os.File, error) { return root.Open(name) }
func singleLink(info os.FileInfo) bool                         { return true } // Checked on the captured native handle below.
func fileSingleLink(file *os.File) bool {
	var information windows.ByHandleFileInformation
	return windows.GetFileInformationByHandle(windows.Handle(file.Fd()), &information) == nil && information.NumberOfLinks == 1
}
