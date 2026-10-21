package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestCheckpointReadBound(t *testing.T) {
	p := filepath.Join(t.TempDir(), "cp")
	f, e := os.Create(p)
	if e != nil {
		t.Fatal(e)
	}
	if e = f.Truncate(32<<20 + 1); e != nil {
		t.Fatal(e)
	}
	f.Close()
	if _, e = readCheckpoint(p); e == nil {
		t.Fatal("oversize read")
	}
}

func TestCheckpointPlanIDs(t *testing.T) {
	d := manifest.Document{Steps: []manifest.Step{{ID: "a"}}}
	if validateCheckpointPlan(checkpoint{Steps: map[string]string{"other": "unknown"}}, d) == nil {
		t.Fatal("foreign step")
	}
}

func TestCheckpointEvidenceOwnership(t *testing.T) {
	d := manifest.Document{Steps: []manifest.Step{{ID: "a"}}}
	for _, cp := range []checkpoint{{Steps: map[string]string{}, Results: map[string]any{"other": 1}}, {Steps: map[string]string{"a": "committed"}, Reconciliations: map[string]Reconciliation{"a": {}}}} {
		if validateCheckpointPlan(cp, d) == nil {
			t.Fatal(cp)
		}
	}
}

func TestTerminalResultPresence(t *testing.T) {
	d := manifest.Document{Steps: []manifest.Step{{ID: "a"}}}
	cp := checkpoint{Steps: map[string]string{"a": "committed"}}
	if validateCheckpointPlan(cp, d) == nil {
		t.Fatal("missing result")
	}
	cp.Results = map[string]any{"a": nil}
	if e := validateCheckpointPlan(cp, d); e != nil {
		t.Fatal(e)
	}
}

func TestCheckpointDependencyStates(t *testing.T) {
	d := manifest.Document{Steps: []manifest.Step{{ID: "a"}, {ID: "b", DependsOn: []string{"a"}}}}
	cp := checkpoint{Steps: map[string]string{"a": "unknown", "b": "committed"}, Results: map[string]any{"b": nil}}
	if validateCheckpointPlan(cp, d) == nil {
		t.Fatal("missing dependency acceptance")
	}
}

func TestNotAttemptedStateIsResumable(t *testing.T) {
	if _, e := parseCheckpoint([]byte(`{"steps":{"a":"not_attempted"}}`)); e != nil {
		t.Fatal(e)
	}
}

func TestOversizedCheckpointDoesNotReplaceExistingFile(t *testing.T) {
	p := filepath.Join(t.TempDir(), "cp")
	before := []byte(`{"steps":{}}`)
	if e := os.WriteFile(p, before, 0600); e != nil {
		t.Fatal(e)
	}
	cp := checkpoint{Steps: map[string]string{}, Results: map[string]any{"a": strings.Repeat("x", 32<<20)}}
	if saveCheckpoint(p, cp) == nil {
		t.Fatal("oversized save")
	}
	after, e := os.ReadFile(p)
	if e != nil || string(after) != string(before) {
		t.Fatal(e, string(after))
	}
}
