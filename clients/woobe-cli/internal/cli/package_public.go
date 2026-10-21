package cli

import "encoding/json"

// Public output identifies deferred bindings without exposing protected store aliases.
// Private approved receipts retain aliases so Apply can resolve them once.
func packagePublic(value any) any {
	encoded, err := json.Marshal(value)
	if err != nil {
		return nil
	}
	var decoded any
	if json.Unmarshal(encoded, &decoded) != nil {
		return nil
	}
	var redact func(any) any
	redact = func(item any) any {
		switch value := item.(type) {
		case map[string]any:
			result := make(map[string]any, len(value))
			for key, child := range value {
				if key == "protected_ref" {
					result[key] = "[REDACTED]"
				} else {
					result[key] = redact(child)
				}
			}
			return result
		case []any:
			result := make([]any, len(value))
			for i, child := range value {
				result[i] = redact(child)
			}
			return result
		default:
			return item
		}
	}
	return redact(decoded)
}
