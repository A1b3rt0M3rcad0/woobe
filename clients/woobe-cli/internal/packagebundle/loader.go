package packagebundle

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"golang.org/x/text/cases"
	"golang.org/x/text/unicode/norm"
)

const MaxFiles = 1024
const MaxDescriptorTotal int64 = 16 << 20
const MaxFileBytes int64 = 64 << 20
const MaxBundleBytes int64 = 512 << 20
const MaxArchiveBytes int64 = 128 << 20

type Bundle struct {
	Root           string
	Graph          *packagefmt.Graph
	Inventory      []InventoryFile
	ArtifactDigest string
	LockIntegrity  string
}

func (b *Bundle) Close() error { return os.RemoveAll(b.Root) }
func (b *Bundle) Lock() map[string]any {
	return map[string]any{"format": "woobe-package", "schema_version": b.Graph.Manifest["schema_version"], "kind": "PackageLock", "algorithm": "sha256", "inventory": b.Inventory, "artifact_digest": b.ArtifactDigest}
}
func failure(code, message, file string) error {
	return &packagefmt.Diagnostic{Code: code, Message: message, File: file}
}
func fold(value string) string { return norm.NFC.String(cases.Fold().String(value)) }

func confinedOpen(root *os.Root, path string) (*os.File, error) {
	parts := strings.Split(path, "/")
	for i := range parts {
		info, err := root.Lstat(strings.Join(parts[:i+1], "/"))
		if err != nil {
			// Preserve the OS cause without weakening path confinement.
			return nil, fmt.Errorf("%w: %w", failure("PACKAGE_PATH_INVALID", "Declared file or parent could not be inspected", path), err)
		}
		if info.Mode()&os.ModeSymlink != 0 {
			return nil, failure("PACKAGE_PATH_INVALID", "Symlinks or unavailable files are forbidden", path)
		}
		if i == len(parts)-1 && (!info.Mode().IsRegular() || !singleLink(info)) {
			return nil, failure("PACKAGE_PATH_INVALID", "Only regular files with one link are accepted", path)
		}
		if i < len(parts)-1 && !info.IsDir() {
			return nil, failure("PACKAGE_PATH_INVALID", "Parent must be a directory", path)
		}
	}
	stream, err := openRegular(root, path)
	if err != nil {
		return nil, failure("PACKAGE_PATH_INVALID", "File is not confined to package root", path)
	}
	opened, err := stream.Stat()
	named, lookupErr := root.Lstat(path)
	if err != nil || lookupErr != nil || !opened.Mode().IsRegular() || !fileSingleLink(stream) || !os.SameFile(opened, named) {
		stream.Close()
		return nil, failure("PACKAGE_PATH_INVALID", "Only stable regular files are accepted", path)
	}
	return stream, nil
}

func Load(input string, locked bool) (bundle *Bundle, err error) {
	return load(input, locked, true)
}

// LoadStructure validates current author bytes without evaluating a captured
// lock. It is for read-only validation, never import, planning or publication.
func LoadStructure(input string) (*Bundle, error) {
	return load(input, false, false)
}

