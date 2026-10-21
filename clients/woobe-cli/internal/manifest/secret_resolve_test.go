package manifest

import "testing"

func TestResolveSecretsDoesNotMutatePlan(t *testing.T) {
	marker := map[string]any{"$secret_ref": "provider"}
	plan := map[string]any{"api_key": marker}
	wire, e := ResolveSecrets(plan, map[string]string{"provider": "fixture-only-secret"})
	if e != nil || wire.(map[string]any)["api_key"] != "fixture-only-secret" {
		t.Fatal(wire, e)
	}
	if _, ok := SecretReference(plan["api_key"]); !ok {
		t.Fatal("plan mutated")
	}
	if _, e := ResolveSecrets(plan, nil); e == nil {
		t.Fatal("missing reference accepted")
	}
}
