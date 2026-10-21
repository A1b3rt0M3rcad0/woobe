package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

func validateSchemaDialect(doc map[string]any) error {
	if raw, exists := doc["openapi"]; exists {
		version, ok := raw.(string)
		if !ok || version != "3.1.0" && version != "3.1.1" && version != "3.1.2" {
			return output.New(9, "unsupported OpenAPI version for body validation; requires 3.1")
		}
	}
	if raw, exists := doc["jsonSchemaDialect"]; exists {
		if raw != "https://json-schema.org/draft/2020-12/schema" && raw != "https://spec.openapis.org/oas/3.1/dialect/base" {
			return output.New(9, "unsupported advertised JSON Schema dialect")
		}
	}
	return nil
}
