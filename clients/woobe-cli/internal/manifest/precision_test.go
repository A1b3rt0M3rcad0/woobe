package manifest

import (
	"strings"
	"testing"
)

func TestResolvedBodyPreservesLargeIntegers(t *testing.T) {
	s, e := ResolveStep(Step{Body: []byte(`{"counter":9007199254740993,"id":"${steps.a.id}"}`)}, map[string]any{"a": map[string]any{"id": "a"}})
	if e != nil || !strings.Contains(string(s.Body), "9007199254740993") {
		t.Fatal(string(s.Body), e)
	}
}