func load(input string, locked, verifyLock bool) (bundle *Bundle, err error) {
	absolute, err := filepath.Abs(input)
	if err != nil {
		return nil, err
	}
	if filepath.Base(absolute) == "woobe.yaml" {
		absolute = filepath.Dir(absolute)
	}
	info, err := os.Lstat(absolute)
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return nil, failure("PACKAGE_PATH_INVALID", "Input must be a package directory or its woobe.yaml", "")
	}
	source, err := os.OpenRoot(absolute)
	if err != nil {
		return nil, err
	}
	defer source.Close()
	temporary, err := os.MkdirTemp("", "woobe-package-")
	if err != nil {
		return nil, err
	}
	bundle = &Bundle{Root: temporary}
	owned := bundle
	defer func() {
		if err != nil {
			owned.Close()
		}
	}()
	captured := map[string]bool{}
	seen := map[string]string{}
	registry := pathRegistry{}
	total := int64(0)
	capture := func(raw string, limit int64) error {
		path, e := PortablePath(raw, "")
		if e != nil {
			return e
		}
		if e = registry.register(path, false); e != nil {
			return e
		}
		if captured[path] {
			return nil
		}
		if _, exists := seen[fold(path)]; exists {
			return failure("PACKAGE_PATH_INVALID", "Normalized path collision", path)
		}
		if len(bundle.Inventory) >= MaxFiles {
			return failure("PACKAGE_LIMIT_EXCEEDED", "Bundle exceeds file count limit", path)
		}
		reader, e := confinedOpen(source, path)
		if e != nil {
			return e
		}
		defer reader.Close()
		before, e := reader.Stat()
		if e != nil {
			return e
		}
		if before.Size() > limit {
			return failure("PACKAGE_LIMIT_EXCEEDED", "File exceeds byte limit", path)
		}
		destination := filepath.Join(temporary, filepath.FromSlash(path))
		if e = os.MkdirAll(filepath.Dir(destination), 0700); e != nil {
			return e
		}
		writer, e := os.OpenFile(destination, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
		if e != nil {
			return e
		}
		digest := sha256.New()
		size, e := io.Copy(io.MultiWriter(writer, digest), io.LimitReader(reader, limit+1))
		closeErr := writer.Close()
		if e != nil {
			return e
		}
		if closeErr != nil {
			return closeErr
		}
		after, e := reader.Stat()
		if e != nil {
			return e
		}
		named, e := source.Lstat(path)
		if e != nil {
			return e
		}
		if size > limit || total+size > MaxBundleBytes {
			return failure("PACKAGE_LIMIT_EXCEEDED", "Bundle resource limit exceeded", path)
		}
		if size != before.Size() || before.Size() != after.Size() || !before.ModTime().Equal(after.ModTime()) || !os.SameFile(before, named) {
			return failure("PACKAGE_FILE_CHANGED", "File changed while creating snapshot", path)
		}
		captured[path] = true
		seen[fold(path)] = path
		total += size
		bundle.Inventory = append(bundle.Inventory, InventoryFile{path, size, hex.EncodeToString(digest.Sum(nil))})
		return nil
	}
	descriptor := func(path string) (*packagefmt.Document, error) {
		if e := capture(path, packagefmt.MaxDescriptorBytes); e != nil {
			return nil, e
		}
		data, e := os.ReadFile(filepath.Join(temporary, filepath.FromSlash(path)))
		if e != nil {
			return nil, e
		}
		document, e := packagefmt.Decode(data, path)
		if e != nil {
			return nil, e
		}
		if e = packagefmt.Validate(document); e != nil {
			return nil, e
		}
		return document, nil
	}
	manifest, err := descriptor("woobe.yaml")
	if err != nil {
		return nil, err
	}
	if manifest.Value["kind"] != "Package" {
		return nil, failure("PACKAGE_SCHEMA_INVALID", "woobe.yaml must be a Package", "")
	}
	documents := map[string]*packagefmt.Document{}
	descriptorBytes := bundle.Inventory[0].SizeBytes
	for _, value := range packagefmt.List(packagefmt.Object(manifest.Value["spec"])["resources"]) {
		path, e := PortablePath(packagefmt.Text(value), "")
		if e != nil {
			return nil, e
		}
		if _, exists := documents[path]; exists {
			return nil, failure("PACKAGE_REFERENCE_DUPLICATE", "Resource path is duplicated", path)
		}
		document, e := descriptor(path)
		if e != nil {
			return nil, e
		}
		documents[path] = document
		file, e := os.Stat(filepath.Join(temporary, filepath.FromSlash(path)))
		if e != nil {
			return nil, e
		}
		descriptorBytes += file.Size()
		if descriptorBytes > MaxDescriptorTotal {
			return nil, failure("PACKAGE_LIMIT_EXCEEDED", "Descriptors exceed 16 MiB", path)
		}
		supports, e := SupportPaths(document.Value, path)
		if e != nil {
			return nil, e
		}
		for _, support := range supports {
			if e = capture(support, MaxFileBytes); e != nil {
				return nil, e
			}
		}
	}
	bundle.Graph, err = packagefmt.Resolve(manifest.Value, documents)
	if err != nil {
		return nil, err
	}
	sort.Slice(bundle.Inventory, func(i, j int) bool { return bundle.Inventory[i].Path < bundle.Inventory[j].Path })
	bundle.ArtifactDigest = VersionInventoryDigest(bundle.Inventory, bundle.Graph.Manifest["schema_version"].(string))
	bundle.LockIntegrity = "not_evaluated"
	if !verifyLock {
		return bundle, nil
	}
	bundle.LockIntegrity = "absent"
	lockInfo, lockErr := source.Lstat("woobe.lock.json")
	if lockErr == nil {
		if !lockInfo.Mode().IsRegular() {
			return nil, failure("PACKAGE_PATH_INVALID", "Lock must be a regular file", "")
		}
		stream, e := confinedOpen(source, "woobe.lock.json")
		if e != nil {
			return nil, e
		}
		data, e := io.ReadAll(io.LimitReader(stream, packagefmt.MaxDescriptorBytes+1))
		stream.Close()
		if e != nil {
			return nil, e
		}
		document, e := packagefmt.Decode(data, "woobe.lock.json")
		if e != nil {
			return nil, e
		}
		if e = packagefmt.Validate(document); e != nil {
			return nil, e
		}
		expected, e := json.Marshal(bundle.Lock())
		if e != nil {
			return nil, e
		}
		parsed, e := packagefmt.Decode(expected, "woobe.lock.json")
		if e != nil {
			return nil, e
		}
		if !reflect.DeepEqual(document.Value, parsed.Value) {
			return nil, failure("PACKAGE_INTEGRITY_MISMATCH", "Lock differs from captured files; use package validate --structure-only to check edited author structure without certifying capture integrity", "")
		}
		bundle.LockIntegrity = "verified"
	} else if !os.IsNotExist(lockErr) {
		return nil, lockErr
	} else if locked {
		return nil, failure("PACKAGE_LOCK_MISSING", "--locked requires woobe.lock.json", "")
	}
	return bundle, nil
}
