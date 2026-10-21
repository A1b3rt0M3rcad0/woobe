package cli

import (
	"encoding/json"
	"io"
	"net/url"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/schemacheck"
)

type advertisedParameter struct {
	name, location string
	required       bool
	schema         any
	style          string
	explode        bool
}

// Operation declarations replace path-level parameters with the same name/location.
func parameterDeclarations(doc, path, def map[string]any) ([]advertisedParameter, error) {
	parameters := []advertisedParameter{}
	indexes := map[string]int{}
	for _, source := range []map[string]any{path, def} {
		raw, exists := source["parameters"]
		if !exists {
			continue
		}
		list, ok := raw.([]any)
		if !ok || len(list) > 1024 {
			return nil, output.New(9, "invalid or excessive OpenAPI parameters")
		}
		seen := map[string]bool{}
		for _, raw := range list {
			resolved, e := resolveOpenAPIObject(doc, raw)
			if e != nil {
				return nil, e
			}
			obj := resolved.(map[string]any)
			name, ok := obj["name"].(string)
			if !ok || name == "" {
				return nil, output.New(9, "invalid parameter name")
			}
			location, ok := obj["in"].(string)
			if !ok || location != "path" && location != "query" && location != "header" && location != "cookie" {
				return nil, output.New(9, "invalid parameter location")
			}
			key := location + ":" + name
			if seen[key] {
				return nil, output.New(9, "duplicate OpenAPI parameter declaration")
			}
			seen[key] = true
			required := false
			if v, exists := obj["required"]; exists {
				var ok bool
				required, ok = v.(bool)
				if !ok {
					return nil, output.New(9, "invalid parameter required declaration")
				}
			}
			if location == "path" && !required {
				return nil, output.New(9, "path parameter must be required")
			}
			p := advertisedParameter{name: name, location: location, required: required, schema: obj["schema"]}
			p.style = "form"
			p.explode = true
			if location == "path" {
				p.style = "simple"
				p.explode = false
			}
			if v, exists := obj["style"]; exists {
				var ok bool
				p.style, ok = v.(string)
				if !ok {
					return nil, output.New(9, "invalid parameter style")
				}
			}
			if v, exists := obj["explode"]; exists {
				var ok bool
				p.explode, ok = v.(bool)
				if !ok {
					return nil, output.New(9, "invalid parameter explode")
				}
			}
			if _, exists := obj["content"]; exists {
				return nil, output.New(9, "content parameter serialization is not supported")
			}
			if p.schema == nil {
				return nil, output.New(9, "parameter schema is not advertised")
			}
			if i, exists := indexes[key]; exists {
				parameters[i] = p
			} else {
				indexes[key] = len(parameters)
				parameters = append(parameters, p)
			}
		}
	}
	return parameters, nil
}

func validateParameterSchema(doc, path, def map[string]any, values map[string]string, query url.Values) error {
	if e := validateSchemaDialect(doc); e != nil {
		return e
	}
	parameters, e := parameterDeclarations(doc, path, def)
	if e != nil {
		return e
	}
	known := map[string]bool{}
	for _, p := range parameters {
		if p.location != "path" && p.location != "query" {
			continue
		}
		// Unsupported optional schemas must never receive a silent approval.
		if e := schemacheck.Check(p.schema, nil, doc); e != nil && output.Normalize(schemaError(e)).Code == 9 {
			return schemaError(e)
		}
		var raw []string
		if p.location == "path" {
			if v, ok := values[p.name]; ok {
				raw = []string{v}
			}
		} else {
			known[p.name] = true
			raw = query[p.name]
		}
		if len(raw) == 0 {
			if p.required {
				return output.New(2, "required "+p.location+" parameter is missing: "+p.name)
			}
			continue
		}
		v, e := decodeParameter(p, raw, doc)
		if e != nil {
			return e
		}
		if e := schemacheck.Check(p.schema, v, doc); e != nil {
			return schemaError(e)
		}
	}
	for name := range query {
		if !known[name] {
			return output.New(9, "query parameter is not advertised: "+name)
		}
	}
	for name := range values {
		found := false
		for _, p := range parameters {
			found = found || p.location == "path" && p.name == name
		}
		if !found {
			return output.New(9, "path parameter is not advertised: "+name)
		}
	}
	return nil
}

func decodeParameter(p advertisedParameter, raw []string, doc map[string]any) (any, error) {
	if p.location == "path" && p.style != "simple" || p.location == "query" && p.style != "form" {
		return nil, output.New(9, "unsupported parameter serialization style")
	}
	typ, e := parameterType(p.schema, doc, 0)
	if e != nil {
		return nil, e
	}
	if typ == "array" {
		obj, e := parameterSchemaObject(p.schema, doc, 0)
		if e != nil {
			return nil, e
		}
		items, exists := obj["items"]
		if !exists {
			return nil, output.New(9, "array parameter items schema is not advertised")
		}
		fields := raw
		if !p.explode || p.location == "path" {
			if len(raw) != 1 {
				return nil, output.New(2, "non-exploded array parameter must occur once: "+p.name)
			}
			fields = strings.Split(raw[0], ",")
		}
		if len(fields) > 10000 {
			return nil, output.New(2, "array parameter exceeds 10000 items")
		}
		values := []any{}
		for _, field := range fields {
			item := p
			item.schema = items
			itemType, e := parameterType(items, doc, 0)
			if e != nil {
				return nil, e
			}
			if itemType == "array" || itemType == "object" {
				return nil, output.New(9, "nested parameter arrays/objects are not supported")
			}
			value, e := decodeParameter(item, []string{field}, doc)
			if e != nil {
				return nil, e
			}
			values = append(values, value)
		}
		return values, nil
	}
	if len(raw) != 1 {
		return nil, output.New(2, "scalar parameter must occur exactly once: "+p.name)
	}
	switch typ {
	case "", "string":
		return raw[0], nil
	case "boolean":
		if raw[0] == "true" {
			return true, nil
		}
		if raw[0] == "false" {
			return false, nil
		}
		return nil, output.New(2, "boolean parameter must be true or false: "+p.name)
	case "integer", "number":
		d := json.NewDecoder(strings.NewReader(raw[0]))
		d.UseNumber()
		var value any
		if e := d.Decode(&value); e != nil {
			return nil, output.New(2, "invalid numeric parameter: "+p.name)
		}
		if _, ok := value.(json.Number); !ok {
			return nil, output.New(2, "invalid numeric parameter: "+p.name)
		}
		var extra any
		if d.Decode(&extra) != io.EOF {
			return nil, output.New(2, "ambiguous numeric parameter: "+p.name)
		}
		return value, nil
	default:
		return nil, output.New(9, "unsupported parameter schema type")
	}

}

