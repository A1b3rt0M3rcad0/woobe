package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"strings"
	"testing"
)

func TestCheckpointSecretBindingsAreStrict(t *testing.T) {
	for _, raw := range []string{`{"steps":{},"secret_fingerprints":{"../x":"` + strings.Repeat("0", 64) + `"}}`, `{"steps":{},"secret_fingerprints":{"ok":"short"}}`} {
		if _, e := parseCheckpoint([]byte(raw)); e == nil {
			t.Fatal(raw)
		}
	}
	d, e := manifest.Parse([]byte(`{"schema_version":"1","steps":[{"id":"s","command":"project tool create","body":{"api_key":{"$secret_ref":"one"}}}]}`))
	if e != nil {
		t.Fatal(e)
	}
	for _, hashes := range []map[string]string{nil, {"other": strings.Repeat("0", 64)}} {
		if validateCheckpointPlan(checkpoint{SecretFingerprints: hashes}, d) == nil {
			t.Fatal("invalid binding accepted")
		}
	}
	if e := validateCheckpointPlan(checkpoint{SecretFingerprints: map[string]string{"one": strings.Repeat("0", 64)}}, d); e != nil {
		t.Fatal(e)
	}
}
