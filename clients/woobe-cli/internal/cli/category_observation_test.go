package cli

import (
	"encoding/json"
	"testing"
)

func TestCategoryObservationBindsIdentityWorkspaceAndRevision(t *testing.T) {
	obj := map[string]any{"id": "c", "workspace_id": "w", "revision": json.Number("2")}
	meta := map[string]string{"etag": `"category:c:2"`}
	if e := verifyCategoryObservation(obj, meta, "w", "c"); e != nil {
		t.Fatal(e)
	}
	for _, etag := range []string{"", `W/"category:c:2"`, `"category:c:1"`, `"category:other:2"`, `"category:c:2147483648"`} {
		if e := verifyCategoryObservation(obj, map[string]string{"etag": etag}, "w", "c"); e == nil {
			t.Fatal(etag)
		}
	}
	if e := verifyCategoryObservation(obj, meta, "other", "c"); e == nil {
		t.Fatal("cross Workspace")
	}
}
