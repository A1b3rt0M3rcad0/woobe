package requestinput

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestYAMLPreservesExactTypesAndOmissions(t *testing.T) {
	data, err := Decode([]byte("description: null\nlarge: 900719925474099312345\nrate: 1.0000000000000000001\nzero: -0\nenabled: false\ntext: '001'\ndate: 2026-10-07\nitems: []\n"), "request.yaml", "auto")
	if err != nil {
		t.Fatal(err)
	}
	decoder := json.NewDecoder(strings.NewReader(string(data)))
	decoder.UseNumber()
	var value map[string]any
	if err := decoder.Decode(&value); err != nil {
		t.Fatal(err)
	}
	if value["large"] != json.Number("900719925474099312345") || value["rate"] != json.Number("1.0000000000000000001") || value["zero"] != json.Number("-0") || value["enabled"] != false || value["text"] != "001" || value["date"] != "2026-10-07" {
		t.Fatal(value)
	}
	if v, exists := value["description"]; !exists || v != nil {
		t.Fatal(value)
	}
	if _, exists := value["name"]; exists {
		t.Fatal("invented omitted field")
	}
}

func TestRejectAmbiguousOrExecutableYAML(t *testing.T) {
	for _, input := range []string{"a: 1\na: 2", "x: {a: 1, a: 2}", "x: &a 1\ny: *a", "x: !custom value", "? [a, b]\n: value", "x: .nan", "x: .inf", "a: 1\n---\nb: 2", "<<: {a: 1}", ""} {
		t.Run(input, func(t *testing.T) {
			if _, err := Decode([]byte(input), "-", "yaml"); err == nil {
				t.Fatalf("accepted %q", input)
			}
		})
	}
	if _, err := Decode([]byte(strings.Repeat("[", 130)+"0"+strings.Repeat("]", 130)), "-", "yaml"); err == nil {
		t.Fatal("accepted excessive depth")
	}
}

func TestExplicitFormatsAndJSONCompatibility(t *testing.T) {
	input := []byte(`{"number":9007199254740993,"description":null}`)
	data, err := Decode(input, "input.json", "auto")
	if err != nil || string(data) != string(input) {
		t.Fatal(string(data), err)
	}
	for _, input := range []string{`{"x":}`, `{"x":1,"x":2}`, `{} {}`} {
		if _, err := Decode([]byte(input), "-", "auto"); err == nil {
			t.Fatal(input)
		}
	}
	if _, err := Decode([]byte("a: 1"), "-", "json"); err == nil {
		t.Fatal("JSON accepted YAML")
	}
	if _, err := Decode([]byte("a: 1"), "-", "xml"); err == nil {
		t.Fatal("accepted unknown format")
	}
}

func TestJSONInYAMLFilesPreservesUnicodeAndExactNumbers(t *testing.T) {
	input := []byte("{\"text\":\"First\u0085Second\",\"emoji\":\"\\ud83d\\ude00\",\"number\":1.0000000000000000001}")
	data, err := Decode(input, "agent.yaml", "auto")
	if err != nil {
		t.Fatal(err)
	}
	decoder := json.NewDecoder(strings.NewReader(string(data)))
	decoder.UseNumber()
	var actual map[string]any
	if err := decoder.Decode(&actual); err != nil {
		t.Fatal(err)
	}
	if actual["text"] != "First\u0085Second" || actual["emoji"] != "😀" || actual["number"] != json.Number("1.0000000000000000001") {
		t.Fatal("changed JSON author input", actual)
	}
}

func FuzzDecode(f *testing.F) {
	f.Add("a: 1\n", "yaml")
	f.Add(`{"a":1}`, "json")
	f.Fuzz(func(t *testing.T, text, format string) {
		if len(text) > MaxBytes {
			return
		}
		data, err := Decode([]byte(text), "-", format)
		if err == nil && !json.Valid(data) {
			t.Fatal("invalid converted JSON")
		}
	})
}
