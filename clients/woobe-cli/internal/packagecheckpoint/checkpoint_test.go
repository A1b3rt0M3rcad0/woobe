package packagecheckpoint

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"
)

func fixture() Checkpoint {
	now := time.Now().UTC()
	return Checkpoint{Format: "woobe-package-checkpoint", SchemaVersion: "1.0", APIOrigin: "https://api.example.com", ProjectID: "project", ArtifactDigest: strings.Repeat("a", 64), UploadID: "upload", PlanID: "plan", PlanDigest: strings.Repeat("b", 64), IdempotencyKey: "stable-import", PrincipalFingerprint: strings.Repeat("c", 64), RequestIdentity: strings.Repeat("d", 64), Lifecycle: "draft", State: Prepared, CreatedAt: now, UpdatedAt: now}
}

func TestCheckpointIsDistinctStrictAndCannotCarryProtectedFields(t *testing.T) {
	valid := fixture()
	data, _ := json.Marshal(valid)
	if _, err := Parse(data); err != nil {
		t.Fatal(err)
	}
	for _, malformed := range [][]byte{
		[]byte(`{"schema_version":1,"steps":{}}`),
		[]byte(`{"format":"woobe-package-checkpoint","format":"woobe-manifest"}`),
		append(data[:len(data)-1], []byte(`,"authorization":"credential"}`)...),
		append(data[:len(data)-1], []byte(`,"secret_hash":"private-value-hash"}`)...),
	} {
		if _, err := Parse(malformed); err == nil {
			t.Fatal("accepted unsafe checkpoint")
		}
	}
}

func TestCheckpointPersistsBeforeRequestAndSurvivesUnknownOutcome(t *testing.T) {
	if runtime.GOOS != "linux" && runtime.GOOS != "darwin" && runtime.GOOS != "windows" {
		t.Skip("protection modality unsupported")
	}
	path := filepath.Join(t.TempDir(), "import.json")
	store, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	cp := fixture()
	if err = store.Save(cp); err != nil {
		t.Fatal(err)
	}
	if _, err = Open(path); err == nil {
		t.Fatal("checkpoint had two writers")
	}
	if err = cp.Move(RequestInFlight); err != nil {
		t.Fatal(err)
	}
	if err = store.Save(cp); err != nil {
		t.Fatal(err)
	}
	store.Close()
	store, err = Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	loaded, err := store.Read()
	if err != nil || loaded.State != RequestInFlight {
		t.Fatal(loaded, err)
	}
	if err = loaded.Move(OutcomeUnknown); err != nil {
		t.Fatal(err)
	}
	if err = store.Save(loaded); err != nil {
		t.Fatal(err)
	}
	// A recovered receipt attaches its operation; it never invents a replacement key.
	loaded.OperationID = "accepted-operation"
	if err = loaded.Move(Accepted); err != nil {
		t.Fatal(err)
	}
	if err = store.Save(loaded); err != nil {
		t.Fatal(err)
	}
	changed := loaded
	changed.IdempotencyKey = "different-key"
	if err = store.Save(changed); err == nil {
		t.Fatal("replaced operation identity")
	}
	changed = loaded
	changed.State = Prepared
	if err = store.Save(changed); err == nil {
		t.Fatal("rolled back accepted checkpoint")
	}
	loaded.LastRemoteState = "succeeded"
	loaded.LastRevision = 8
	if err = loaded.Move(Terminal); err != nil {
		t.Fatal(err)
	}
	if err = store.Save(loaded); err != nil {
		t.Fatal(err)
	}
	info, _ := os.Stat(path)
	if !privateMode(info) {
		t.Fatal("public checkpoint")
	}
}

func TestCheckpointNeverOverwritesOtherFormatsOrFollowsSymlinks(t *testing.T) {
	if runtime.GOOS != "linux" && runtime.GOOS != "darwin" && runtime.GOOS != "windows" {
		t.Skip("protection modality unsupported")
	}
	path := filepath.Join(t.TempDir(), "other.json")
	before := []byte(`{"format":"woobe-manifest"}`)
	if err := os.WriteFile(path, before, 0600); err != nil {
		t.Fatal(err)
	}
	store, err := Open(path)
	if err != nil {
		t.Fatal(err)
	}
	if err = store.Save(fixture()); err == nil {
		t.Fatal("overwrote non-package file")
	}
	store.Close()
	after, _ := os.ReadFile(path)
	if string(before) != string(after) {
		t.Fatal("file changed")
	}
	symlink := filepath.Join(t.TempDir(), "alias.json")
	if err = os.Symlink(path, symlink); err != nil {
		t.Fatal(err)
	}
	store, err = Open(symlink)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	if _, err = store.Read(); err == nil {
		t.Fatal("followed checkpoint symlink")
	}
}

func FuzzCheckpointStrictParsing(f *testing.F) {
	data, _ := json.Marshal(fixture())
	f.Add(data)
	f.Add([]byte(`{"format":"woobe-manifest"}`))
	f.Fuzz(func(t *testing.T, data []byte) {
		cp, err := Parse(data)
		if err == nil && cp.Validate() != nil {
			t.Fatal("accepted invalid identity")
		}
	})
}

func TestCheckpointUsesCapturedParentAfterReplacement(t *testing.T) {
	if runtime.GOOS != "linux" && runtime.GOOS != "darwin" && runtime.GOOS != "windows" {
		t.Skip("native protection")
	}
	base := t.TempDir()
	parent := filepath.Join(base, "chosen")
	if err := os.Mkdir(parent, 0700); err != nil {
		t.Fatal(err)
	}
	store, err := Open(filepath.Join(parent, "import.json"))
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	cp := fixture()
	if err = store.Save(cp); err != nil {
		t.Fatal(err)
	}
	captured := filepath.Join(base, "captured")
	if err = os.Rename(parent, captured); err != nil {
		if runtime.GOOS != "windows" {
			t.Fatal(err)
		}
		// Windows pins the directory handle against deletion/rename. A blocked
		// replacement is also confinement: subsequent writes stay in that root.
		if err = cp.Move(RequestInFlight); err != nil {
			t.Fatal(err)
		}
		if err = store.Save(cp); err != nil {
			t.Fatal(err)
		}
		recovered, err := store.Read()
		if err != nil || recovered.State != RequestInFlight {
			t.Fatal("lost pinned checkpoint", err)
		}
		if _, err = os.Stat(captured); !os.IsNotExist(err) {
			t.Fatal("replacement unexpectedly exists", err)
		}
		return
	}
	if err = os.Mkdir(parent, 0700); err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(filepath.Join(parent, "import.json"), []byte("unrelated"), 0600); err != nil {
		t.Fatal(err)
	}
	if err = cp.Move(RequestInFlight); err != nil {
		t.Fatal(err)
	}
	if err = store.Save(cp); err != nil {
		t.Fatal(err)
	}
	wrong, err := os.ReadFile(filepath.Join(parent, "import.json"))
	if err != nil || string(wrong) != "unrelated" {
		t.Fatal("changed replacement parent", err)
	}
	data, err := os.ReadFile(filepath.Join(captured, "import.json"))
	if err != nil {
		t.Fatal(err)
	}
	recovered, err := Parse(data)
	if err != nil || recovered.State != RequestInFlight {
		t.Fatal("lost captured checkpoint", err)
	}
}
