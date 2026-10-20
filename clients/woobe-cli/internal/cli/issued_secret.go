package cli

import (
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"strings"
	"unicode/utf8"
)

// Read only the documented issuance envelope or a raw one-line credential.
// Never treat arbitrary JSON, redacted data or empty input as a bearer token.
func credentialFromInput(data []byte) (string, error) {
	raw := strings.TrimSpace(string(data))
	if raw == "" || !utf8.Valid(data) {
		return "", output.New(2, "Credential input is empty")
	}
	if !strings.HasPrefix(raw, "{") {
		if strings.ContainsAny(raw, "\r\n\t ") || strings.HasPrefix(raw, "[") {
			return "", output.New(2, "Credential must be a raw token or an issued-secret JSON file")
		}
		return raw, nil
	}
	var envelope map[string]any
	if jsoninput.Validate(data) != nil || json.Unmarshal(data, &envelope) != nil {
		return "", output.New(2, "Invalid issued-secret JSON")
	}
	if format, exists := envelope["format"]; exists && (format != "woobe-issued-secret" || envelope["file_schema_version"] != "1") {
		return "", output.New(2, "Unsupported issued-secret file format")
	}
	if envelope["success"] == false {
		return "", output.New(2, "Issued-secret response was unsuccessful")
	}
	candidate := envelope
	if nested, ok := envelope["data"].(map[string]any); ok {
		candidate = nested
	}
	var secret string
	for _, key := range []string{"key", "api_key", "secret", "token", "access_token"} {
		if value, ok := candidate[key].(string); ok && value != "" {
			if secret != "" {
				return "", output.New(2, "Issued-secret file is ambiguous")
			}
			secret = value
		}
	}
	if secret == "" || secret == "[REDACTED]" || strings.ContainsAny(secret, "\r\n\t ") {
		return "", output.New(2, "Issued-secret file has no usable credential")
	}
	return secret, nil
}
