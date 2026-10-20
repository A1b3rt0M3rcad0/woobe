package jsoninput

import (
	"bytes"
	"encoding/json"
	"io"
	"reflect"
	"testing"
)

func TestYAMLCompatibleJSONPreservesTokensAndNumbers(t *testing.T) {
	for _, input := range []string{
		`{"text":"\ud83d\ude00","number":1.0000000000000000001,"zero":-0}`,
		`{"text":"literal \\ud800 and quote \""}`,
		"{\"text\":\"First\u0085Second\"}",
		`{"\ud83d\ude00":1,"😀":2}`,
	} {
		data, err := YAMLCompatibleJSON([]byte(input))
		if err != nil {
			t.Fatal(err)
		}
		assertSameTokens(t, []byte(input), data)
		if (Validate([]byte(input)) == nil) != (Validate(data) == nil) {
			t.Fatal("normalization changed duplicate-key validation")
		}
	}
	for _, input := range []string{`{"text":"\ud800"}`, `{"text":"\udc00"}`, `{"text":"\ud800\ud800"}`, `{"text":"\ud800a"}`, `{`} {
		if _, err := YAMLCompatibleJSON([]byte(input)); err == nil {
			t.Fatal("accepted invalid Unicode/JSON", input)
		}
	}
}

func assertSameTokens(t *testing.T, original, normalized []byte) {
	t.Helper()
	a, b := json.NewDecoder(bytes.NewReader(original)), json.NewDecoder(bytes.NewReader(normalized))
	a.UseNumber()
	b.UseNumber()
	for {
		x, xe := a.Token()
		y, ye := b.Token()
		if xe == io.EOF && ye == io.EOF {
			return
		}
		if xe != nil || ye != nil || !reflect.DeepEqual(x, y) {
			t.Fatalf("normalization changed a JSON token: %v / %v (%v / %v)", x, y, xe, ye)
		}
	}
}

func FuzzYAMLCompatibleJSON(f *testing.F) {
	for _, text := range []string{`{"text":"\ud83d\ude00"}`, `{"text":"\ud800"}`, `{"a":1,"a":2}`, `{"n":1.0000000000000000001}`, `{"text":"quote \""}`, "{\"text\":\"\u0085\"}"} {
		f.Add([]byte(text))
	}
	f.Fuzz(func(t *testing.T, data []byte) {
		if len(data) > 65536 {
			return
		}
		result, err := YAMLCompatibleJSON(data)
		if err == nil {
			assertSameTokens(t, data, result)
		}
	})
}
