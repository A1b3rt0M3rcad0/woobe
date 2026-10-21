//go:build windows

package packagebundle

import "golang.org/x/sys/windows"

func renameNoReplace(source, destination string) error {
	from, err := windows.UTF16PtrFromString(source)
	if err != nil {
		return err
	}
	to, err := windows.UTF16PtrFromString(destination)
	if err != nil {
		return err
	}
	// Without MOVEFILE_REPLACE_EXISTING an existing destination always wins.
	return windows.MoveFileEx(from, to, 0)
}
