package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"strings"
	"testing"
)

func TestEnvironmentCredentialIdentity(t *testing.T) {
	a := New(nil, nil, nil)
	t.Setenv("WOOBE_CONTROL_KEY", "first-secret")
	x, _ := a.credentialFingerprint(config.Context{})
	t.Setenv("WOOBE_CONTROL_KEY", "second-secret")
	y, _ := a.credentialFingerprint(config.Context{})
	if x == y || strings.Contains(x, "secret") || len(x) != 64 {
		t.Fatal("invalid identity binding")
	}
}
