package packagecheckpoint

import (
	"crypto/rand"
	"encoding/hex"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"io"
	"os"
	"path/filepath"
)

// WritePrivateExclusive publishes a bounded operational receipt without replacing
// any existing destination. It deliberately shares checkpoint platform protection.
func WritePrivateExclusive(path string, data []byte) error {
	if err := supportedProtection(); err != nil {
		return err
	}
	if len(data) > 2<<20 {
		return output.New(2, "Package receipt exceeds 2 MiB")
	}
	root, err := os.OpenRoot(filepath.Dir(path))
	if err != nil {
		return output.New(2, "Package receipt parent is unavailable")
	}
	defer root.Close()
	if err = checkPrivateParent(root); err != nil {
		return err
	}
	parent, err := root.Open(".")
	if err != nil {
		return err
	}
	defer parent.Close()
	nonce := make([]byte, 16)
	if _, err = rand.Read(nonce); err != nil {
		return err
	}
	name := ".woobe-package-receipt-" + hex.EncodeToString(nonce)
	temporary, err := root.OpenFile(name, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	defer temporary.Close()
	defer root.Remove(name)
	if _, err = temporary.Write(data); err == nil {
		err = temporary.Sync()
	}
	if err != nil {
		return err
	}
	if err = temporary.Close(); err != nil {
		return err
	}
	if err = root.Link(name, filepath.Base(path)); err != nil {
		return output.New(2, "Package receipt destination already exists or cannot be published")
	}
	return syncParent(parent)
}

func ReadPrivate(path string) ([]byte, error) {
	if err := supportedProtection(); err != nil {
		return nil, err
	}
	info, err := os.Lstat(path)
	if err != nil || !privateMode(info) || info.Size() > 2<<20 {
		return nil, output.New(3, "Package receipt must be a bounded private regular file")
	}
	file, err := openPrivateRead(path)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	actual, err := file.Stat()
	if err != nil || !os.SameFile(info, actual) || !privateMode(actual) {
		return nil, output.New(3, "Package receipt changed while opening")
	}
	if err = checkPrivateFile(file); err != nil {
		return nil, err
	}
	data, err := io.ReadAll(io.LimitReader(file, 2<<20+1))
	if err != nil || len(data) > 2<<20 {
		return nil, output.New(2, "Package receipt exceeds 2 MiB")
	}
	return data, nil
}
