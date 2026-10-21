//go:build !linux && !darwin && !windows

package packagecheckpoint

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"os"
)

func supportedProtection() error {
	return output.New(9, "private package checkpoints require a supported OS protection mechanism")
}
func lockCheckpoint(root *os.Root, name string) (*os.File, error) { return nil, supportedProtection() }

func openPrivateRead(path string) (*os.File, error) { return nil, supportedProtection() }

func openConfinedRead(root *os.Root, name string) (*os.File, error) {
	return nil, supportedProtection()
}

func privateMode(info os.FileInfo) bool      { return false }
func checkPrivateFile(file *os.File) error   { return supportedProtection() }
func checkPrivateParent(root *os.Root) error { return supportedProtection() }
func syncParent(file *os.File) error         { return supportedProtection() }

func protectNewPrivateFile(file *os.File) error { return supportedProtection() }

func checkPublicationParent(root *os.Root) error { return supportedProtection() }
