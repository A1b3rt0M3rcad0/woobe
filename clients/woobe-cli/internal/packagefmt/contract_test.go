package packagefmt

import (
	"encoding/json"
	"errors"
	"os"
	"reflect"
	"testing"
)

func TestSharedContractParity(t *testing.T) {
	data, err := os.ReadFile("../../testdata/package/shared/parity.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []struct {
		Name, File, Input, Error string
		Expected                 map[string]any
		Validate                 bool
	}
	if err = json.Unmarshal(data, &cases); err != nil {
		t.Fatal(err)
	}
	for _, c := range cases {
		t.Run(c.Name, func(t *testing.T) {
			document, err := Decode([]byte(c.Input), c.File)
			if err == nil && (c.Validate || c.Name == "minimal-model") {
				err = Validate(document)
			}
			if c.Error != "" {
				var diagnostic *Diagnostic
				if !errors.As(err, &diagnostic) || diagnostic.Code != c.Error {
					t.Fatalf("expected %s, got %v", c.Error, err)
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			normalized, err := json.Marshal(document.Value)
			if err != nil {
				t.Fatal(err)
			}
			var actual map[string]any
			if err = json.Unmarshal(normalized, &actual); err != nil {
				t.Fatal(err)
			}
			if !reflect.DeepEqual(actual, c.Expected) {
				t.Fatalf("normalized mismatch: %#v", actual)
			}
		})
	}
}

func TestEmbeddedCatalogIsOffline(t *testing.T) {
	document, err := Decode([]byte(`{"format":"woobe-package","schema_version":"1.0","kind":"Model","metadata":{"key":"primary","name":"Primary"},"spec":{"provider":"fake","model":"fake","credential":{"ref":"primary"}}}`), "model.json")
	if err != nil {
		t.Fatal(err)
	}
	if err = Validate(document); err != nil {
		t.Fatal(err)
	}
}
