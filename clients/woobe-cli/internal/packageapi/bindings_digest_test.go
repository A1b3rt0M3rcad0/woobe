package packageapi

import "testing"

func TestBindingsDigestMatchesBackendUnicodeWithoutChangingLiteralEscapes(t *testing.T) {
	value := map[string]any{"metadata": map[string]any{"name": "é<>\u2028\\u2028"}, "spec": map[string]any{}}
	digest, err := BindingsDigest(value)
	if err != nil || digest != "a5dc90912b1d55bb4c39567f65ad123caa6c00ee87e7f97fed22168690f1fc75" {
		t.Fatal("backend canonical identity differs", digest, err)
	}
	value["spec"].(map[string]any)["credentials"] = map[string]any{"primary": map[string]any{"protected_ref": "changed-reference"}}
	changed, err := BindingsDigest(value)
	if err != nil || changed == digest {
		t.Fatal("binding identity change was ignored")
	}
}
