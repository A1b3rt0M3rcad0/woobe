package packagebundle

import (
	"io"
	"os"
)

// ReadConfined reuses the package loader's native stable-file checks for local
// authoring compilers. The returned bytes never broaden a declared root.
func ReadConfined(root *os.Root, path string, limit int64) ([]byte, error) {
	normalized, err := PortablePath(path, "")
	if err != nil || normalized != path {
		return nil, failure("PACKAGE_PATH_INVALID", "File path is not canonical", path)
	}
	f, err := confinedOpen(root, path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	data, err := io.ReadAll(io.LimitReader(f, limit+1))
	if err != nil {
		return nil, err
	}
	if int64(len(data)) > limit {
		return nil, failure("PACKAGE_LIMIT_EXCEEDED", "Declared file exceeds limit", path)
	}
	return data, nil
}
