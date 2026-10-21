package cli

import (
	"bytes"
	"encoding/json"
	"sort"
	"strings"
)

func scrubSecretJSON(b []byte, values map[string]string) []byte {
	var value any
	dec := json.NewDecoder(bytes.NewReader(b))
	dec.UseNumber()
	if dec.Decode(&value) != nil {
		return nil
	}
	secrets := []string{}
	for _, secret := range values {
		secrets = append(secrets, secret)
	}
	sort.Slice(secrets, func(i, j int) bool { return len(secrets[i]) > len(secrets[j]) })
	var scrub func(any) any
	scrub = func(v any) any {
		switch x := v.(type) {
		case string:
			for _, secret := range secrets {
				if secret != "" {
					x = strings.ReplaceAll(x, secret, "[REDACTED]")
				}
			}
			return x
		case map[string]any:
			out := map[string]any{}
			for k, sub := range x {
				out[scrub(k).(string)] = scrub(sub)
			}
			return out
		case []any:
			for i, sub := range x {
				x[i] = scrub(sub)
			}
			return x
		}
		return v
	}
	out, _ := json.Marshal(scrub(value))
	return out
}
