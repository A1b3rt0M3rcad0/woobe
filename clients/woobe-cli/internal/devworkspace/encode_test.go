package devworkspace

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/requestinput"
)

func TestEncodeReadableYAMLWithoutChangingValues(t *testing.T) {
	document := map[string]any{
		"format": "woobe-package", "schema_version": "1.0", "kind": "Agent",
		"metadata": map[string]any{"key": "support", "name": "Suporte", "description": "Diagnóstico técnico"},
		"spec": map[string]any{
			"instructions": "Primeira linha.\n\nSegunda linha.\n",
			"numbers":      []any{json.Number("900719925474099312345"), json.Number("1.0000000000000000001"), json.Number("-0"), json.Number("1e+30")},
			"strings":      []any{"true", "false", "null", "~", "yes", "on", "001", "1e3", ".nan", "2026-10-07", "12:34:56"},
			"empty_map":    map[string]any{}, "empty_list": []any{}, "nullable": nil, "enabled": false,
		},
	}
	data, err := Encode(document)
	if err != nil {
		t.Fatal(err)
	}
	if !bytes.HasPrefix(data, []byte("format: woobe-package\nschema_version: \"1.0\"\nkind: Agent\nmetadata:\n  key: support\n  name: Suporte\n")) {
		t.Fatalf("descriptor is not ordered block YAML:\n%s", data)
	}
	if !bytes.Contains(data, []byte("  instructions: |\n    Primeira linha.\n\n    Segunda linha.\n")) {
		t.Fatalf("instructions are not a readable literal block:\n%s", data)
	}
	assertEncodedValues(t, document, data, "agent.yaml")
	again, err := Encode(document)
	if err != nil || !bytes.Equal(data, again) {
		t.Fatal("serialization is not deterministic", err)
	}
}

func assertEncodedValues(t *testing.T, original map[string]any, data []byte, filename string) {
	t.Helper()
	decoded, err := requestinput.Decode(data, filename, "auto")
	if err != nil {
		t.Fatalf("cannot read generated descriptor: %v\n%s", err, data)
	}
	decoder := json.NewDecoder(bytes.NewReader(decoded))
	decoder.UseNumber()
	var actual map[string]any
	if err := decoder.Decode(&actual); err != nil {
		t.Fatal(err)
	}
	if !reflect.DeepEqual(clone(original), actual) {
		t.Fatalf("serialization changed values:\nwant %#v\ngot %#v\n%s", clone(original), actual, data)
	}
}

func TestEncodePreservesEveryStringLineEnding(t *testing.T) {
	for _, value := range []string{"a\nb", "a\nb\n", "a\n\n", "\n", "  indented\nnext", "a\r\nb\r\n", "a\rb", "a\u0085b\n", "a\u2028b\n", "a\u2029b\n", "a\t\nb", "\x00"} {
		t.Run(strings.ReplaceAll(value, "\n", "LF"), func(t *testing.T) {
			document := map[string]any{"text": value}
			data, err := Encode(document)
			if err != nil {
				t.Fatal(err)
			}
			assertEncodedValues(t, document, data, "agent.yaml")
		})
	}
}

func TestEncodePreservesTabIndentedInstructions(t *testing.T) {
	for _, value := range []string{"\t0\n", "\tfirst\n\tsecond", "first\n\tsecond\n", " \tfirst\nnext"} {
		t.Run(fmt.Sprintf("%q", value), func(t *testing.T) {
			document := map[string]any{"spec": map[string]any{"instructions": value}}
			data, err := Encode(document)
			if err != nil {
				t.Fatal(err)
			}
			assertEncodedValues(t, document, data, "agent.yaml")
			parsed, err := packagefmt.Decode(data, "agent.yaml")
			if err != nil || !reflect.DeepEqual(parsed.Value, document) {
				t.Fatalf("portable package changed tab-indented instructions: %v", err)
			}
		})
	}
}

func TestCreateAndCloneKeepRegisteredJSONDescriptorsReadable(t *testing.T) {
	c, err := Create(t.TempDir(), ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	document := map[string]any{"kind": "Agent", "metadata": map[string]any{"name": "Support"}, "spec": map[string]any{"instructions": "First\nSecond", "limit": json.Number("900719925474099312345")}}
	resource, err := c.Add("Agent", "support", "agents/support.json", document, nil, false)
	if err != nil {
		t.Fatal(err)
	}
	copy, err := c.Clone("Agent", "@support", "copy", "agents/copy.json", false)
	if err != nil {
		t.Fatal(err)
	}
	for _, resource := range []Resource{resource, copy} {
		data, err := os.ReadFile(filepath.Join(c.RootPath(), descriptor(resource)))
		if err != nil {
			t.Fatal(err)
		}
		if !json.Valid(data) || !bytes.Contains(data, []byte("\n  \"kind\": \"Agent\"")) {
			t.Fatalf(".json descriptor must remain indented JSON:\n%s", data)
		}
	}
	if _, err := LoadGraph(c); err != nil {
		t.Fatal(err)
	}
}

func TestMoveConvertsDescriptorFormatWithoutChangingIdentityOrContent(t *testing.T) {
	c, err := Create(t.TempDir(), ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	document := map[string]any{"kind": "Agent", "metadata": map[string]any{"name": "Support"}, "spec": map[string]any{"instructions": "First\nSecond\n", "limit": json.Number("-0")}}
	resource, err := c.Add("Agent", "support", "", document, nil, false)
	if err != nil {
		t.Fatal(err)
	}
	before, err := LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	for _, destination := range []string{"agents/support.json", "agents/support.yml", "agents/support.yaml"} {
		if err := c.Move("Agent", "@support", destination, false); err != nil {
			t.Fatal(err)
		}
		after, err := LoadGraph(c)
		if err != nil {
			t.Fatal(err)
		}
		if after.Nodes[resource.Key].Resource.UID != resource.UID || !reflect.DeepEqual(before.Nodes[resource.Key].Document, after.Nodes[resource.Key].Document) {
			t.Fatal("move changed resource identity or values")
		}
	}
}

func TestReadableDescriptorsKeepCompleteDependencyGraphSemantics(t *testing.T) {
	_, graph := completeGraph(t)
	for key, node := range graph.Nodes {
		t.Run(key, func(t *testing.T) {
			data, err := Encode(node.Document)
			if err != nil {
				t.Fatal(err)
			}
			parsed, err := packagefmt.Decode(data, "descriptor.yaml")
			if err != nil {
				t.Fatal(err)
			}
			if !reflect.DeepEqual(node.Document, parsed.Value) {
				t.Fatal("formatting changed dependency graph values")
			}
			merged, conflicts := Merge(node.Document, parsed.Value, node.Document)
			if len(conflicts) != 0 || !reflect.DeepEqual(merged, node.Document) {
				t.Fatal("formatting caused a semantic merge change")
			}
		})
	}
}

func FuzzEncodeRoundTrip(f *testing.F) {
	for _, text := range []string{"Hello\nWorld", "\n", "a\u0085b\n", "null", "yes", "1.0", "2026-10-07", "\r\n", "\t0\n"} {
		f.Add(text)
	}
	f.Fuzz(func(t *testing.T, text string) {
		if len(text) > 65536 {
			return
		}
		document := map[string]any{"text": text}
		data, err := Encode(document)
		if err != nil {
			t.Fatal(err)
		}
		assertEncodedValues(t, document, data, "agent.yaml")
	})
}
