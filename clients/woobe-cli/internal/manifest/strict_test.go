package manifest

import "testing"

func TestManifestDuplicateFields(t *testing.T) {
	_, e := Parse([]byte(`{"schema_version":"1","schema_version":"2","steps":[]}`))
	if e == nil {
		t.Fatal("accepted duplicate")
	}
}
