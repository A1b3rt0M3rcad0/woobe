package devworkspace

import (
	"bytes"
	"encoding/json"
	"fmt"
	"path/filepath"
	"sort"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/requestinput"
	"gopkg.in/yaml.v3"
)

// Encode renders editable block YAML without converting JSON numbers to floats
// or passing string values through YAML's newline normalization.
func Encode(document map[string]any) ([]byte, error) {
	data, err := json.Marshal(document)
	if err != nil {
		return nil, err
	}
	if len(data) > requestinput.MaxBytes {
		return nil, fmt.Errorf("descriptor exceeds 8 MiB")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	var value any
	if err := decoder.Decode(&value); err != nil {
		return nil, err
	}
	node, err := authorNode(value, 0)
	if err != nil {
		return nil, err
	}
	orderFields(node, []string{"format", "schema_version", "kind", "metadata", "spec", "provenance"})
	for i := 0; i+1 < len(node.Content); i += 2 {
		if node.Content[i].Value == "metadata" {
			orderFields(node.Content[i+1], []string{"key", "name", "description", "version", "tags"})
		}
	}
	var output bytes.Buffer
	encoder := yaml.NewEncoder(&output)
	encoder.SetIndent(2)
	if err := encoder.Encode(node); err != nil {
		return nil, err
	}
	if err := encoder.Close(); err != nil {
		return nil, err
	}
	if output.Len() > requestinput.MaxBytes {
		return nil, fmt.Errorf("rendered descriptor exceeds 8 MiB")
	}
	return output.Bytes(), nil
}

// EncodeFile respects the registered descriptor extension. Private state and
// receipts have their own JSON writers and never pass through this formatter.
func EncodeFile(document map[string]any, filename string) ([]byte, error) {
	if !strings.EqualFold(filepath.Ext(filename), ".json") {
		return Encode(document)
	}
	data, err := json.MarshalIndent(document, "", "  ")
	if err != nil {
		return nil, err
	}
	if len(data)+1 > requestinput.MaxBytes {
		return nil, fmt.Errorf("rendered descriptor exceeds 8 MiB")
	}
	return append(data, '\n'), nil
}

func authorNode(value any, depth int) (*yaml.Node, error) {
	if depth > 128 {
		return nil, fmt.Errorf("descriptor nesting exceeds 128")
	}
	node := &yaml.Node{Kind: yaml.ScalarNode}
	switch value := value.(type) {
	case map[string]any:
		node.Kind = yaml.MappingNode
		keys := make([]string, 0, len(value))
		for key := range value {
			keys = append(keys, key)
		}
		sort.Strings(keys)
		for _, key := range keys {
			keyNode, err := authorNode(key, depth+1)
			if err != nil {
				return nil, err
			}
			child, err := authorNode(value[key], depth+1)
			if err != nil {
				return nil, err
			}
			node.Content = append(node.Content, keyNode, child)
		}
	case []any:
		node.Kind = yaml.SequenceNode
		for _, value := range value {
			child, err := authorNode(value, depth+1)
			if err != nil {
				return nil, err
			}
			node.Content = append(node.Content, child)
		}
	case string:
		node.Tag, node.Value = "!!str", value
		// Literal blocks normalize CR/NEL and other YAML line separators. Quote
		// these strings so an edit/pull never silently changes instructions.
		// Tabs at the start of a block's content also confuse YAML indentation
		// discovery; escaped quoted scalars preserve them without invalid YAML.
		if strings.ContainsAny(value, "\t\r\u0085\u2028\u2029") || strings.HasPrefix(value, "\n") || strings.TrimSpace(value) == "" && strings.Contains(value, "\n") {
			node.Style = yaml.DoubleQuotedStyle
		} else if strings.Contains(value, "\n") {
			node.Style = yaml.LiteralStyle
		} else {
			switch strings.ToLower(value) {
			case "y", "n", "yes", "no", "on", "off", "<<":
				node.Style = yaml.DoubleQuotedStyle
			}
		}
	case json.Number:
		// Leave the tag implicit: forcing !!int on a large integer makes the
		// emitter add an explicit tag, forbidden by the portable parser.
		node.Value = value.String()
	case bool:
		node.Tag, node.Value = "!!bool", fmt.Sprint(value)
	case nil:
		node.Tag, node.Value = "!!null", "null"
	default:
		return nil, fmt.Errorf("unsupported descriptor value")
	}
	return node, nil
}

func orderFields(node *yaml.Node, preferred []string) {
	if node.Kind != yaml.MappingNode {
		return
	}
	ordered := make([]*yaml.Node, 0, len(node.Content))
	used := map[int]bool{}
	for _, field := range preferred {
		for i := 0; i+1 < len(node.Content); i += 2 {
			if node.Content[i].Value == field {
				ordered = append(ordered, node.Content[i], node.Content[i+1])
				used[i] = true
			}
		}
	}
	for i := 0; i+1 < len(node.Content); i += 2 {
		if !used[i] {
			ordered = append(ordered, node.Content[i], node.Content[i+1])
		}
	}
	node.Content = ordered
}

// EncodeWithComments applies semantic changes to fresh safe YAML nodes while
// carrying comments attached to surviving fields. Deleted fields have no target.
// JSON descriptors retain JSON format and do not acquire YAML comments.
func EncodeWithComments(document map[string]any, filename, original string) ([]byte, error) {
	if strings.EqualFold(filepath.Ext(filename), ".json") {
		return EncodeFile(document, filename)
	}
	encoded, err := Encode(document)
	if err != nil {
		return nil, err
	}
	var old, next yaml.Node
	if err = yaml.Unmarshal([]byte(original), &old); err != nil {
		return nil, err
	}
	if err = yaml.Unmarshal(encoded, &next); err != nil {
		return nil, err
	}
	var carry func(*yaml.Node, *yaml.Node)
	carry = func(before, after *yaml.Node) {
		after.HeadComment = before.HeadComment
		after.LineComment = before.LineComment
		after.FootComment = before.FootComment
		if before.Kind != after.Kind {
			return
		}
		if before.Kind == yaml.DocumentNode && len(before.Content) == 1 && len(after.Content) == 1 {
			carry(before.Content[0], after.Content[0])
			return
		}
		if before.Kind == yaml.MappingNode {
			fields := map[string]int{}
			for i := 0; i+1 < len(before.Content); i += 2 {
				fields[before.Content[i].Value] = i
			}
			for i := 0; i+1 < len(after.Content); i += 2 {
				if old, ok := fields[after.Content[i].Value]; ok {
					carry(before.Content[old], after.Content[i])
					carry(before.Content[old+1], after.Content[i+1])
				}
			}
		}
		// Lists are atomic in three-way merge. Carry individual comments only when
		// unchanged scalar entries retain the same identity and position.
		if before.Kind == yaml.SequenceNode {
			for i, node := range after.Content {
				if i < len(before.Content) && before.Content[i].Kind == node.Kind && before.Content[i].Tag == node.Tag && before.Content[i].Value == node.Value && node.Kind == yaml.ScalarNode {
					carry(before.Content[i], node)
				}
			}
		}
	}
	carry(&old, &next)
	var result bytes.Buffer
	writer := yaml.NewEncoder(&result)
	writer.SetIndent(2)
	if err = writer.Encode(&next); err != nil {
		return nil, err
	}
	if err = writer.Close(); err != nil {
		return nil, err
	}
	if result.Len() > requestinput.MaxBytes {
		return nil, fmt.Errorf("rendered descriptor exceeds 8 MiB")
	}
	return result.Bytes(), nil
}
