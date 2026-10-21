package jsoninput

import (
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"unicode/utf8"
)

// YAMLCompatibleJSON preserves JSON string semantics in a YAML AST. YAML does
// not combine JSON UTF-16 surrogate pairs and normalizes raw NEL characters.
// Only string tokens change; number lexemes and duplicate keys stay intact.
func YAMLCompatibleJSON(data []byte) ([]byte, error) {
	if !utf8.Valid(data) || !json.Valid(data) {
		return nil, fmt.Errorf("invalid JSON encoding")
	}
	var output strings.Builder
	for i := 0; i < len(data); {
		if data[i] != '"' {
			output.WriteByte(data[i])
			i++
			continue
		}
		start := i
		i++
		for i < len(data) && data[i] != '"' {
			if data[i] == '\\' {
				i++
			}
			i++
		}
		i++
		token := data[start:i]
		if !validUTF16(token) {
			return nil, fmt.Errorf("unpaired JSON Unicode surrogate")
		}
		var value string
		if err := json.Unmarshal(token, &value); err != nil {
			return nil, err
		}
		encoded, err := json.Marshal(value)
		if err != nil {
			return nil, err
		}
		for _, r := range string(encoded) {
			if r >= 0x7f && r <= 0x9f {
				fmt.Fprintf(&output, "\\u%04x", r)
			} else {
				output.WriteRune(r)
			}
		}
	}
	return []byte(output.String()), nil
}

func validUTF16(token []byte) bool {
	for i := 1; i < len(token)-1; i++ {
		if token[i] != '\\' {
			continue
		}
		i++
		if token[i] != 'u' {
			continue
		}
		code, _ := strconv.ParseUint(string(token[i+1:i+5]), 16, 16)
		i += 4
		if code < 0xd800 || code > 0xdfff {
			continue
		}
		if code > 0xdbff || i+6 >= len(token) || token[i+1] != '\\' || token[i+2] != 'u' {
			return false
		}
		low, _ := strconv.ParseUint(string(token[i+3:i+7]), 16, 16)
		if low < 0xdc00 || low > 0xdfff {
			return false
		}
		i += 6
	}
	return true
}
