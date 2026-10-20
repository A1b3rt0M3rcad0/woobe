package manifest

import "fmt"

// ResolveSecrets builds a separate wire value; it never changes the saved plan.
func ResolveSecrets(v any, values map[string]string) (any, error) {
	if name, ok := SecretReference(v); ok {
		value, exists := values[name]
		if !exists || value == "" {
			return nil, fmt.Errorf("protected credential reference is unavailable")
		}
		return value, nil
	}
	switch x := v.(type) {
	case map[string]any:
		out := map[string]any{}
		for k, sub := range x {
			resolved, e := ResolveSecrets(sub, values)
			if e != nil {
				return nil, e
			}
			out[k] = resolved
		}
		return out, nil
	case []any:
		out := make([]any, len(x))
		for i, sub := range x {
			resolved, e := ResolveSecrets(sub, values)
			if e != nil {
				return nil, e
			}
			out[i] = resolved
		}
		return out, nil
	}
	return v, nil
}
