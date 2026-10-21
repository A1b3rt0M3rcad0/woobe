//go:build !linux && !darwin

package packagefmt

import "os"

func openBindingsRead(path string) (*os.File, error) { return os.Open(path) }
