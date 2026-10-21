package packagebundle

import (
	"archive/tar"
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func fixture(t *testing.T) string {
	t.Helper()
	root := t.TempDir()
	files := map[string]string{
		"woobe.yaml":            `{"format":"woobe-package","schema_version":"1.0","kind":"Package","metadata":{"name":"support","version":"1.0.0"},"spec":{"entrypoint":{"kind":"Agent","ref":"support"},"resources":["agent.yaml","model.yaml"],"requires":{"credentials":[{"ref":"primary-key","provider":"openai_compatible"}]}}}`,
		"agent.yaml":            `{"format":"woobe-package","schema_version":"1.0","kind":"Agent","metadata":{"key":"support","name":"Support"},"spec":{"legacy_system_prompt":"Answer","model":{"primary":{"ref":"primary"}}}}`,
		"model.yaml":            `{"format":"woobe-package","schema_version":"1.0","kind":"Model","metadata":{"key":"primary","name":"Primary"},"spec":{"provider":"openai_compatible","model":"fake","credential":{"ref":"primary-key"}}}`,
		"incidental-secret.txt": "never included",
	}
	for path, data := range files {
		if err := os.WriteFile(filepath.Join(root, path), []byte(data), 0600); err != nil {
			t.Fatal(err)
		}
	}
	return root
}

func TestSnapshotAndArchiveKeepTheExactDeclaredBytes(t *testing.T) {
	root := fixture(t)
	bundle, err := Load(root, false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	if len(bundle.Inventory) != 3 {
		t.Fatal("incidental file was included")
	}
	if err = os.WriteFile(filepath.Join(root, "agent.yaml"), []byte("changed"), 0600); err != nil {
		t.Fatal(err)
	}
	var archive bytes.Buffer
	if err = bundle.Archive(&archive, true); err != nil {
		t.Fatal(err)
	}
	received, err := ReceiveArchive(bytes.NewReader(archive.Bytes()), true)
	if err != nil {
		t.Fatal(err)
	}
	defer received.Close()
	if received.ArtifactDigest != bundle.ArtifactDigest {
		t.Fatal("snapshot changed")
	}
}

func TestLockIsRequiredWithoutImplicitRewriting(t *testing.T) {
	root := fixture(t)
	if _, err := Load(root, true); err == nil {
		t.Fatal("missing lock accepted")
	}
	bundle, err := Load(root, false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	data, err := json.Marshal(bundle.Lock())
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(filepath.Join(root, "woobe.lock.json"), data, 0600); err != nil {
		t.Fatal(err)
	}
	locked, err := Load(root, true)
	if err != nil {
		t.Fatal(err)
	}
	locked.Close()
	file, err := os.OpenFile(filepath.Join(root, "agent.yaml"), os.O_APPEND|os.O_WRONLY, 0600)
	if err != nil {
		t.Fatal(err)
	}
	file.WriteString("\n")
	file.Close()
	if _, err = Load(root, true); err == nil {
		t.Fatal("tamper accepted")
	}
	actual, err := os.ReadFile(filepath.Join(root, "woobe.lock.json"))
	if err != nil || !bytes.Equal(data, actual) {
		t.Fatal("lock rewritten")
	}
}

func TestNonportablePaths(t *testing.T) {
	for _, path := range []string{"../escape", "/absolute", "C:/drive", `a\b`, "CON.txt", "a/NUL", "a:stream", ".git/config", "trailing.", "trailing "} {
		t.Run(path, func(t *testing.T) {
			if _, err := PortablePath(path, ""); err == nil {
				t.Fatal("path accepted")
			}
		})
	}
	if path, err := PortablePath("../documents/policy.md", "knowledge/main.yaml"); err != nil || path != "documents/policy.md" {
		t.Fatal(path, err)
	}
}

func TestMaliciousArchiveEntries(t *testing.T) {
	for _, kind := range []byte{tar.TypeSymlink, tar.TypeLink, tar.TypeChar} {
		t.Run(string(kind), func(t *testing.T) {
			var data bytes.Buffer
			zip := gzip.NewWriter(&data)
			archive := tar.NewWriter(zip)
			archive.WriteHeader(&tar.Header{Name: "alias", Typeflag: kind, Linkname: "../escape", Mode: 0600})
			archive.Close()
			zip.Close()
			if _, err := ReceiveArchive(bytes.NewReader(data.Bytes()), false); err == nil {
				t.Fatal("special entry accepted")
			}
		})
	}
}

func TestGoldenInventoryDigest(t *testing.T) {
	hash := func(data string) string { value := sha256.Sum256([]byte(data)); return hex.EncodeToString(value[:]) }
	inventory := []InventoryFile{{"a", 1, hash("x")}, {"b", 2, hash("yz")}}
	tuples := [][3]any{{"a", int64(1), hash("x")}, {"b", int64(2), hash("yz")}}
	encoded, err := json.Marshal(tuples)
	if err != nil {
		t.Fatal(err)
	}
	expected := sha256.Sum256(append([]byte("woobe-package@1.0\n"), encoded...))
	if InventoryDigest(inventory) != hex.EncodeToString(expected[:]) {
		t.Fatal("golden mismatch")
	}
	inventory[0], inventory[1] = inventory[1], inventory[0]
	if InventoryDigest(inventory) != hex.EncodeToString(expected[:]) {
		t.Fatal("order changed hash")
	}
}

func FuzzPortablePath(f *testing.F) {
	for _, path := range []string{"agent.yaml", "../escape", "skills/a/SKILL.md", "C:/a"} {
		f.Add(path)
	}
	f.Fuzz(func(t *testing.T, value string) {
		path, err := PortablePath(value, "")
		if err == nil {
			if filepath.IsAbs(path) || path == ".." {
				t.Fatal("escaped")
			}
		}
	})
}

func TestInventoryCanonicalUTF8MatchesBackendForLineSeparators(t *testing.T) {
	inventory := []InventoryFile{{Path: "notes/line\u2028separator\u2029.md", SizeBytes: 3, SHA256: strings.Repeat("0", 64)}}
	const expected = "e6743f6ed9c9a1de959e987a7fec303a5559b4bf9972e273438c6426378ec890"
	if InventoryDigest(inventory) != expected {
		t.Fatal("cross-language canonical UTF-8 digest mismatch")
	}
}

func TestCompleteSharedCompositionFixtureAndInventory(t *testing.T) {
	data, err := os.ReadFile("../../testdata/package/shared/complete.json")
	if err != nil {
		t.Fatal(err)
	}
	var fixture struct {
		Files map[string]string `json:"files"`
	}
	if err = json.Unmarshal(data, &fixture); err != nil {
		t.Fatal(err)
	}
	root := t.TempDir()
	for relative, content := range fixture.Files {
		path := filepath.Join(root, filepath.FromSlash(relative))
		if err = os.MkdirAll(filepath.Dir(path), 0700); err != nil {
			t.Fatal(err)
		}
		if err = os.WriteFile(path, []byte(content), 0600); err != nil {
			t.Fatal(err)
		}
	}
	bundle, err := Load(root, false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	if len(bundle.Inventory) != len(fixture.Files) {
		t.Fatal("full closure was not captured")
	}
	var archive bytes.Buffer
	if err = bundle.Archive(&archive, true); err != nil {
		t.Fatal(err)
	}
	restored, err := ReceiveArchive(bytes.NewReader(archive.Bytes()), true)
	if err != nil {
		t.Fatal(err)
	}
	defer restored.Close()
	if restored.ArtifactDigest != bundle.ArtifactDigest {
		t.Fatal("full fixture changed in locked archive")
	}
}

func FuzzLockedArchive(f *testing.F) {
	f.Add([]byte("invalid gzip"))
	f.Add([]byte{0x1f, 0x8b, 8, 0, 0, 0, 0, 0, 0, 0})
	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > 65536 {
			t.Skip()
		}
		bundle, err := ReceiveArchive(bytes.NewReader(data), true)
		if err == nil {
			defer bundle.Close()
			if len(bundle.Inventory) == 0 {
				t.Fatal("empty locked composition")
			}
		}
	})
}
