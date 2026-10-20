package cli

import (
	"archive/tar"
	"compress/gzip"
	"os"
	"path/filepath"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
)

func TestPackageStructureOnlySeparatesEditedAuthorFromCaptureIntegrity(t *testing.T) {
	bundle, err := packagebundle.Load(localPackageFixture(t), false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	captured := filepath.Join(t.TempDir(), "captured")
	if err = bundle.Publish(captured); err != nil {
		t.Fatal(err)
	}
	lock, err := os.ReadFile(filepath.Join(captured, "woobe.lock.json"))
	if err != nil {
		t.Fatal(err)
	}
	path := filepath.Join(captured, "agent.yaml")
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	edited := append([]byte("# local author edit\n"), raw...)
	if err = os.WriteFile(path, edited, 0600); err != nil {
		t.Fatal(err)
	}
	// Preserve the stale capture lock in the archive, exactly as in a copied
	// export. Transport safety is independent of author structure/integrity.
	archive := filepath.Join(t.TempDir(), "edited.tar.gz")
	f, err := os.Create(archive)
	if err != nil {
		t.Fatal(err)
	}
	gz := gzip.NewWriter(f)
	tw := tar.NewWriter(gz)
	for _, name := range []string{"woobe.yaml", "agent.yaml", "model.yaml", "woobe.lock.json"} {
		data, err := os.ReadFile(filepath.Join(captured, name))
		if err != nil {
			t.Fatal(err)
		}
		if err = tw.WriteHeader(&tar.Header{Name: name, Size: int64(len(data)), Mode: 0600}); err != nil {
			t.Fatal(err)
		}
		if _, err = tw.Write(data); err != nil {
			t.Fatal(err)
		}
	}
	for _, closer := range []interface{ Close() error }{tw, gz, f} {
		if err = closer.Close(); err != nil {
			t.Fatal(err)
		}
	}
	for _, source := range []string{captured, filepath.Join(captured, "woobe.yaml"), archive} {
		for _, format := range []string{"json", "compact"} {
			code, result := invoke(t, []string{"package", "validate", source, "--structure-only", "--output", format}, "")
			if code != 0 {
				t.Fatal(code, result)
			}
			data := result["data"].(map[string]any)
			if data["valid"] != true || data["validation_mode"] != "structure_only" || data["capture_integrity"] != "not_evaluated" || data["semantic_validation"] != "server_required" {
				t.Fatal(result)
			}
		}
		for _, flags := range [][]string{nil, {"--locked"}, {"--structure-only", "--locked"}} {
			if code, result := invoke(t, append([]string{"package", "validate", source}, flags...), ""); code != 2 {
				t.Fatal(code, result)
			}
		}
	}
	gotLock, _ := os.ReadFile(filepath.Join(captured, "woobe.lock.json"))
	gotAuthor, _ := os.ReadFile(path)
	if string(gotLock) != string(lock) || string(gotAuthor) != string(edited) {
		t.Fatal("validation modified the source")
	}
	// Schema/reference checks still run while capture integrity is skipped.
	for _, bad := range []string{"a: 1\na: 2\n", `{"format":"woobe-package","schema_version":"1.0","kind":"Agent","metadata":{"key":"support","name":"Support"},"spec":{"model":{"primary":{"ref":"missing-model"}}}}`} {
		if err = os.WriteFile(path, []byte(bad), 0600); err != nil {
			t.Fatal(err)
		}
		if code, result := invoke(t, []string{"package", "validate", captured, "--structure-only"}, ""); code != 2 {
			t.Fatal(code, result)
		}
	}
}

func TestPackageStructureOnlyCannotDisableIntegrityOnWrites(t *testing.T) {
	for _, command := range []string{"plan", "import", "seal", "edit"} {
		if code, result := invoke(t, []string{"package", command, localPackageFixture(t), "--structure-only"}, ""); code != 2 {
			t.Fatal(code, result)
		}
	}
}
