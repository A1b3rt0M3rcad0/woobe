package output

import (
	"encoding/json"
	"reflect"
	"strings"
	"testing"
)

func TestNestedTypedSecrets(t *testing.T) {
	v := struct {
		Body json.RawMessage `json:"body"`
	}{json.RawMessage(`{"password":"never-output","nested":{"access_token":"never-output"}}`)}
	b, _ := json.Marshal(Redact(v))
	if strings.Contains(string(b), "never-output") {
		t.Fatal(string(b))
	}
}

func TestFencingCounterExceptionNeverExposesTextualTokensOrOtherCredentials(t *testing.T) {
	for _, value := range []any{json.Number("1"), json.Number("9223372036854775807"), int(2), int64(3), uint64(4), float64(5)} {
		data := Redact(map[string]any{"fencing_token": value, "access_token": "private-access", "nested": map[string]any{"provider_token": "private-provider"}}).(map[string]any)
		if data["fencing_token"] != value {
			t.Fatal("Concurrency counter hidden", data)
		}
		raw, _ := json.Marshal(data)
		if strings.Contains(string(raw), "private-") {
			t.Fatal("Credential disclosed", string(raw))
		}
	}
	for _, value := range []any{"private-provider-secret", "123", json.Number("1.2"), json.Number("9223372036854775808"), json.Number("1e3"), float64(1.5), float64(0), int(-1), true, nil, map[string]any{"value": "private-token"}} {
		data := Redact(map[string]any{"fencing_token": value, "Fencing_Token": "private-token"}).(map[string]any)
		if data["fencing_token"] != "[REDACTED]" || data["Fencing_Token"] != "[REDACTED]" {
			t.Fatal("Textual/invalid token exposed", data)
		}
	}
}

func TestAuthenticationReferenceMetadataSurvivesWhileMaterialAndLookalikesDoNot(t *testing.T) {
	for _, source := range []string{"project_environment", "legacy_configuration"} {
		ref := map[string]any{"source": source, "key": "PROVIDER_TOKEN"}
		if source == "legacy_configuration" {
			ref["alias_id"] = "00000000-0000-4000-8000-000000000001"
		}
		auth := map[string]any{"type": "bearer", "fields": map[string]any{"token": ref}}
		data := Redact(map[string]any{"config": map[string]any{"authentication": auth}, "token": ref}).(map[string]any)
		got := data["config"].(map[string]any)["authentication"].(map[string]any)["fields"].(map[string]any)["token"]
		if !reflect.DeepEqual(got, ref) || data["token"] != "[REDACTED]" {
			t.Fatal(data)
		}
		ref["value"] = "private-reference-canary"
		encoded, _ := json.Marshal(Redact(map[string]any{"config": map[string]any{"authentication": auth}}))
		if strings.Contains(string(encoded), "private-reference-canary") {
			t.Fatal("material leaked")
		}
	}
}
