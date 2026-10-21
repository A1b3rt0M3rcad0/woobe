package output

import (
	"bytes"
	"strings"
	"testing"
)

func TestASaCCompactKeepsContinuationIdentities(t *testing.T) {
	data := map[string]any{"operation_id": "acceptance", "candidate_id": "candidate", "preparation_operation_id": "preparation", "evaluation_id": "evaluation", "publication_id": "publication", "release_id": "release", "draft_id": "draft", "revision_id": "revision", "state": "pending", "complete": false, "write_outcome": "committed"}
	for _, command := range []string{"develop agent stage", "develop network stage", "develop agent candidate", "develop network candidate", "develop agent test", "develop network publish"} {
		_, result := view(t, Options{Mode: "compact", Command: command}, data, nil, nil)
		out := result["data"].(map[string]any)
		for key, value := range data {
			if out[key] != value {
				t.Fatal(command, key, result)
			}
		}
	}
}

func TestFieldProjectionDistinguishesAbsentAndNull(t *testing.T) {
	value := []any{map[string]any{"id": "one", "nullable": nil}}
	_, result := view(t, Options{Mode: "compact", Fields: []string{"id", "nullable", "missing"}}, value, nil, nil)
	row := result["data"].([]any)[0].(map[string]any)
	if _, exists := row["missing"]; exists {
		t.Fatal("absent field became null", row)
	}
	if v, exists := row["nullable"]; !exists || v != nil {
		t.Fatal("explicit null lost", row)
	}
	for _, value := range []any{value, []any{map[string]any{"id": "one"}, map[string]any{"other": "two"}}, "scalar"} {
		var out bytes.Buffer
		err := WriteView(&out, Options{Mode: "compact", Fields: []string{"id", "missing"}, StrictFields: true}, value, nil, nil, nil)
		if err == nil || Normalize(err).Code != 2 || !strings.Contains(err.Error(), "missing") || out.Len() != 0 {
			t.Fatal(err, out.String())
		}
	}
	view(t, Options{Mode: "compact", Fields: []string{"nullable"}, StrictFields: true}, map[string]any{"nullable": nil}, nil, nil)
	view(t, Options{Mode: "compact", Fields: []string{"missing"}, StrictFields: true}, []any{}, nil, nil)
}
