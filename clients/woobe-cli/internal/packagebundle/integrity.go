package packagebundle

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"sort"
)

type InventoryFile struct {
	Path      string `json:"path"`
	SizeBytes int64  `json:"size_bytes"`
	SHA256    string `json:"sha256"`
}

func InventoryDigest(inventory []InventoryFile) string {
	return VersionInventoryDigest(inventory, "1.0")
}

func VersionInventoryDigest(inventory []InventoryFile, version string) string {
	sorted := append([]InventoryFile(nil), inventory...)
	sort.Slice(sorted, func(i, j int) bool { return sorted[i].Path < sorted[j].Path })
	tuples := make([][3]any, 0, len(sorted))
	for _, item := range sorted {
		tuples = append(tuples, [3]any{item.Path, item.SizeBytes, item.SHA256})
	}
	var data bytes.Buffer
	encoder := json.NewEncoder(&data)
	encoder.SetEscapeHTML(false)
	// All inventory values are bounded paths, integers and computed digests.
	if err := encoder.Encode(tuples); err != nil {
		panic(err)
	}
	canonical := bytes.TrimSuffix(data.Bytes(), []byte("\n"))
	// encoding/json always escapes JavaScript line separators, even with HTML
	// escaping disabled. Inventory paths forbid backslashes, so restoring these
	// two literals is unambiguous and matches the backend's canonical UTF-8 JSON.
	canonical = bytes.ReplaceAll(canonical, []byte(`\u2028`), []byte("\u2028"))
	canonical = bytes.ReplaceAll(canonical, []byte(`\u2029`), []byte("\u2029"))
	digest := sha256.Sum256(append([]byte("woobe-package@"+version+"\n"), canonical...))
	return hex.EncodeToString(digest[:])
}
