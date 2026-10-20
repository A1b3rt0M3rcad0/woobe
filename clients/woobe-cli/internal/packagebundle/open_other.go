//go:build !linux && !darwin && !windows

package packagebundle

import "os"

func openRegular(root *os.Root, name string) (*os.File, error) { return root.Open(name) }
func singleLink(info os.FileInfo) bool                         { return true }

func fileSingleLink(file *os.File) bool { return true }
