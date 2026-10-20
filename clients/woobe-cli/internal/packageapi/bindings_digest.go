package packageapi

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
)

// BindingsDigest uses the backend's UTF-8 canonical JSON for the reference-only
// ImportBindings contract. Protected values and numeric author configuration do
// not belong in this document.
func BindingsDigest(value map[string]any) (string, error) {
	var buffer bytes.Buffer
	buffer.WriteString("woobe-package-definition@1.0\n")
	var write func(any) error
	quote := func(value string) {
		buffer.WriteByte('"')
		for _, character := range value {
			switch character {
			case '"', '\\':
				buffer.WriteByte('\\')
				buffer.WriteRune(character)
			case '\b':
				buffer.WriteString(`\b`)
			case '\f':
				buffer.WriteString(`\f`)
			case '\n':
				buffer.WriteString(`\n`)
			case '\r':
				buffer.WriteString(`\r`)
			case '\t':
				buffer.WriteString(`\t`)
			default:
				if character < 32 {
					fmt.Fprintf(&buffer, `\u%04x`, character)
				} else {
					buffer.WriteRune(character)
				}
			}
		}
		buffer.WriteByte('"')
	}
	write = func(item any) error {
		switch value := item.(type) {
		case nil:
			buffer.WriteString("null")
		case string:
			quote(value)
		case bool:
			if value {
				buffer.WriteString("true")
			} else {
				buffer.WriteString("false")
			}
		case map[string]any:
			keys := make([]string, 0, len(value))
			for key := range value {
				keys = append(keys, key)
			}
			sort.Strings(keys)
			buffer.WriteByte('{')
			for index, key := range keys {
				if index > 0 {
					buffer.WriteByte(',')
				}
				quote(key)
				buffer.WriteByte(':')
				if err := write(value[key]); err != nil {
					return err
				}
			}
			buffer.WriteByte('}')
		case []any:
			buffer.WriteByte('[')
			for index, child := range value {
				if index > 0 {
					buffer.WriteByte(',')
				}
				if err := write(child); err != nil {
					return err
				}
			}
			buffer.WriteByte(']')
		default:
			return fmt.Errorf("invalid ImportBindings value type")
		}
		return nil
	}
	if err := write(value); err != nil {
		return "", err
	}
	digest := sha256.Sum256(buffer.Bytes())
	return hex.EncodeToString(digest[:]), nil
}
