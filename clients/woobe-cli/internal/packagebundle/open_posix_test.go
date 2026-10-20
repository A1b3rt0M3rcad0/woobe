//go:build linux || darwin

package packagebundle

import (
	"golang.org/x/sys/unix"
	"os"
	"path/filepath"
	"testing"
)

func TestArchiveRejectsNonRegularAndMultiplyLinkedSources(t *testing.T) {
	dir := t.TempDir()
	fifo := filepath.Join(dir, "fifo.tar.gz")
	if err := unix.Mkfifo(fifo, 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := LoadArchive(fifo, false); err == nil {
		t.Fatal("FIFO accepted")
	}
	regular := filepath.Join(dir, "regular.tar.gz")
	if err := os.WriteFile(regular, []byte("invalid archive"), 0600); err != nil {
		t.Fatal(err)
	}
	link := filepath.Join(dir, "hard.tar.gz")
	if err := os.Link(regular, link); err != nil {
		t.Fatal(err)
	}
	root, err := os.OpenRoot(dir)
	if err != nil {
		t.Fatal(err)
	}
	defer root.Close()
	for _, name := range []string{"regular.tar.gz", "hard.tar.gz"} {
		if file, err := confinedOpen(root, name); err == nil {
			file.Close()
			t.Fatal("multiply linked file accepted")
		}
	}
}
