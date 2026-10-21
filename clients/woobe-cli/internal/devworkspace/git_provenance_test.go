package devworkspace

import (
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
)

func TestGitProofRequiresExactCommittedRetainedAuthorClosure(t *testing.T) {
	if _, err := exec.LookPath("git"); err != nil {
		t.Skip("Git is required for provenance proof")
	}
	c, graph := completeGraph(t)
	resource := graph.Nodes["support"].Resource
	record, err := graph.CreateRevision(resource, authorState(), "sealed author", nil)
	if err != nil {
		t.Fatal(err)
	}
	directory := filepath.Dir(c.File)
	git := func(args ...string) string {
		t.Helper()
		command := exec.Command("git", append([]string{"-C", directory}, args...)...)
		raw, err := command.CombinedOutput()
		if err != nil {
			t.Fatalf("Git fixture failed: %v", err)
		}
		return strings.TrimSpace(string(raw))
	}
	git("init", "-q")
	git("config", "core.autocrlf", "false")
	git("config", "user.name", "ASaC test fixture")
	git("config", "user.email", "fixture@example.invalid")
	git("add", "--", ".")
	git("commit", "-q", "-m", "sealed author fixture")
	commit := git("rev-parse", "HEAD")
	if err = graph.VerifyGitRevision(resource, record, commit); err != nil {
		t.Fatal(err)
	}
	descriptor := filepath.Join(c.RootPath(), graph.Nodes[resource.Key].Descriptor)
	raw, err := os.ReadFile(descriptor)
	if err != nil {
		t.Fatal(err)
	}
	if err = os.WriteFile(descriptor, append(raw, []byte("\n# divergent committed source\n")...), 0600); err != nil {
		t.Fatal(err)
	}
	git("add", "--", ".")
	git("commit", "-q", "-m", "different author bytes")
	divergent := git("rev-parse", "HEAD")
	if err = graph.VerifyGitRevision(resource, record, divergent); err == nil {
		t.Fatal("different Git closure accepted")
	}
	if err = graph.VerifyGitRevision(resource, record, commit); err != nil {
		t.Fatal("original sealed commit should remain verifiable", err)
	}
	// A local replacement ref must not make another commit appear to contain
	// the sealed source under a forged immutable identity.
	git("replace", divergent, commit)
	if err = graph.VerifyGitRevision(resource, record, divergent); err == nil {
		t.Fatal("Git replacement ref forged the committed author closure")
	}
	git("replace", "-d", divergent)
	if err = graph.VerifyGitRevision(resource, record, "HEAD"); err == nil {
		t.Fatal("moving Git reference accepted")
	}
}
