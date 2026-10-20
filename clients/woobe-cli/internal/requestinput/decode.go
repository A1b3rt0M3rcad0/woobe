// Package requestinput converts author input to the JSON HTTP contract without
// evaluating YAML aliases, merge keys, arbitrary tags or lossy numeric coercions.
package requestinput

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"math/big"
	"path/filepath"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"gopkg.in/yaml.v3"
)

const MaxBytes = 8 << 20

func Decode(data []byte, source, format string) ([]byte, error) {
	if len(data) > MaxBytes {
		return nil, fmt.Errorf("input exceeds 8 MiB")
	}
	if format == "auto" {
		ext := strings.ToLower(filepath.Ext(source))
		switch ext {
		case ".json":
			format = "json"
		case ".yaml", ".yml":
			format = "yaml"
		default:
			trimmed := bytes.TrimSpace(data)
			if json.Valid(data) || len(trimmed) > 0 && (trimmed[0] == '{' || trimmed[0] == '[') {
				format = "json"
			} else {
				format = "yaml"
			}
		}
	}
	if format == "json" {
		if err := jsoninput.Validate(data); err != nil {
			return nil, fmt.Errorf("invalid or ambiguous JSON input")
		}
		return data, nil
	}
	if format != "yaml" {
		return nil, fmt.Errorf("input-format must be auto, json or yaml")
	}
	if json.Valid(data) {
		var err error
		data, err = jsoninput.YAMLCompatibleJSON(data)
		if err != nil {
			return nil, fmt.Errorf("invalid JSON Unicode encoding")
		}
	}
	decoder := yaml.NewDecoder(bytes.NewReader(data))
	var doc yaml.Node
	if err := decoder.Decode(&doc); err != nil {
		return nil, fmt.Errorf("invalid YAML input")
	}
	var extra yaml.Node
	if decoder.Decode(&extra) != io.EOF {
		return nil, fmt.Errorf("expected one YAML document")
	}
	if len(doc.Content) != 1 {
		return nil, fmt.Errorf("expected one YAML value")
	}
	value, err := convert(doc.Content[0], 0)
	if err != nil {
		return nil, err
	}
	result, err := json.Marshal(value)
	if err != nil || len(result) > MaxBytes {
		return nil, fmt.Errorf("invalid or excessive converted JSON input")
	}
	if err := jsoninput.Validate(result); err != nil {
		return nil, fmt.Errorf("invalid converted JSON input")
	}
	return result, nil
}

func convert(node *yaml.Node, depth int) (any, error) {
	if depth > 128 {
		return nil, fmt.Errorf("YAML nesting exceeds 128")
	}
	if node.Anchor != "" || node.Kind == yaml.AliasNode {
		return nil, fmt.Errorf("YAML anchors and aliases are unsupported")
	}
	switch node.Kind {
	case yaml.MappingNode:
		if node.Tag != "!!map" || len(node.Content)%2 != 0 {
			return nil, fmt.Errorf("invalid YAML mapping")
		}
		value := map[string]any{}
		for i := 0; i < len(node.Content); i += 2 {
			key := node.Content[i]
			if key.Kind != yaml.ScalarNode || key.Tag != "!!str" || key.Anchor != "" {
				return nil, fmt.Errorf("YAML object keys must be strings; merge keys are unsupported")
			}
			if _, exists := value[key.Value]; exists {
				return nil, fmt.Errorf("duplicate YAML object field")
			}
			item, err := convert(node.Content[i+1], depth+1)
			if err != nil {
				return nil, err
			}
			value[key.Value] = item
		}
		return value, nil
	case yaml.SequenceNode:
		if node.Tag != "!!seq" {
			return nil, fmt.Errorf("unsupported YAML sequence tag")
		}
		value := make([]any, len(node.Content))
		for i, item := range node.Content {
			converted, err := convert(item, depth+1)
			if err != nil {
				return nil, err
			}
			value[i] = converted
		}
		return value, nil
	case yaml.ScalarNode:
		switch node.Tag {
		case "!!str", "!!timestamp":
			return node.Value, nil
		case "!!null":
			if node.Value != "" && node.Value != "~" && !strings.EqualFold(node.Value, "null") {
				return nil, fmt.Errorf("invalid YAML null")
			}
			return nil, nil
		case "!!bool":
			if !strings.EqualFold(node.Value, "true") && !strings.EqualFold(node.Value, "false") {
				return nil, fmt.Errorf("invalid YAML boolean")
			}
			return strings.EqualFold(node.Value, "true"), nil
		case "!!int":
			if json.Valid([]byte(node.Value)) {
				return json.Number(node.Value), nil
			}
			text := strings.ReplaceAll(node.Value, "_", "")
			number, ok := new(big.Int).SetString(text, 0)
			if !ok {
				return nil, fmt.Errorf("unsupported YAML integer")
			}
			return json.Number(number.String()), nil
		case "!!float":
			text := strings.ReplaceAll(node.Value, "_", "")
			text = strings.TrimPrefix(text, "+")
			if strings.HasPrefix(text, ".") {
				text = "0" + text
			}
			if strings.HasPrefix(text, "-.") {
				text = "-0" + text[1:]
			}
			if strings.HasSuffix(text, ".") {
				text += "0"
			}
			if !json.Valid([]byte(text)) {
				return nil, fmt.Errorf("YAML float must be a finite JSON number")
			}
			return json.Number(text), nil
		}
	}
	return nil, fmt.Errorf("unsupported YAML node or tag")
}
