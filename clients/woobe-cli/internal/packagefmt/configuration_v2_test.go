package packagefmt

import (
	"strings"
	"testing"
)

func TestConfigurationV2IntentBindingsAndCatalogIsolation(t *testing.T) {
	manifest, err := Decode([]byte(`{"format":"woobe-package","schema_version":"2.0","kind":"Package","metadata":{"name":"Support","version":"1"},"spec":{"entrypoint":{"kind":"Agent","ref":"agent"},"resources":["agent.yaml","model.yaml"],"configuration":{"keys":[{"key":"PRIMARY_KEY"}]},"connections":{"primary":{"provider":"openai","name":"Main","authentication":{"type":"api_key","fields":{"api_key":{"source":"project_environment","key":"PRIMARY_KEY"}}}}}}}`), "woobe.yaml")
	if err != nil {
		t.Fatal(err)
	}
	if err = Validate(manifest); err != nil {
		t.Fatal(err)
	}
	documents := map[string]*Document{}
	for path, content := range map[string]string{
		"agent.yaml": `{"format":"woobe-package","schema_version":"2.0","kind":"Agent","metadata":{"key":"agent","name":"Support"},"spec":{"legacy_system_prompt":"Help","model":{"primary":{"ref":"model"}}}}`,
		"model.yaml": `{"format":"woobe-package","schema_version":"2.0","kind":"Model","metadata":{"key":"model","name":"Main"},"spec":{"provider":"openai","model":"gpt-4o-mini","credential":{"ref":"primary"}}}`,
	} {
		document, err := Decode([]byte(content), path)
		if err != nil {
			t.Fatal(err)
		}
		if err = Validate(document); err != nil {
			t.Fatal(err)
		}
		documents[path] = document
	}
	graph, err := Resolve(manifest.Value, documents)
	if err != nil {
		t.Fatal(err)
	}
	bindings, err := LoadBindings("", nil, graph)
	if err != nil {
		t.Fatal(err)
	}
	spec := Object(bindings["spec"])
	if Object(Object(spec["credentials"])["primary"])["create"] != true || Object(Object(spec["project_environment"])["PRIMARY_KEY"])["create"] != true {
		t.Fatal("new declarations must require creation, never silent reuse")
	}
	bindings, err = LoadBindings("", []string{"configuration.PRIMARY_KEY=SHARED_KEY", "credential.primary=00000000-0000-4000-8000-000000000001"}, graph)
	if err != nil {
		t.Fatal(err)
	}
	if Object(Object(Object(bindings["spec"])["project_environment"])["PRIMARY_KEY"])["existing_key"] != "SHARED_KEY" {
		t.Fatal("explicit binding lost")
	}
	if VersionCatalogDigest("1.0") == VersionCatalogDigest("2.0") || VersionCatalogDigest("3.0") != "" {
		t.Fatal("catalog versions are not isolated")
	}
	documents["model.yaml"].Value["schema_version"] = "1.0"
	if _, err = Resolve(manifest.Value, documents); err == nil {
		t.Fatal("mixed resource versions accepted")
	}
	for _, secret := range []string{`{"source":"legacy_configuration","key":"PRIMARY_KEY","alias_id":"00000000-0000-4000-8000-000000000001"}`, `{"source":"project_environment","key":"PRIMARY_KEY","value":"PRIVATE-CANARY"}`} {
		connection := Object(Object(Object(manifest.Value["spec"])["connections"])["primary"])
		parsed, parseErr := Decode([]byte(secret), "ref.yaml")
		if parseErr != nil {
			t.Fatal(parseErr)
		}
		Object(Object(connection["authentication"])["fields"])["api_key"] = parsed.Value
		err = Validate(manifest)
		if err == nil || strings.Contains(err.Error(), "PRIVATE-CANARY") {
			t.Fatalf("protected value accepted or leaked: %v", err)
		}
	}
}

func TestRouteAuthenticationIsTypedAndRequiresItsOwnDeclaredKey(t *testing.T) {
	tool, err := Decode([]byte(`{"format":"woobe-package","schema_version":"2.0","kind":"Tool","metadata":{"key":"http","name":"Scoped HTTP"},"spec":{"type":"http","config":{"mode":"group","base_url":"https://approved.example","authentication":{"type":"none"},"routes":[{"id":"orders/read","name":"Read orders","description":"Read orders","path":"/orders","authentication":{"type":"bearer","fields":{"token":{"source":"project_environment","key":"ROUTE_TOKEN"}}}}]}}}`), "tool.yaml")
	if err != nil {
		t.Fatal(err)
	}
	if err = Validate(tool); err != nil {
		t.Fatal(err)
	}
	config := Object(Object(tool.Value["spec"])["config"])
	auth := Object(Object(List(config["routes"])[0])["authentication"])
	auth["fields"] = map[string]any{"api_key": map[string]any{"source": "project_environment", "key": "ROUTE_TOKEN"}}
	if err = Validate(tool); err == nil {
		t.Fatal("invalid bearer field accepted for route")
	}
	auth["fields"] = map[string]any{"token": map[string]any{"source": "project_environment", "key": "ROUTE_TOKEN"}}
	manifest, _ := Decode([]byte(`{"format":"woobe-package","schema_version":"2.0","kind":"Package","metadata":{"name":"Support","version":"1"},"spec":{"entrypoint":{"kind":"Agent","ref":"agent"},"resources":["agent.yaml","model.yaml","tool.yaml"],"configuration":{"keys":[{"key":"PRIMARY_KEY"}]},"connections":{"primary":{"provider":"openai","name":"Main","authentication":{"type":"api_key","fields":{"api_key":{"source":"project_environment","key":"PRIMARY_KEY"}}}}}}}`), "woobe.yaml")
	documents := map[string]*Document{"tool.yaml": tool}
	for path, content := range map[string]string{
		"agent.yaml": `{"format":"woobe-package","schema_version":"2.0","kind":"Agent","metadata":{"key":"agent","name":"Support"},"spec":{"legacy_system_prompt":"Help","model":{"primary":{"ref":"model"}},"tools":[{"ref":"http"}]}}`,
		"model.yaml": `{"format":"woobe-package","schema_version":"2.0","kind":"Model","metadata":{"key":"model","name":"Main"},"spec":{"provider":"openai","model":"gpt-4o-mini","credential":{"ref":"primary"}}}`,
	} {
		document, decodeErr := Decode([]byte(content), path)
		if decodeErr != nil {
			t.Fatal(decodeErr)
		}
		documents[path] = document
	}
	if _, err = Resolve(manifest.Value, documents); err == nil {
		t.Fatal("undeclared route key accepted")
	}
	Object(Object(manifest.Value["spec"])["configuration"])["keys"] = []any{map[string]any{"key": "PRIMARY_KEY"}, map[string]any{"key": "ROUTE_TOKEN"}}
	if _, err = Resolve(manifest.Value, documents); err != nil {
		t.Fatal(err)
	}
	tool.Value["schema_version"] = "1.0"
	if err = Validate(tool); err == nil {
		t.Fatal("route authentication silently entered old schema")
	}
}
