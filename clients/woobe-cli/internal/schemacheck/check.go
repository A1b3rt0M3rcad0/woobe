package schemacheck

import (
	"encoding/json"
	"fmt"
	"math/big"
	"regexp"
	"sort"
	"strconv"
	"strings"
	"unicode/utf8"
)

type Error struct {
	Path, Rule  string
	Unsupported bool
}

func (e *Error) Error() string      { return fmt.Sprintf("schema check at %s: %s", e.Path, e.Rule) }
func fail(p, r string) error        { return &Error{Path: p, Rule: r} }
func unsupported(p, r string) error { return &Error{Path: p, Rule: r, Unsupported: true} }

// Check implements a bounded, explicit schema subset. Unknown assertions fail closed.
func Check(schema, value, document any) error {
	return checkDocument(schema, value, document, false)
}

// CheckRequest applies OpenAPI request direction: read-only fields cannot be sent.
func CheckRequest(schema, value, document any) error {
	return checkDocument(schema, value, document, true)
}

func checkDocument(schema, value, document any, request bool) error {
	budget := 100000
	if e := valueWork(value, 0, &budget); e != nil {
		return e
	}
	if e := inspect(schema, document, "$", 0, map[string]bool{}, &budget, request, false, modernDialect(document)); e != nil {
		return e
	}
	return check(schema, value, document, "$", 0, &budget, request)
}
func equal(a, b any) bool {
	if x, y := number(a), number(b); x != nil || y != nil {
		return x != nil && y != nil && x.Cmp(y) == 0
	}
	switch x := a.(type) {
	case map[string]any:
		y, ok := b.(map[string]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for k, v := range x {
			w, ok := y[k]
			if !ok || !equal(v, w) {
				return false
			}
		}
		return true
	case []any:
		y, ok := b.([]any)
		if !ok || len(x) != len(y) {
			return false
		}
		for i, v := range x {
			if !equal(v, y[i]) {
				return false
			}
		}
		return true
	}
	x, _ := json.Marshal(a)
	y, _ := json.Marshal(b)
	return string(x) == string(y)
}
func number(v any) *big.Rat {
	var text string
	switch x := v.(type) {
	case json.Number:
		text = x.String()
	case float64:
		text = fmt.Sprint(x)
	default:
		return nil
	}
	if len(text) > 4096 {
		return nil
	}
	if i := strings.IndexAny(text, "eE"); i >= 0 {
		exp, e := strconv.Atoi(text[i+1:])
		if e != nil || exp > 4096 || exp < -4096 {
			return nil
		}
	}
	r, _ := new(big.Rat).SetString(text)
	return r
}
func typeOK(t string, v any) bool {
	switch t {
	case "null":
		return v == nil
	case "object":
		_, ok := v.(map[string]any)
		return ok
	case "array":
		_, ok := v.([]any)
		return ok
	case "string":
		_, ok := v.(string)
		return ok
	case "boolean":
		_, ok := v.(bool)
		return ok
	case "number":
		return number(v) != nil
	case "integer":
		n := number(v)
		return n != nil && n.IsInt()
	}
	return false
}
func check(raw, v, doc any, p string, depth int, budget *int, request bool) error {
	*budget--
	if *budget < 0 {
		return unsupported(p, "schema evaluation budget exceeded")
	}
	if depth > 64 {
		return unsupported(p, "schema depth exceeds 64")
	}
	if b, ok := raw.(bool); ok {
		if !b {
			return fail(p, "false schema")
		}
		return nil
	}
	s, ok := raw.(map[string]any)
	if !ok {
		return unsupported(p, "schema must be object or boolean")
	}
	if e := schemaHeader(s, p); e != nil {
		return e
	}
	if request && s["readOnly"] == true {
		return fail(p, "read-only field cannot be sent in a request")
	}
	if ref, ok := s["$ref"].(string); ok {
		target, e := Resolve(doc, ref)
		if e != nil {
			return e
		}
		if e = check(target, v, doc, p, depth+1, budget, request); e != nil {
			return e
		}
	}
	for _, key := range []string{"allOf", "anyOf", "oneOf"} {
		if raw, ok := s[key]; ok {
			branches, ok := raw.([]any)
			if !ok || len(branches) == 0 {
				return unsupported(p, "invalid composition")
			}
			matches := 0
			for _, b := range branches {
				e := check(b, v, doc, p, depth+1, budget, request)
				if x, ok := e.(*Error); ok && x.Unsupported {
					return e
				}
				if e == nil {
					matches++
				}
			}
			if key == "allOf" && matches != len(branches) || key == "anyOf" && matches == 0 || key == "oneOf" && matches != 1 {
				return fail(p, key+" mismatch")
			}
		}
	}
	if b, ok := s["not"]; ok {
		e := check(b, v, doc, p, depth+1, budget, request)
		if x, ok := e.(*Error); ok && x.Unsupported {
			return e
		}
		if e == nil {
			return fail(p, "not mismatch")
		}
	}
	if cond, ok := s["if"]; ok {
		e := check(cond, v, doc, p, depth+1, budget, request)
		if x, ok := e.(*Error); ok && x.Unsupported {
			return e
		}
		branch := "else"
		if e == nil {
			branch = "then"
		}
		if sub, ok := s[branch]; ok {
			if e := check(sub, v, doc, p, depth+1, budget, request); e != nil {
				return e
			}
		}
	}
	if typ, ok := s["type"]; ok && !(v == nil && s["nullable"] == true) {
		if e := validType(typ, p); e != nil {
			return e
		}
		matched := false
		switch t := typ.(type) {
		case string:
			matched = typeOK(t, v)
		case []any:
			for _, t := range t {
				if name, ok := t.(string); ok && typeOK(name, v) {
					matched = true
				}
			}
		default:
			return unsupported(p, "invalid type declaration")
		}
		if !matched {
			return fail(p, "type mismatch")
		}
	}
	if c, ok := s["const"]; ok && !equal(c, v) {
		return fail(p, "const mismatch")
	}
	if e, ok := s["enum"].([]any); ok {
		match := false
		for _, x := range e {
			match = match || equal(x, v)
		}
		if !match {
			return fail(p, "enum mismatch")
		}
	}
	if obj, ok := v.(map[string]any); ok {
		if e := bounds(s, "minProperties", "maxProperties", len(obj), p); e != nil {
			return e
		}
		if req, ok := s["required"].([]any); ok {
			for _, r := range req {
				name, ok := r.(string)
				if !ok {
					return unsupported(p, "invalid required field")
				}
				if _, ok := obj[name]; !ok {
					if request {
						props, _ := s["properties"].(map[string]any)
						ro, e := requestReadOnly(props[name], doc, p+"."+name, depth+1, budget)
						if e != nil {
							return e
						}
						if ro {
							continue
						}
					}
					return fail(p, "required field absent: "+name)
				}
			}
		}
		if deps, ok := s["dependentRequired"].(map[string]any); ok {
			for k, raw := range deps {
				if _, exists := obj[k]; exists {
					for _, name := range raw.([]any) {
						if _, exists := obj[name.(string)]; !exists {
							return fail(p, "dependent required field absent")
						}
					}
				}
			}
		}
		if deps, ok := s["dependentSchemas"].(map[string]any); ok {
			for k, sub := range deps {
				if _, exists := obj[k]; exists {
					if e := check(sub, v, doc, p, depth+1, budget, request); e != nil {
						return e
					}
				}
			}
		}
		props, _ := s["properties"].(map[string]any)
		keys := []string{}
		for k := range obj {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			if sub, ok := s["propertyNames"]; ok {
				if e := check(sub, k, doc, p, depth+1, budget, request); e != nil {
					return e
				}
			}
			matched := false
			if sub, ok := props[k]; ok {
				matched = true
				if e := check(sub, obj[k], doc, p+"."+k, depth+1, budget, request); e != nil {
					return e
				}
			}
			if patterns, ok := s["patternProperties"].(map[string]any); ok {
				for pattern, sub := range patterns {
					if regexp.MustCompile(pattern).MatchString(k) {
						matched = true
						if e := check(sub, obj[k], doc, p+"."+k, depth+1, budget, request); e != nil {
							return e
						}
					}
				}
			}
			if sub, ok := s["additionalProperties"]; ok && !matched {
				if e := check(sub, obj[k], doc, p+"."+k, depth+1, budget, request); e != nil {
					return e
				}
			}
		}
	}
	if a, ok := v.([]any); ok {
		if e := bounds(s, "minItems", "maxItems", len(a), p); e != nil {
			return e
		}
		if sub, ok := s["contains"]; ok {
			matches := 0
			for i, x := range a {
				e := check(sub, x, doc, fmt.Sprintf("%s[%d]", p, i), depth+1, budget, request)
				if y, ok := e.(*Error); ok && y.Unsupported {
					return e
				}
				if e == nil {
					matches++
				}
			}
			limits := map[string]any{"minContains": json.Number("1")}
			for _, k := range []string{"minContains", "maxContains"} {
				if n, ok := s[k]; ok {
					limits[k] = n
				}
			}
			if e := bounds(limits, "minContains", "maxContains", matches, p); e != nil {
				return e
			}
		}
		seen := map[string]bool{}
		for i, x := range a {
			if s["uniqueItems"] == true {
				key := semanticKey(x)
				if seen[key] {
					return fail(p, "duplicate array item")
				}
				seen[key] = true
			}
			prefix, _ := s["prefixItems"].([]any)
			if i < len(prefix) {
				if e := check(prefix[i], x, doc, fmt.Sprintf("%s[%d]", p, i), depth+1, budget, request); e != nil {
					return e
				}
				continue
			}
			if sub, ok := s["items"]; ok {
				if e := check(sub, x, doc, fmt.Sprintf("%s[%d]", p, i), depth+1, budget, request); e != nil {
					return e
				}
			}
		}
	}
	if text, ok := v.(string); ok {
		if format, ok := s["format"].(string); ok && !formatOK(format, text) {
			return fail(p, "format mismatch: "+format)
		}
		if e := bounds(s, "minLength", "maxLength", utf8.RuneCountInString(text), p); e != nil {
			return e
		}
		if pattern, ok := s["pattern"].(string); ok {
			r, e := regexp.Compile(pattern)
			if e != nil {
				return unsupported(p, "pattern incompatible with RE2")
			}
			if !r.MatchString(text) {
				return fail(p, "pattern mismatch")
			}
		}
	}
	if n := number(v); n != nil {
		for _, k := range []string{"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"} {
			limit, ok := s[k]
			if !ok {
				continue
			}
			l := number(limit)
			if l == nil {
				return unsupported(p, "numeric assertion unsupported: "+k)
			}
			c := n.Cmp(l)
			bad := k == "minimum" && c < 0 || k == "maximum" && c > 0 || k == "exclusiveMinimum" && c <= 0 || k == "exclusiveMaximum" && c >= 0
			if k == "multipleOf" {
				if l.Sign() <= 0 {
					return unsupported(p, "invalid multipleOf")
				}
				bad = !new(big.Rat).Quo(n, l).IsInt()
			}
			if bad {
				return fail(p, k+" constraint")
			}
		}
	}
	return nil
}
func bounds(s map[string]any, min, max string, n int, p string) error {
	for _, k := range []string{min, max} {
		if v, ok := s[k]; ok {
			limit := number(v)
			if limit == nil || !limit.IsInt() {
				return unsupported(p, "invalid "+k)
			}
			c := new(big.Rat).SetInt64(int64(n)).Cmp(limit)
			if k == min && c < 0 || k == max && c > 0 {
				return fail(p, k+" constraint")
			}
		}
	}
	return nil
}

func semanticKey(v any) string {
	if n := number(v); n != nil {
		return "n:" + n.RatString()
	}
	switch x := v.(type) {
	case []any:
		parts := []string{}
		for _, v := range x {
			parts = append(parts, semanticKey(v))
		}
		b, _ := json.Marshal(parts)
		return "a:" + string(b)
	case map[string]any:
		m := map[string]string{}
		for k, v := range x {
			m[k] = semanticKey(v)
		}
		b, _ := json.Marshal(m)
		return "o:" + string(b)
	}
	b, _ := json.Marshal(v)
	return "v:" + string(b)
}
