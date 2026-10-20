package packagebundle

import (
	"archive/tar"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"os"
	"path/filepath"
	"time"
)

func (b *Bundle) Archive(writer io.Writer, includeLock bool) error {
	compressed := gzip.NewWriter(writer)
	compressed.Header.ModTime = time.Unix(0, 0)
	compressed.Header.OS = 255
	archive := tar.NewWriter(compressed)
	defer compressed.Close()
	defer archive.Close()
	for _, item := range b.Inventory {
		header := &tar.Header{Name: item.Path, Size: item.SizeBytes, Mode: 0600, ModTime: time.Unix(0, 0), Typeflag: tar.TypeReg, Format: tar.FormatPAX}
		if err := archive.WriteHeader(header); err != nil {
			return err
		}
		reader, err := os.Open(filepath.Join(b.Root, filepath.FromSlash(item.Path)))
		if err != nil {
			return err
		}
		digest := sha256.New()
		size, copyErr := io.Copy(io.MultiWriter(archive, digest), io.LimitReader(reader, item.SizeBytes+1))
		closeErr := reader.Close()
		if copyErr != nil {
			return copyErr
		}
		if closeErr != nil {
			return closeErr
		}
		if size != item.SizeBytes || hex.EncodeToString(digest.Sum(nil)) != item.SHA256 {
			return failure("PACKAGE_FILE_CHANGED", "Captured file changed before transfer", item.Path)
		}
	}
	if includeLock {
		data, err := json.Marshal(b.Lock())
		if err != nil {
			return err
		}
		if err = archive.WriteHeader(&tar.Header{Name: "woobe.lock.json", Size: int64(len(data)), Mode: 0600, ModTime: time.Unix(0, 0), Typeflag: tar.TypeReg}); err != nil {
			return err
		}
		if _, err = archive.Write(data); err != nil {
			return err
		}
	}
	if err := archive.Close(); err != nil {
		return err
	}
	return compressed.Close()
}

func ReceiveArchive(reader io.Reader, locked bool) (*Bundle, error) {
	return receiveArchive(reader, locked, true)
}

func receiveArchive(reader io.Reader, locked, verifyLock bool) (*Bundle, error) {
	temporary, err := os.MkdirTemp("", "woobe-package-archive-")
	if err != nil {
		return nil, err
	}
	defer os.RemoveAll(temporary)
	archivePath := filepath.Join(temporary, "transport.tar.gz")
	file, err := os.OpenFile(archivePath, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if err != nil {
		return nil, err
	}
	compressedSize, copyErr := io.Copy(file, io.LimitReader(reader, MaxArchiveBytes+1))
	closeErr := file.Close()
	if copyErr != nil {
		return nil, copyErr
	}
	if closeErr != nil {
		return nil, closeErr
	}
	if compressedSize > MaxArchiveBytes {
		return nil, failure("PACKAGE_LIMIT_EXCEEDED", "Compressed archive exceeds 128 MiB", "")
	}
	file, err = os.Open(archivePath)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	compressed, err := gzip.NewReader(file)
	if err != nil {
		return nil, failure("PACKAGE_PARSE_INVALID", "Invalid gzip archive", "")
	}
	defer compressed.Close()
	bounded := &io.LimitedReader{R: compressed, N: MaxBundleBytes + (16 << 20) + 1}
	archive := tar.NewReader(bounded)
	root := filepath.Join(temporary, "content")
	if err = os.Mkdir(root, 0700); err != nil {
		return nil, err
	}
	files := map[string]bool{}
	registry := pathRegistry{}
	entries, total := 0, int64(0)
	for {
		entry, e := archive.Next()
		if e == io.EOF {
			break
		}
		if e != nil {
			return nil, failure("PACKAGE_PARSE_INVALID", "Invalid or truncated tar archive", "")
		}
		entries++
		if entries > MaxFiles*2 {
			return nil, failure("PACKAGE_LIMIT_EXCEEDED", "Archive exceeds entry count", "")
		}
		if entry.Typeflag == tar.TypeDir && (entry.Name == "." || entry.Name == "./") {
			continue
		}
		path, e := PortablePath(entry.Name, "")
		if e != nil {
			return nil, e
		}
		if e = registry.register(path, entry.Typeflag == tar.TypeDir); e != nil {
			return nil, e
		}
		if entry.Typeflag == tar.TypeDir {
			continue
		}
		if entry.Typeflag != tar.TypeReg && entry.Typeflag != tar.TypeRegA {
			return nil, failure("PACKAGE_PATH_INVALID", "Archive rejects links and special entries", path)
		}
		if files[fold(path)] || len(files) > MaxFiles {
			return nil, failure("PACKAGE_PATH_INVALID", "Archive duplicate or case collision", path)
		}
		total += entry.Size
		if entry.Size < 0 || entry.Size > MaxFileBytes || total > MaxBundleBytes {
			return nil, failure("PACKAGE_LIMIT_EXCEEDED", "Archive exceeds file or bundle bytes", path)
		}
		destination := filepath.Join(root, filepath.FromSlash(path))
		if e = os.MkdirAll(filepath.Dir(destination), 0700); e != nil {
			return nil, e
		}
		output, e := os.OpenFile(destination, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
		if e != nil {
			return nil, e
		}
		size, e := io.Copy(output, archive)
		closeErr := output.Close()
		if e != nil {
			return nil, failure("PACKAGE_PARSE_INVALID", "Truncated archive entry", path)
		}
		if closeErr != nil {
			return nil, closeErr
		}
		if size != entry.Size {
			return nil, failure("PACKAGE_INTEGRITY_MISMATCH", "Archive entry size differs", path)
		}
		files[fold(path)] = true
	}
	if _, err = io.Copy(io.Discard, bounded); err != nil {
		return nil, failure("PACKAGE_PARSE_INVALID", "Invalid compressed archive checksum", "")
	}
	if bounded.N <= 0 {
		return nil, failure("PACKAGE_LIMIT_EXCEEDED", "Decompressed transport exceeds limits", "")
	}
	bundle, err := load(root, locked, verifyLock)
	if err != nil {
		return nil, err
	}
	declared := map[string]bool{"woobe.lock.json": true}
	for _, item := range bundle.Inventory {
		declared[fold(item.Path)] = true
	}
	for path := range files {
		if !declared[path] {
			bundle.Close()
			return nil, failure("PACKAGE_RESOURCE_INVALID", "Archive contains undeclared files", path)
		}
	}
	return bundle, nil
}

// LoadArchive captures an already checked regular transport file through its parent handle.
func LoadArchive(path string, locked bool) (*Bundle, error) {
	return loadArchive(path, locked, true)
}

// LoadArchiveStructure retains transport/path safety while checking only the
// author structure. The embedded lock is not evidence in this validation mode.
func LoadArchiveStructure(path string) (*Bundle, error) {
	return loadArchive(path, false, false)
}

func loadArchive(path string, locked, verifyLock bool) (*Bundle, error) {
	root, err := os.OpenRoot(filepath.Dir(path))
	if err != nil {
		return nil, failure("PACKAGE_PATH_INVALID", "Archive parent is unavailable", "")
	}
	defer root.Close()
	input, err := confinedOpen(root, filepath.Base(path))
	if err != nil {
		return nil, err
	}
	defer input.Close()
	info, err := input.Stat()
	if err != nil || info.Size() > MaxArchiveBytes {
		return nil, failure("PACKAGE_LIMIT_EXCEEDED", "Archive exceeds transport limit", "")
	}
	return receiveArchive(input, locked, verifyLock)
}
