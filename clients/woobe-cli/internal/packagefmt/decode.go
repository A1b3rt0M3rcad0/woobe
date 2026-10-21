// Package packagefmt parses the public portable format without network or tenancy.
package packagefmt

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"regexp"
	"strconv"
	"strings"
	"unicode/utf8"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"

	"gopkg.in/yaml.v3"
)

const MaxDescriptorBytes = 2 << 20
const MaxDepth = 32
const MaxNodes = 200000
const MaxInteger int64 = 9007199254740991

var numberSyntax = regexp.MustCompile(`^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?$`)

type Diagnostic struct {
	Code    string `json:"code"`
	Message string `json:"message"`
	File    string `json:"file,omitempty"`
	Path    string `json:"path,omitempty"`
	Line    int    `json:"line,omitempty"`
	Column  int    `json:"column,omitempty"`
}

func (d *Diagnostic) Error() string {
	return fmt.Sprintf("%s: %s (%s%s)", d.Code, d.Message, d.File, d.Path)
}

type Location struct{ Line, Column int }
type Document struct {
	Value     map[string]any
	Locations map[string]Location
	File      string
}

func Decode(data []byte, file string) (*Document, error) {
	failure := func(code, message string) error { return &Diagnostic{Code: code, Message: message, File: file} }
	if len(data) > MaxDescriptorBytes {
		return nil, failure("PACKAGE_LIMIT_EXCEEDED", "Descriptor exceeds 2 MiB")
	}
	if !utf8.Valid(data) {
		return nil, failure("PACKAGE_PARSE_INVALID", "Invalid UTF-8 document")
	}
	if strings.HasSuffix(file, ".json") && jsoninput.Validate(data) != nil {
		return nil, failure("PACKAGE_PARSE_INVALID", "Invalid or duplicate-key JSON")
	}
	if json.Valid(data) {
		var err error
		data, err = jsoninput.YAMLCompatibleJSON(data)
		if err != nil {
			return nil, failure("PACKAGE_PARSE_INVALID", "Invalid JSON Unicode encoding")
		}
	}
	decoder := yaml.NewDecoder(bytes.NewReader(data))
	var root yaml.Node
	if err := decoder.Decode(&root); err != nil {
		return nil, failure("PACKAGE_PARSE_INVALID", "Invalid YAML/JSON document")
	}
	var extra yaml.Node
	if decoder.Decode(&extra) != io.EOF {
		return nil, failure("PACKAGE_PARSE_INVALID", "Exactly one document is required")
	}
	locations := map[string]Location{}
	count := 0
	var convert func(*yaml.Node, string, int) (any, error)
	convert = func(node *yaml.Node, path string, depth int) (any, error) {
		count++
		locations[path] = Location{node.Line, node.Column}
		fail := func(code, message string) (any, error) {
			return nil, &Diagnostic{Code: code, Message: message, File: file, Path: path, Line: node.Line, Column: node.Column}
		}
		if count > MaxNodes || depth > MaxDepth {
			return fail("PACKAGE_LIMIT_EXCEEDED", "Descriptor exceeds structural limits")
		}
		if node.Anchor != "" || node.Kind == yaml.AliasNode || node.Style&yaml.TaggedStyle != 0 {
			return fail("PACKAGE_PARSE_INVALID", "Aliases, anchors and explicit tags are forbidden")
		}
		switch node.Kind {
		case yaml.DocumentNode:
			if len(node.Content) != 1 {
				return fail("PACKAGE_PARSE_INVALID", "Exactly one document is required")
			}
			return convert(node.Content[0], path, depth)
		case yaml.MappingNode:
			result := map[string]any{}
			for i := 0; i < len(node.Content); i += 2 {
				key := node.Content[i]
				if key.Kind != yaml.ScalarNode || key.Tag != "!!str" || key.Value == "<<" {
					return fail("PACKAGE_PARSE_INVALID", "Mapping keys must be strings; merge keys are forbidden")
				}
				if _, ok := result[key.Value]; ok {
					return fail("PACKAGE_PARSE_INVALID", "Duplicate mapping key")
				}
				escaped := strings.ReplaceAll(strings.ReplaceAll(key.Value, "~", "~0"), "/", "~1")
				value, err := convert(node.Content[i+1], path+"/"+escaped, depth+1)
				if err != nil {
					return nil, err
				}
				result[key.Value] = value
			}
			return result, nil
		case yaml.SequenceNode:
			result := make([]any, 0, len(node.Content))
			for i, child := range node.Content {
				value, err := convert(child, path+"/"+strconv.Itoa(i), depth+1)
				if err != nil {
					return nil, err
				}
				result = append(result, value)
			}
			return result, nil
		case yaml.ScalarNode:
			if node.Style == 0 && numberSyntax.MatchString(node.Value) {
				number := json.Number(node.Value)
				if !strings.ContainsAny(node.Value, ".eE") {
					integer, err := number.Int64()
					if err != nil || integer > MaxInteger || integer < -MaxInteger {
						return fail("PACKAGE_PARSE_INVALID", "Integer exceeds exact interoperable range")
					}
				} else {
					value, err := number.Float64()
					if err != nil || math.IsInf(value, 0) || math.IsNaN(value) {
						return fail("PACKAGE_PARSE_INVALID", "Nonfinite numbers are forbidden")
					}
				}
				return number, nil
			}
			switch node.Tag {
			case "!!str", "!!timestamp":
				return node.Value, nil
			case "!!null":
				return nil, nil
			case "!!bool":
				if node.Value == "true" {
					return true, nil
				}
				if node.Value == "false" {
					return false, nil
				}
				return node.Value, nil
			default:
				return fail("PACKAGE_PARSE_INVALID", "Only JSON-compatible scalars are supported")
			}
		default:
			return fail("PACKAGE_PARSE_INVALID", "Unsupported node")
		}
	}
	value, err := convert(&root, "", 0)
	if err != nil {
		return nil, err
	}
	object, ok := value.(map[string]any)
	if !ok {
		return nil, failure("PACKAGE_PARSE_INVALID", "Document root must be a mapping")
	}
	return &Document{Value: object, Locations: locations, File: file}, nil
}
