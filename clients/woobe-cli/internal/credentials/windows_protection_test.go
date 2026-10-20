package credentials

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

func TestWindowsProtectionVaultPersistenceAndIsolation(t *testing.T) {
	if !nativeStore {
		t.Skip("Windows native protection")
	}
	store := Store{Dir: t.TempDir()}
	if e := store.Put("private", "fixture"); e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { _ = store.Remove("private") })
	child := exec.Command(os.Args[0], "-test.run=^TestWindowsProtectionVaultChild$")
	child.Env = append(os.Environ(), "WOOBE_TEST_VAULT_DIR="+store.Dir)
	if out, e := child.CombinedOutput(); e != nil {
		t.Fatalf("Credential unavailable after process restart: %s", out)
	}
	restored := Store{Dir: store.Dir}
	v, e := restored.Get("private")
	if e != nil || v != "fixture" {
		t.Fatal("credential did not persist", e)
	}
	if _, e = os.Stat(filepath.Join(store.Dir, "private.json")); !os.IsNotExist(e) {
		t.Fatal("secret written to disk")
	}
	if _, e = (Store{Dir: t.TempDir()}).Get("private"); e == nil {
		t.Fatal("credential leaked across configurations")
	}
	names, e := restored.List()
	if e != nil || len(names) != 1 || names[0] != "private" {
		t.Fatal(names, e)
	}
	if e = restored.Remove("private"); e != nil {
		t.Fatal(e)
	}
	if _, e = restored.Get("private"); e == nil {
		t.Fatal("credential survived logout")
	}
}

func TestWindowsProtectionVaultChild(t *testing.T) {
	dir := os.Getenv("WOOBE_TEST_VAULT_DIR")
	if !nativeStore || dir == "" {
		t.Skip("Child-process vault probe")
	}
	value, err := (Store{Dir: dir}).Get("private")
	if err != nil || value != "fixture" {
		t.Fatal("Credential did not persist across processes")
	}
}

func TestWindowsProtectionMissingCredentialUsesAuthenticationExit(t *testing.T) {
	if !nativeStore {
		t.Skip("Windows native protection")
	}
	_, err := (Store{Dir: t.TempDir()}).Get("missing")
	if err == nil || output.Normalize(err).Code != 3 {
		t.Fatal("missing credential must use authentication exit", err)
	}
}
