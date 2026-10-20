//go:build !linux && !darwin && !windows

package packagecheckpoint

import "os"

func protectNewDirectory(path string) error { return supportedProtection() }

func checkStateDirectory(root *os.Root) error { return checkPrivateParent(root) }
