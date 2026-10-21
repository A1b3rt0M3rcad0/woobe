package asac

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

func TestSharedPythonGoDigests(t *testing.T) {
	data, err := os.ReadFile("testdata/asac-digests.json")
	if err != nil {
		t.Fatal(err)
	}
	var cases []struct {
		Scope  string `json:"scope"`
		JSON   string `json:"json"`
		Digest string `json:"digest"`
	}
	if err = json.Unmarshal(data, &cases); err != nil {
		t.Fatal(err)
	}
	for _, c := range cases {
		d := json.NewDecoder(strings.NewReader(c.JSON))
		d.UseNumber()
		var v any
		if err = d.Decode(&v); err != nil {
			t.Fatal(err)
		}
		digest, err := Digest(c.Scope, v)
		if err != nil || digest != c.Digest {
			t.Fatalf("%s: %s != %s: %v", c.JSON, digest, c.Digest, err)
		}
	}
}

func TestDigestNormalizesNumbersButPreservesTypes(t *testing.T) {
	a, _ := Digest("definition", map[string]any{"n": json.Number("1.00")})
	b, _ := Digest("definition", map[string]any{"n": json.Number("1e0")})
	c, _ := Digest("definition", map[string]any{"n": "1"})
	if a != b || a == c {
		t.Fatal("numeric equivalence or string identity changed")
	}
}

func TestDigestRejectsUnboundedNumbers(t *testing.T) {
	for _, number := range []string{"1e999999999", "1e-999999999", strings.Repeat("9", 4097)} {
		if _, err := Digest("definition", json.Number(number)); err == nil {
			t.Fatal("unbounded number accepted", number[:10])
		}
	}
}
