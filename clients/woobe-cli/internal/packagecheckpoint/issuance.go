package packagecheckpoint

import (
	"crypto/rand"
	"encoding/hex"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"os"
	"path/filepath"
)

// PrivateDestination pins the parent and prepares an empty protected temporary
// file. The final path appears only after successful issuance and a durable write.
type PrivateDestination struct {
	root                   *os.Root
	file                   *os.File
	temporary, destination string
}

func PreparePrivateDestination(path string) (*PrivateDestination, error) {
	if err := supportedProtection(); err != nil {
		return nil, err
	}
	root, err := os.OpenRoot(filepath.Dir(path))
	if err != nil {
		return nil, output.New(2, "Secret destination parent is unavailable")
	}
	if err = checkPublicationParent(root); err != nil {
		root.Close()
		return nil, err
	}
	name := filepath.Base(path)
	if _, err = root.Lstat(name); !os.IsNotExist(err) {
		root.Close()
		return nil, output.New(2, "Secret destination must not exist")
	}
	nonce := make([]byte, 16)
	if _, err = rand.Read(nonce); err != nil {
		root.Close()
		return nil, err
	}
	temporary := ".woobe-issued-secret-" + hex.EncodeToString(nonce)
	file, err := root.OpenFile(temporary, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		root.Close()
		return nil, output.New(2, "Secret destination is not writable")
	}
	d := &PrivateDestination{root, file, temporary, name}
	if err = protectNewPrivateFile(file); err != nil {
		d.Close()
		return nil, err
	}
	if err = checkPrivateFile(file); err != nil {
		d.Close()
		return nil, err
	}
	return d, nil
}
func (d *PrivateDestination) Close() { d.file.Close(); d.root.Remove(d.temporary); d.root.Close() }
func (d *PrivateDestination) Publish(data []byte) error {
	if len(data) > 2<<20 {
		return output.New(2, "Issued secret file exceeds 2 MiB")
	}
	if _, err := d.file.Write(data); err != nil {
		return err
	}
	if err := d.file.Sync(); err != nil {
		return err
	}
	if err := d.file.Close(); err != nil {
		return err
	}
	if err := d.root.Link(d.temporary, d.destination); err != nil {
		return err
	}
	// Remove the temporary link before checking/reading the private final file.
	if err := d.root.Remove(d.temporary); err != nil {
		return err
	}
	parent, err := d.root.Open(".")
	if err != nil {
		return err
	}
	defer parent.Close()
	return syncParent(parent)
}
