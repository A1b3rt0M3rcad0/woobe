//go:build windows

package credentials

import (
	"crypto/sha256"
	"fmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"golang.org/x/sys/windows"
	"path/filepath"
	"sort"
	"strings"
	"unsafe"
)

const nativeStore = true

var vaultDLL = windows.NewLazySystemDLL("advapi32.dll")
var credWrite = vaultDLL.NewProc("CredWriteW")
var credRead = vaultDLL.NewProc("CredReadW")
var credDelete = vaultDLL.NewProc("CredDeleteW")
var credEnumerate = vaultDLL.NewProc("CredEnumerateW")
var credFree = vaultDLL.NewProc("CredFree")

type vaultCredential struct {
	Flags, Type             uint32
	TargetName, Comment     *uint16
	LastWritten             windows.Filetime
	BlobSize                uint32
	Blob                    *byte
	Persist, AttributeCount uint32
	Attributes              unsafe.Pointer
	TargetAlias, UserName   *uint16
}

func (s Store) vaultPrefix() (string, error) {
	dir, e := filepath.Abs(s.Dir)
	if e != nil {
		return "", e
	}
	sum := sha256.Sum256([]byte(strings.ToLower(filepath.Clean(dir))))
	return fmt.Sprintf("woobe-cli/%x/", sum), nil
}
func (s Store) vaultTarget(name string) (*uint16, error) {
	p, e := s.vaultPrefix()
	if e != nil {
		return nil, e
	}
	return windows.UTF16PtrFromString(p + name)
}
func (s Store) nativePut(name, value string) error {
	if len(value) > 2560 {
		return fmt.Errorf("Windows credential exceeds 2560 bytes")
	}
	target, e := s.vaultTarget(name)
	if e != nil {
		return e
	}
	blob := []byte(value)
	c := vaultCredential{Type: 1, TargetName: target, BlobSize: uint32(len(blob)), Blob: &blob[0], Persist: 2}
	r, _, e := credWrite.Call(uintptr(unsafe.Pointer(&c)), 0)
	if r == 0 {
		return fmt.Errorf("Windows Credential Manager write failed: %w", e)
	}
	return nil
}
func (s Store) nativeGet(name string) (string, error) {
	target, e := s.vaultTarget(name)
	if e != nil {
		return "", e
	}
	var c *vaultCredential
	r, _, e := credRead.Call(uintptr(unsafe.Pointer(target)), 1, 0, uintptr(unsafe.Pointer(&c)))
	if r == 0 {
		return "", &output.Error{Code: 3, Message: "Windows credential unavailable", Cause: e}
	}
	defer credFree.Call(uintptr(unsafe.Pointer(c)))
	if c == nil || c.BlobSize == 0 || c.BlobSize > 2560 || c.Blob == nil {
		return "", output.New(3, "Invalid Windows credential")
	}
	value := strings.TrimSpace(string(unsafe.Slice(c.Blob, int(c.BlobSize))))
	if value == "" {
		return "", output.New(3, "Windows credential unavailable")
	}
	return value, nil
}
func (s Store) nativeRemove(name string) error {
	target, e := s.vaultTarget(name)
	if e != nil {
		return e
	}
	r, _, e := credDelete.Call(uintptr(unsafe.Pointer(target)), 1, 0)
	if r == 0 && e != windows.ERROR_NOT_FOUND {
		return fmt.Errorf("Windows credential removal failed: %w", e)
	}
	return nil
}
func (s Store) nativeList() ([]string, error) {
	prefix, e := s.vaultPrefix()
	if e != nil {
		return nil, e
	}
	filter, e := windows.UTF16PtrFromString(prefix + "*")
	if e != nil {
		return nil, e
	}
	var count uint32
	var entries **vaultCredential
	r, _, e := credEnumerate.Call(uintptr(unsafe.Pointer(filter)), 0, uintptr(unsafe.Pointer(&count)), uintptr(unsafe.Pointer(&entries)))
	if r == 0 {
		if e == windows.ERROR_NOT_FOUND {
			return []string{}, nil
		}
		return nil, fmt.Errorf("Windows credential enumeration failed: %w", e)
	}
	defer credFree.Call(uintptr(unsafe.Pointer(entries)))
	if count > 100000 {
		return nil, fmt.Errorf("Too many credentials")
	}
	out := []string{}
	for _, c := range unsafe.Slice(entries, int(count)) {
		target := windows.UTF16PtrToString(c.TargetName)
		name := strings.TrimPrefix(target, prefix)
		if strings.HasPrefix(target, prefix) && valid.MatchString(name) {
			out = append(out, name)
		}
	}
	sort.Strings(out)
	return out, nil
}
