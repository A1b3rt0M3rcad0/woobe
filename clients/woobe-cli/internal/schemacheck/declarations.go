package schemacheck

import (
	"regexp"
	"strings"
)

func validType(v any, p string) error {
	types := []any{v}
	if a, ok := v.([]any); ok {
		types = a
	}
	if len(types) == 0 {
		return unsupported(p, "empty type declaration")
	}
	seen := map[string]bool{}
	for _, v := range types {
		s, ok := v.(string)
		known := map[string]bool{"null": true, "object": true, "array": true, "string": true, "boolean": true, "number": true, "integer": true}
		if !ok || !known[s] || seen[s] {
			return unsupported(p, "invalid type declaration")
		}
		seen[s] = true
	}
	return nil
}

func stringList(v any, p, k string) error {
	a, ok := v.([]any)
	if !ok {
		return unsupported(p, "invalid "+k)
	}
	seen := map[string]bool{}
	for _, v := range a {
		s, ok := v.(string)
		if !ok || seen[s] {
			return unsupported(p, "invalid "+k)
		}
		seen[s] = true
	}
	return nil
}
func declarations(s map[string]any, p string) error {
	if v, ok := s["$schema"]; ok {
		if v != "https://json-schema.org/draft/2020-12/schema" && v != "https://spec.openapis.org/oas/3.1/dialect/base" {
			return unsupported(p, "unsupported schema dialect")
		}
		if _, exists := s["nullable"]; exists {
			return unsupported(p, "legacy nullable is not supported in an advertised 2020-12 dialect")
		}
	}
	if v, ok := s["format"]; ok {
		name, ok := v.(string)
		if !ok || !supportedFormat(name) {
			return unsupported(p, "unsupported format declaration")
		}
	}
	if v, ok := s["type"]; ok {
		if e := validType(v, p); e != nil {
			return e
		}
	}
	for _, k := range []string{"nullable", "uniqueItems", "readOnly", "writeOnly", "deprecated"} {
		if v, ok := s[k]; ok {
			if _, ok := v.(bool); !ok {
				return unsupported(p, "invalid "+k)
			}
		}
	}
	if v, ok := s["required"]; ok {
		if e := stringList(v, p, "required"); e != nil {
			return e
		}
	}
	if v, ok := s["$defs"]; ok {
		if _, ok := v.(map[string]any); !ok {
			return unsupported(p, "invalid $defs")
		}
	}
	if v, ok := s["properties"]; ok {
		if _, ok := v.(map[string]any); !ok {
			return unsupported(p, "invalid properties")
		}
	}
	if v, ok := s["enum"]; ok {
		a, ok := v.([]any)
		if !ok || len(a) == 0 {
			return unsupported(p, "invalid enum")
		}
	}
	if v, ok := s["$ref"]; ok {
		if _, ok := v.(string); !ok {
			return unsupported(p, "invalid $ref")
		}
	}
	if v, ok := s["pattern"]; ok {
		r, ok := v.(string)
		if !ok {
			return unsupported(p, "invalid pattern")
		}
		if _, e := regexp.Compile(r); e != nil {
			return unsupported(p, "pattern incompatible with RE2")
		}
	}
	for _, k := range []string{"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "minItems", "maxItems", "minProperties", "maxProperties", "minContains", "maxContains", "minLength", "maxLength"} {
		if v, ok := s[k]; ok {
			n := number(v)
			if n == nil {
				return unsupported(p, "invalid "+k)
			}
			if strings.HasPrefix(k, "min") && k != "minimum" || strings.HasPrefix(k, "max") && k != "maximum" {
				if !n.IsInt() || n.Sign() < 0 {
					return unsupported(p, "invalid "+k)
				}
			}
			if k == "multipleOf" && n.Sign() <= 0 {
				return unsupported(p, "invalid multipleOf")
			}
		}
	}
	if v, ok := s["dependentRequired"]; ok {
		m, ok := v.(map[string]any)
		if !ok {
			return unsupported(p, "invalid dependentRequired")
		}
		for _, v := range m {
			if e := stringList(v, p, "dependentRequired"); e != nil {
				return e
			}
		}
	}
	if v, ok := s["dependentSchemas"]; ok {
		if _, ok := v.(map[string]any); !ok {
			return unsupported(p, "invalid dependentSchemas")
		}
	}
	if v, ok := s["patternProperties"]; ok {
		m, ok := v.(map[string]any)
		if !ok {
			return unsupported(p, "invalid patternProperties")
		}
		for pattern := range m {
			if _, e := regexp.Compile(pattern); e != nil {
				return unsupported(p, "pattern incompatible with RE2")
			}
		}
	}
	if v, ok := s["prefixItems"]; ok {
		a, ok := v.([]any)
		if !ok || len(a) == 0 {
			return unsupported(p, "invalid prefixItems")
		}
	}
	for _, k := range []string{"allOf", "anyOf", "oneOf"} {
		if v, ok := s[k]; ok {
			a, ok := v.([]any)
			if !ok || len(a) == 0 {
				return unsupported(p, "invalid composition")
			}
		}
	}
	if v, ok := s["$id"]; ok && v != "" {
		return unsupported(p, "schema resource IDs are not supported")
	}
	return nil
}

func schemaHeader(s map[string]any, p string) error {
	if e := declarations(s, p); e != nil {
		return e
	}
	allowed := map[string]bool{}
	for _, k := range strings.Fields("$defs $schema $id title description default examples example deprecated readOnly writeOnly discriminator xml externalDocs type format nullable required properties additionalProperties items prefixItems contains minContains maxContains minItems maxItems minProperties maxProperties dependentRequired dependentSchemas propertyNames patternProperties uniqueItems minLength maxLength pattern minimum maximum exclusiveMinimum exclusiveMaximum multipleOf enum const $ref allOf anyOf oneOf not if then else") {
		allowed[k] = true
	}
	for k := range s {
		if !allowed[k] && !strings.HasPrefix(k, "x-") {
			return unsupported(p, "unsupported keyword: "+k)
		}
	}
	return nil
}
