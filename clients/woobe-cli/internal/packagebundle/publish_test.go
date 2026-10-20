package packagebundle

import (
	"os"
	"path/filepath"
	"sync"
	"testing"
)

func TestPublicationIsCompleteAndRejectsExistingDestinations(t *testing.T) {
	bundle, err := Load(fixture(t), false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	destination := filepath.Join(t.TempDir(), "export")
	if err = bundle.Publish(destination); err != nil {
		t.Fatal(err)
	}
	verified, err := Load(destination, true)
	if err != nil {
		t.Fatal(err)
	}
	defer verified.Close()
	if verified.ArtifactDigest != bundle.ArtifactDigest {
		t.Fatal("published incomplete package")
	}
	if err = bundle.Publish(destination); err == nil {
		t.Fatal("replaced existing destination")
	}
	empty := filepath.Join(t.TempDir(), "empty")
	if err = os.Mkdir(empty, 0700); err != nil {
		t.Fatal(err)
	}
	if err = bundle.Publish(empty); err == nil {
		t.Fatal("replaced existing empty directory")
	}
}

func TestPublicationRaceHasExactlyOneWinner(t *testing.T) {
	bundle, err := Load(fixture(t), false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	destination := filepath.Join(t.TempDir(), "concurrent-export")
	var workers sync.WaitGroup
	results := make(chan error, 8)
	for range 8 {
		workers.Add(1)
		go func() { defer workers.Done(); results <- bundle.Publish(destination) }()
	}
	workers.Wait()
	close(results)
	winners := 0
	for err := range results {
		if err == nil {
			winners++
		}
	}
	if winners != 1 {
		t.Fatalf("publication winners: %d", winners)
	}
	verified, err := Load(destination, true)
	if err != nil {
		t.Fatal(err)
	}
	verified.Close()
}

func TestCorruptCapturedBytesNeverPublishDestination(t *testing.T) {
	bundle, err := Load(fixture(t), false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	if err = os.WriteFile(filepath.Join(bundle.Root, "agent.yaml"), []byte("changed"), 0600); err != nil {
		t.Fatal(err)
	}
	destination := filepath.Join(t.TempDir(), "incomplete")
	if err = bundle.Publish(destination); err == nil {
		t.Fatal("published changed snapshot")
	}
	if _, err = os.Lstat(destination); !os.IsNotExist(err) {
		t.Fatal("partial destination appeared")
	}
	entries, err := os.ReadDir(filepath.Dir(destination))
	if err != nil || len(entries) != 0 {
		t.Fatal("private staging was left behind", entries, err)
	}
}
