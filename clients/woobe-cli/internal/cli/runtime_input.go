package cli

import (
	"bytes"
	"encoding/json"
	"fmt"
	sdk "github.com/A1b3rt0M3rcad0/woobe-sdk-go"
	"strings"
)

type runtimeInput struct {
	Input   string
	Options sdk.RunOptions
}

// Normalize the stable CLI YAML names; retain explicitly documented SDK spellings.
// Never silently ignore a misspelled session identity and start a new Session.
func decodeRuntimeInput(raw []byte) (runtimeInput, error) {
	var result runtimeInput
	var root map[string]json.RawMessage
	if err := json.Unmarshal(raw, &root); err != nil || root == nil {
		return result, fmt.Errorf("runtime input must be an object")
	}
	for key := range root {
		if key != "input" && key != "options" && key != "session_id" {
			return result, fmt.Errorf("unknown runtime input field; use input, session_id or options")
		}
	}
	if err := json.Unmarshal(root["input"], &result.Input); err != nil || strings.TrimSpace(result.Input) == "" {
		return result, fmt.Errorf("runtime input requires nonempty input")
	}
	if options, present := root["options"]; present && !bytes.Equal(options, []byte("null")) {
		var values map[string]json.RawMessage
		if err := json.Unmarshal(options, &values); err != nil || values == nil {
			return result, fmt.Errorf("runtime options must be an object")
		}
		aliases := map[string]string{"session_id": "SessionID", "tenant_id": "TenantID", "user_id": "UserID", "metadata": "Metadata", "external_context": "ExternalContext", "SessionID": "SessionID", "TenantID": "TenantID", "UserID": "UserID", "Metadata": "Metadata", "ExternalContext": "ExternalContext"}
		normalized := map[string]json.RawMessage{}
		for key, value := range values {
			canonical, valid := aliases[key]
			if !valid {
				return result, fmt.Errorf("unknown runtime option; use session_id, tenant_id, user_id, metadata or external_context")
			}
			if _, duplicate := normalized[canonical]; duplicate {
				return result, fmt.Errorf("runtime option has duplicate spellings")
			}
			if canonical == "SessionID" && bytes.Equal(value, []byte("null")) {
				return result, fmt.Errorf("session_id must be a nonempty string when supplied")
			}
			normalized[canonical] = value
		}
		encoded, _ := json.Marshal(normalized)
		decoder := json.NewDecoder(bytes.NewReader(encoded))
		decoder.UseNumber()
		if err := decoder.Decode(&result.Options); err != nil {
			return result, fmt.Errorf("runtime option value has an invalid type")
		}
	}
	if session, present := root["session_id"]; present {
		var id string
		if err := json.Unmarshal(session, &id); err != nil || strings.TrimSpace(id) == "" {
			return result, fmt.Errorf("session_id must be a nonempty string when supplied")
		}
		if result.Options.SessionID != "" && result.Options.SessionID != id {
			return result, fmt.Errorf("conflicting runtime session identities")
		}
		result.Options.SessionID = id
	}
	return result, nil
}
