package manifest

import "testing"

func TestManifestSecretValues(t *testing.T) {
	for _, body := range []string{`{"api_key":"secret"}`, `{"nested":{"password":"secret"}}`} {
		d := Document{Steps: []Step{{ID: "a", Command: "x", Body: []byte(body)}}}
		if _, e := d.Order(); e == nil {
			t.Fatal(body)
		}
	}
	d := Document{Steps: []Step{{ID: "a", Command: "x", Body: []byte(`{"description":null}`)}}}
	if _, e := d.Order(); e != nil {
		t.Fatal(e)
	}
}
