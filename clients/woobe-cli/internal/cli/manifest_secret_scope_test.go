package cli

import "testing"

func TestManifestSecretsRestrictedToCredentialConfiguration(t *testing.T) {
	for _, command := range []string{"project agent create", "project tool create", "project provider-credential create"} {
		body := `{"schema_version":"1","project_id":"p","steps":[{"id":"s","command":"` + command + `","body":{"api_key":{"$secret_ref":"provider"}}}]}`
		code, _ := invoke(t, []string{"manifest", "validate", "--file", "-"}, body)
		if command == "project agent create" && code != 2 {
			t.Fatal(command, code)
		}
		if command != "project agent create" && code != 0 {
			t.Fatal(command, code)
		}
	}
}
