package cli

import (
	"bytes"
	"context"
	"fmt"
	"strings"
	"testing"
)

func TestGitReferenceFirstHelpRoutesBothOwnersWithoutConfigOrNetwork(t *testing.T) {
	t.Chdir(t.TempDir())
	for _, kind := range []string{"agent", "network"} {
		for _, action := range []string{"git-proof", "git-attest"} {
			var out bytes.Buffer
			app := New(strings.NewReader(""), &out, &bytes.Buffer{})
			code := app.Execute(context.Background(), []string{kind, "@support", action, "--help"})
			response := out.String()
			if code != 0 || !strings.Contains(response, action) || strings.Contains(response, "unknown flag") {
				t.Fatal(kind, action, code, response)
			}
		}
	}
}
func TestGitProofRequiresExplicitIdentityWithoutReadingPrivateCredentials(t *testing.T) {
	t.Chdir(t.TempDir())
	code, response := invoke(t, []string{"agent", "@support", "git-proof", "--output", "json"}, "")
	if code != 2 || !strings.Contains(fmt.Sprint(response), "Supply revision") {
		t.Fatal(code, response)
	}
}