// Infer serialization only when all non-null declarations agree on one type.
func parameterType(schema any, doc map[string]any, depth int) (string, error) {
	if depth > 16 {
		return "", output.New(9, "parameter schema composition exceeds 16")
	}
	if b, ok := schema.(bool); ok {
		if b {
			return "string", nil
		}
		return "", output.New(9, "false parameter schema")
	}
	obj, ok := schema.(map[string]any)
	if !ok {
		return "", output.New(9, "invalid parameter schema")
	}
	types := map[string]bool{}
	add := func(t string) {
		if t != "null" && t != "" {
			types[t] = true
		}
	}
	if raw, exists := obj["type"]; exists {
		switch t := raw.(type) {
		case string:
			add(t)
		case []any:
			for _, v := range t {
				name, ok := v.(string)
				if !ok {
					return "", output.New(9, "invalid parameter type")
				}
				add(name)
			}
		default:
			return "", output.New(9, "invalid parameter type")
		}
	}
	if ref, exists := obj["$ref"]; exists {
		name, ok := ref.(string)
		if !ok {
			return "", output.New(9, "invalid parameter reference")
		}
		target, e := schemacheck.Resolve(doc, name)
		if e != nil {
			return "", schemaError(e)
		}
		typ, e := parameterType(target, doc, depth+1)
		if e != nil {
			return "", e
		}
		add(typ)
	}
	for _, key := range []string{"allOf", "anyOf", "oneOf"} {
		if raw, exists := obj[key]; exists {
			branches, ok := raw.([]any)
			if !ok || len(branches) == 0 || len(branches) > 128 {
				return "", output.New(9, "invalid parameter composition")
			}
			for _, branch := range branches {
				typ, e := parameterType(branch, doc, depth+1)
				if e != nil {
					return "", e
				}
				add(typ)
			}
		}
	}
	if len(types) > 1 {
		return "", output.New(9, "ambiguous parameter serialization type")
	}
	for typ := range types {
		return typ, nil
	}
	if obj["type"] == "null" {
		return "null", nil
	}
	return "", nil
}

func parameterSchemaObject(schema any, doc map[string]any, depth int) (map[string]any, error) {
	if depth > 16 {
		return nil, output.New(9, "array parameter reference chain exceeds 16")
	}
	obj, ok := schema.(map[string]any)
	if !ok {
		return nil, output.New(9, "invalid array parameter schema")
	}
	if _, ok := obj["items"]; ok {
		return obj, nil
	}
	if ref, ok := obj["$ref"].(string); ok {
		target, e := schemacheck.Resolve(doc, ref)
		if e != nil {
			return nil, schemaError(e)
		}
		return parameterSchemaObject(target, doc, depth+1)
	}
	return nil, output.New(9, "array serialization requires an explicit items schema")
}

func validateOperationParameters(doc map[string]any, op Operation, values map[string]string, query url.Values) error {
	path, def, template, e := advertisedOperation(doc, op)
	if e != nil {
		return e
	}
	canonical := placeholders.FindAllStringSubmatch(op.Path, -1)
	advertised := placeholders.FindAllStringSubmatch(template, -1)
	translated := map[string]string{}
	for k, v := range values {
		translated[k] = v
	}
	for i, p := range canonical {
		if i >= len(advertised) {
			return output.New(9, "advertised path parameter count differs")
		}
		if value, ok := values[p[1]]; ok {
			delete(translated, p[1])
			translated[advertised[i][1]] = value
		}
	}
	return validateParameterSchema(doc, path, def, translated, query)
}

func (a *App) manifestParameterValues(op Operation, s manifest.Step) (map[string]string, url.Values, error) {
	if len(a.Query) > 0 {
		return nil, nil, output.New(2, "manifest parameter validation does not accept global query overrides")
	}
	values := map[string]string{}
	for i, name := range op.Params {
		if i >= len(s.Args) {
			return nil, nil, output.New(2, "manifest resource argument is missing")
		}
		values[name] = s.Args[i]
	}
	for _, name := range []string{"workspace_id", "project_id"} {
		if strings.Contains(op.Path, "{"+name+"}") {
			value := a.Workspace
			if name == "project_id" {
				value = a.Project
			}
			values[name] = value
		}
	}
	query := url.Values{}
	if op.QueryScope != "" {
		value := a.Project
		if op.QueryScope == "workspace_id" {
			value = a.Workspace
		}
		query.Set(op.QueryScope, value)
	}
	return values, query, nil
}
