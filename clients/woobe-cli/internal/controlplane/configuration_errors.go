package controlplane

import (
	"encoding/json"
	"regexp"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

// Configuration failures can originate at any canonical operation (including
// admission, promotion and deployment). Accept only the versioned contract and
// known codes; never echo upstream messages, inputs or provider responses.
func configurationDiagnostic(raw []byte, failure *output.Error) bool {
	if len(raw) > 64<<10 || jsoninput.Validate(raw) != nil {
		return false
	}
	var envelope struct {
		Data struct {
			Version     string `json:"configuration_schema_version"`
			Diagnostics []struct {
				Code        string `json:"code"`
				Key         string `json:"key"`
				Environment string `json:"environment"`
			} `json:"diagnostics"`
		} `json:"data"`
	}
	if json.Unmarshal(raw, &envelope) != nil || envelope.Data.Version != "project_configuration.v1" || len(envelope.Data.Diagnostics) != 1 {
		return false
	}
	item := envelope.Data.Diagnostics[0]
	messages := map[string]string{
		"CONFIG_REFERENCE_NOT_FOUND":    "Remote configuration reference is missing; inspect Project Environments and the consumer binding",
		"CONFIG_KIND_MISMATCH":          "Remote configuration kind does not match the consumer",
		"CONFIG_VALUE_MISSING":          "Fill the required value for this Environment in Woobe, then retry the explicit operation",
		"CONFIG_VALUE_INVALID":          "Correct the value format in Woobe Project Environments",
		"CONFIG_USAGE_NOT_AUTHORIZED":   "An authorized operator must approve this consumer and destination in Project Environments",
		"CONFIG_DESTINATION_CHANGED":    "The connection destination needs explicit configuration approval",
		"CONFIG_VALUE_REVOKED":          "Configuration was revoked; review it in Woobe before starting a new operation",
		"CONFIG_VERSION_UNAVAILABLE":    "The pinned configuration version is unavailable; reconcile the original operation before starting another",
		"CONFIG_REVISION_CONFLICT":      "Configuration changed; refresh readiness and create a new plan before applying",
		"CONFIG_STORE_UNAVAILABLE":      "Configuration status is unavailable; restore the store and reconcile the original operation",
		"CONFIG_REFERENCE_IN_USE":       "A retained definition still uses this configuration reference",
		"CONFIG_BINDING_INVALID":        "Correct the typed configuration binding; do not supply an inline value",
		"CONFIG_DEFINITION_INVALID":     "Correct the remote configuration declaration",
		"CONFIG_MIGRATION_WORK_PENDING": "Finish active work and apply or expire pending package plans before configuration cutover",
		"CONFIG_BRIDGE_REQUIRED":        "Configuration migration requires a compatible, drained process fleet",
		"LEGACY_ENVIRONMENT_REQUIRED":   "Select an explicit Environment after converting legacy configuration",
		"LEGACY_FORMAT_UNSUPPORTED":     "This legacy configuration needs operator review",
	}
	message, ok := messages[item.Code]
	if !ok {
		return false
	}
	diagnostic := output.DomainDiagnostic{Code: item.Code}
	if regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]{0,127}$`).MatchString(item.Key) {
		diagnostic.Key = item.Key
	}
	if item.Environment == "draft" || item.Environment == "staging" || item.Environment == "production" {
		diagnostic.Environment = item.Environment
	}
	failure.DomainCode, failure.Diagnostics, failure.Message = item.Code, []output.DomainDiagnostic{diagnostic}, message
	failure.Code = 6
	if failure.Status == 401 || failure.Status == 403 {
		failure.Code = 3
		if failure.Status == 403 {
			failure.Code = 4
		}
		return true
	}
	switch item.Code {
	case "CONFIG_STORE_UNAVAILABLE", "CONFIG_VERSION_UNAVAILABLE":
		failure.Code = 9
	case "CONFIG_BINDING_INVALID", "CONFIG_DEFINITION_INVALID", "CONFIG_KIND_MISMATCH":
		failure.Code = 2
	}
	return true
}
