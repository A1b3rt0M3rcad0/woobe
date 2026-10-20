package packagebundle

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
)

// Publish exposes a new directory only after every captured byte and lock has
// been verified. Native exclusive rename is required; ordinary rename is unsafe.
func (b *Bundle) Publish(destination string) error {
	return b.publish(destination, true)
}

// PublishAuthor creates a separate editable copy. The verified captured source
// stays sealed; the new directory deliberately has no captured inventory lock.
func (b *Bundle) PublishAuthor(destination string) error {
	return b.publish(destination, false)
}

func (b *Bundle) publish(destination string, sealed bool) error {
	absolute, err := filepath.Abs(destination)
	if err != nil {
		return err
	}
	parent, name := filepath.Dir(absolute), filepath.Base(absolute)
	if name == "." || name == string(filepath.Separator) {
		return failure("PACKAGE_PATH_INVALID", "Destination must name a new directory", "")
	}
	if _, err = os.Lstat(absolute); err == nil {
		return failure("PACKAGE_DESTINATION_EXISTS", "Destination already exists", "")
	} else if !os.IsNotExist(err) {
		return err
	}
	stage, err := os.MkdirTemp(parent, ".woobe-package-export-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(stage)
	source, err := os.OpenRoot(b.Root)
	if err != nil {
		return err
	}
	defer source.Close()
	for _, item := range b.Inventory {
		reader, err := confinedOpen(source, item.Path)
		if err != nil {
			return err
		}
		target := filepath.Join(stage, filepath.FromSlash(item.Path))
		if err = os.MkdirAll(filepath.Dir(target), 0700); err != nil {
			reader.Close()
			return err
		}
		writer, err := os.OpenFile(target, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
		if err != nil {
			reader.Close()
			return err
		}
		hash := sha256.New()
		size, copyErr := io.Copy(io.MultiWriter(writer, hash), io.LimitReader(reader, item.SizeBytes+1))
		reader.Close()
		syncErr := writer.Sync()
		closeErr := writer.Close()
		if copyErr != nil {
			return copyErr
		}
		if syncErr != nil {
			return syncErr
		}
		if closeErr != nil {
			return closeErr
		}
		if size != item.SizeBytes || hex.EncodeToString(hash.Sum(nil)) != item.SHA256 {
			return failure("PACKAGE_INTEGRITY_MISMATCH", "Captured artifact changed before publication", item.Path)
		}
	}
	if sealed {
		lock, err := json.Marshal(b.Lock())
		if err != nil {
			return err
		}
		if err = os.WriteFile(filepath.Join(stage, "woobe.lock.json"), lock, 0600); err != nil {
			return err
		}
	}
	verified, err := Load(stage, sealed)
	if err != nil {
		return err
	}
	if verified.ArtifactDigest != b.ArtifactDigest {
		verified.Close()
		return failure("PACKAGE_INTEGRITY_MISMATCH", "Export closure differs from the verified artifact", "")
	}
	verified.Close()
	return renameNoReplace(stage, absolute)
}
