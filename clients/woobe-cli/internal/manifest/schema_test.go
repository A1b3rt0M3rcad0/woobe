package manifest

import (
	"encoding/json"
	"testing"
)

func TestManifestSchemaVersioned(t *testing.T) {
	b, e := json.Marshal(Schema())
	if e != nil || !json.Valid(b) || Schema()["$id"] != "urn:woobe:manifest:steps:1" {
		t.Fatal(e)
	}
}
