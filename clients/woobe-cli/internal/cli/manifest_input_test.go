package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"testing"
)

func TestManifestConfigurationOnly(t *testing.T) {
	a := New(nil, nil, nil)
	a.completeDiscovery()
	for _, s := range []manifest.Step{{ID: "a", Command: "project agent get", Args: []string{"a"}}, {ID: "a", Command: "project agent create", Body: []byte(`[]`)}} {
		if a.validateManifest(manifest.Document{Steps: []manifest.Step{s}}) == nil {
			t.Fatal(s)
		}
	}
}
