package cli

import (
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
	"unicode/utf8"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

var evaluationCaseID = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9._-]*$`)

// Validate the advertised v1 suite shape before creating local delivery records.
// Qualification and execution still belong to the authoritative server owner.
func validateEvaluationSuite(suite map[string]any) error {
	if suite["schema_version"] != "1.0" || len(packagefmt.List(suite["cases"])) < 1 || len(packagefmt.List(suite["cases"])) > 16 {
		return output.New(2, "Use a versioned Evaluation suite with schema_version: '1.0' and 1–16 cases")
	}
	for key := range suite {
		switch key {
		case "schema_version", "suite_id", "suite_version", "dataset_version", "policy_version", "cases":
		default:
			return output.New(2, "Evaluation suite contains an unknown field")
		}
	}
	for _, key := range []string{"suite_id", "suite_version", "dataset_version"} {
		text, ok := suite[key].(string)
		if !ok || utf8.RuneCountInString(text) < 1 || utf8.RuneCountInString(text) > 128 {
			return output.New(2, "Evaluation suite requires "+key+" as a string of 1–128 characters")
		}
	}
	if policy, exists := suite["policy_version"]; exists && policy != "all-cases-pass@1" {
		return output.New(2, "Evaluation policy_version must be all-cases-pass@1")
	}
	seen := map[string]bool{}
	for index, item := range packagefmt.List(suite["cases"]) {
		fail := func(field string) error {
			return output.New(2, fmt.Sprintf("Evaluation suite cases[%d].%s is invalid", index, field))
		}
		entry, ok := item.(map[string]any)
		if !ok {
			return fail("case")
		}
		for key := range entry {
			if key != "id" && key != "message" && key != "external_context" && key != "expected_output" {
				return fail("unknown_field")
			}
		}
		id, ok := entry["id"].(string)
		if !ok || len(id) > 80 || !evaluationCaseID.MatchString(id) || seen[id] {
			return fail("id")
		}
		seen[id] = true
		message, ok := entry["message"].(string)
		if !ok || utf8.RuneCountInString(message) > 32768 || strings.TrimSpace(message) == "" {
			return fail("message")
		}
		if context, exists := entry["external_context"]; exists {
			if _, ok := context.(map[string]any); !ok {
				return fail("external_context")
			}
		}
	}
	raw, err := json.Marshal(suite)
	if err != nil || len(raw) > 1<<20 {
		return output.New(2, "Evaluation suite exceeds its 1 MiB encoded input bound")
	}
	return nil
}
