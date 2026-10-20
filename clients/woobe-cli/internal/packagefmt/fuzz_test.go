package packagefmt

import "testing"

func FuzzDecodePackage(f *testing.F) {
	for _, seed := range []string{"{}", "format: woobe-package\nschema_version: \"1.0\"\n", "a: &x [*x]", "{\"a\":1,\"a\":2}", "schema_version: 1.0\n"} {
		f.Add([]byte(seed))
	}
	f.Fuzz(func(t *testing.T, source []byte) {
		if len(source) > MaxDescriptorBytes {
			t.Skip()
		}
		document, err := Decode(source, "fuzz.yaml")
		if err == nil {
			_ = Validate(document)
		}
	})
}

func FuzzReferenceClosure(f *testing.F) {
	f.Add("primary")
	f.Add("missing")
	f.Add("../escape")
	f.Fuzz(func(t *testing.T, reference string) {
		if len(reference) > 512 {
			t.Skip()
		}
		manifest := map[string]any{"spec": map[string]any{"entrypoint": map[string]any{"kind": "Agent", "ref": "support"}, "requires": map[string]any{"credentials": []any{map[string]any{"ref": "key", "provider": "fake"}}}}}
		documents := map[string]*Document{
			"agent.yaml": {Value: map[string]any{"kind": "Agent", "metadata": map[string]any{"key": "support"}, "spec": map[string]any{"model": map[string]any{"primary": map[string]any{"ref": reference}}}}},
			"model.yaml": {Value: map[string]any{"kind": "Model", "metadata": map[string]any{"key": "primary"}, "spec": map[string]any{"provider": "fake", "credential": map[string]any{"ref": "key"}}}},
		}
		graph, err := Resolve(manifest, documents)
		if err == nil && reference != "" && reference != "primary" {
			t.Fatal("unresolved reference accepted", graph)
		}
	})
}

func FuzzPackageLockDocument(f *testing.F) {
	f.Add([]byte(`{"format":"woobe-package","schema_version":"1.0","kind":"PackageLock","algorithm":"sha256","inventory":[],"artifact_digest":"invalid"}`))
	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > 65536 {
			t.Skip()
		}
		document, err := Decode(data, "woobe.lock.json")
		if err == nil {
			_ = Validate(document)
		}
	})
}
