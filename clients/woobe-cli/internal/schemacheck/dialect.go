package schemacheck

import "strings"

func modernDialect(document any) bool {
	doc, ok := document.(map[string]any)
	if !ok {
		return false
	}
	version, _ := doc["openapi"].(string)
	return strings.HasPrefix(version, "3.1.") || doc["$schema"] != nil || doc["jsonSchemaDialect"] != nil
}
