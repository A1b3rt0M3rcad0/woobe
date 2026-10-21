package cli

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
)

func TestPackageEditableCopyAndNewSealRetainCapturedSource(t *testing.T) {
	source := localPackageFixture(t)
	bundle, err := packagebundle.Load(source, false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	sealed := filepath.Join(t.TempDir(), "captured")
	if err = bundle.Publish(sealed); err != nil {
		t.Fatal(err)
	}
	lock, _ := os.ReadFile(filepath.Join(sealed, "woobe.lock.json"))
	author := filepath.Join(t.TempDir(), "author")
	if code, result := invoke(t, []string{"package", "edit", sealed, "--destination", author}, ""); code != 0 {
		t.Fatal(code, result)
	}
	if _, err = os.Stat(filepath.Join(author, "woobe.lock.json")); !os.IsNotExist(err) {
		t.Fatal("author kept old lock", err)
	}
	p := filepath.Join(author, "agent.yaml")
	raw, _ := os.ReadFile(p)
	if err = os.WriteFile(p, append([]byte("# edited author\n"), raw...), 0600); err != nil {
		t.Fatal(err)
	}
	if code, result := invoke(t, []string{"package", "validate", author}, ""); code != 0 {
		t.Fatal(code, result)
	}
	if code, _ := invoke(t, []string{"package", "validate", author, "--locked"}, ""); code != 2 {
		t.Fatal(code)
	}
	newSeal := filepath.Join(t.TempDir(), "new-seal")
	if code, result := invoke(t, []string{"package", "seal", author, "--destination", newSeal}, ""); code != 0 {
		t.Fatal(code, result)
	}
	if code, result := invoke(t, []string{"package", "validate", newSeal, "--locked"}, ""); code != 0 {
		t.Fatal(code, result)
	}
	newLock, _ := os.ReadFile(filepath.Join(newSeal, "woobe.lock.json"))
	if string(lock) == string(newLock) {
		t.Fatal("edited bytes reused old lock")
	}
	original, _ := os.ReadFile(filepath.Join(sealed, "woobe.lock.json"))
	if string(lock) != string(original) {
		t.Fatal("source lock changed")
	}
	if code, result := invoke(t, []string{"package", "edit", sealed, "--destination", author}, ""); code != 2 {
		t.Fatal(code, result)
	}
	if err = os.WriteFile(filepath.Join(sealed, "agent.yaml"), []byte("changed"), 0600); err != nil {
		t.Fatal(err)
	}
	invalidCopy := filepath.Join(t.TempDir(), "invalid-copy")
	if code, result := invoke(t, []string{"package", "edit", sealed, "--destination", invalidCopy}, ""); code != 2 {
		t.Fatal(code, result)
	}
	if _, err = os.Stat(invalidCopy); !os.IsNotExist(err) {
		t.Fatal("tampered capture copied", err)
	}
}
