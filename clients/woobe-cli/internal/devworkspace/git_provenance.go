package devworkspace

import (
	"bytes"
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"time"
)

var gitCommitPattern = regexp.MustCompile(`^(?:[a-f0-9]{40}|[a-f0-9]{64})$`)

// VerifyGitRevision compares retained compiler-verified author bytes against
// immutable Git blobs. It neither checks out a branch nor executes repository code.
func (g *Graph) VerifyGitRevision(resource Resource, record *Revision, commit string) error {
	if !gitCommitPattern.MatchString(commit) {
		return fmt.Errorf("supply an exact lowercase Git commit SHA")
	}
	c := g.Config
	object, err := c.ReadAuthorObject(resource, record)
	if err != nil {
		return err
	}
	tracking, err := c.ReadTracking(resource)
	if err != nil {
		return err
	}
	if err = g.validateAuthorExecution(resource, record, object, tracking); err != nil {
		return err
	}
	directory := filepath.Dir(c.File)
	git := func(arguments ...string) ([]byte, error) {
		ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
		defer cancel()
		command := exec.CommandContext(ctx, "git", append([]string{"--no-pager", "--no-replace-objects", "--literal-pathspecs", "-C", directory}, arguments...)...)
		// stderr can contain remote URLs, user paths or hooks. Never echo it.
		raw, err := command.Output()
		if err != nil {
			return nil, fmt.Errorf("Git evidence is unavailable or not a committed blob")
		}
		return raw, nil
	}
	rootRaw, err := git("rev-parse", "--show-toplevel")
	if err != nil {
		return err
	}
	root := filepath.FromSlash(strings.TrimSpace(string(rootRaw)))
	root, err = filepath.EvalSymlinks(root)
	if err != nil {
		return fmt.Errorf("Git worktree identity is unavailable")
	}
	resolved, err := git("rev-parse", "--verify", commit+"^{commit}")
	if err != nil || strings.TrimSpace(string(resolved)) != commit {
		return fmt.Errorf("Git commit identity differs")
	}
	// Validate Git object integrity without replacement refs or reflog origins.
	if _, err = git("fsck", "--strict", "--no-reflogs", "--no-dangling", commit); err != nil {
		return fmt.Errorf("Git object integrity is unavailable")
	}
	writes, err := c.sourceWrites(object)
	if err != nil {
		return err
	}
	// Configuration bytes situate the retained resource paths; formatting is not
	// rewritten into the proof. Source bytes are exactly those sealed in history.
	writes[c.File], err = os.ReadFile(c.File)
	if err != nil {
		return err
	}
	for file, wanted := range writes {
		physicalFile, err := filepath.EvalSymlinks(file)
		if err != nil {
			return fmt.Errorf("Git author file identity is unavailable")
		}
		relative, err := filepath.Rel(root, physicalFile)
		if err != nil || relative == ".." || strings.HasPrefix(relative, ".."+string(filepath.Separator)) {
			return fmt.Errorf("author closure is outside the Git worktree")
		}
		relative = filepath.ToSlash(relative)
		mode, err := git("ls-tree", commit, "--", relative)
		if err != nil || (!bytes.HasPrefix(mode, []byte("100644 blob ")) && !bytes.HasPrefix(mode, []byte("100755 blob "))) {
			return fmt.Errorf("Git author files must be committed regular blobs")
		}
		sizeRaw, err := git("cat-file", "-s", commit+":"+relative)
		if err != nil {
			return err
		}
		size, err := strconv.ParseInt(strings.TrimSpace(string(sizeRaw)), 10, 64)
		if err != nil || size != int64(len(wanted)) {
			return fmt.Errorf("Git commit does not contain the exact retained author closure")
		}
		actual, err := git("show", commit+":"+relative)
		if err != nil {
			return err
		}
		if !bytes.Equal(actual, wanted) {
			return fmt.Errorf("Git commit does not contain the exact retained author closure")
		}
	}
	return nil
}
