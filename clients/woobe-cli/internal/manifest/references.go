package manifest

import (
	"bytes"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
)

var reference = regexp.MustCompile(`^\$\{steps\.([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_.-]+)\}$`)

func Resolve(v any, results map[string]any) (any, error) {
	switch x := v.(type) {
	case string:
		m := reference.FindStringSubmatch(x)
		if m == nil {
			return x, nil
		}
		cur, ok := results[m[1]]
		if !ok {
			return nil, fmt.Errorf("unresolved step %s", m[1])
		}
		for _, key := range strings.Split(m[2], ".") {
			obj, ok := cur.(map[string]any)
			if !ok {
				return nil, fmt.Errorf("invalid reference %s", x)
			}
			cur, ok = obj[key]
			if !ok {
				return nil, fmt.Errorf("missing referenced field %s", x)
			}
		}
		if cur == "[REDACTED]" {
			return nil, fmt.Errorf("secret references are forbidden")
		}
		return cur, nil
	case map[string]any:
		out := map[string]any{}
		for k, value := range x {
			r, e := Resolve(value, results)
			if e != nil {
				return nil, e
			}
			out[k] = r
		}
		return out, nil
	case []any:
		out := make([]any, len(x))
		for i, value := range x {
			r, e := Resolve(value, results)
			if e != nil {
				return nil, e
			}
			out[i] = r
		}
		return out, nil
	default:
		return v, nil
	}
}
func ResolveStep(s Step, results map[string]any) (Step, error) {
	args := make([]string, len(s.Args))
	for i, arg := range s.Args {
		v, e := Resolve(arg, results)
		if e != nil {
			return s, e
		}
		text, ok := v.(string)
		if !ok {
			return s, fmt.Errorf("resource ID reference must resolve to string")
		}
		args[i] = text
	}
	s.Args = args
	if len(s.Body) > 0 {
		var body any
		dec := json.NewDecoder(bytes.NewReader(s.Body))
		dec.UseNumber()
		if e := dec.Decode(&body); e != nil {
			return s, e
		}
		body, e := Resolve(body, results)
		if e != nil {
			return s, e
		}
		s.Body, e = json.Marshal(body)
		if e != nil {
			return s, e
		}
	}
	return s, nil
}

// ValidateReferences requires every referenced step to be an explicit dependency.
func ValidateReferences(s Step) error {
	deps := map[string]bool{}
	for _, id := range s.DependsOn {
		if deps[id] {
			return fmt.Errorf("duplicate dependency in step %s", s.ID)
		}
		if id == s.ID {
			return fmt.Errorf("step cannot depend on itself")
		}
		deps[id] = true
	}
	var check func(any) error
	check = func(v any) error {
		switch x := v.(type) {
		case string:
			if m := reference.FindStringSubmatch(x); m != nil && !deps[m[1]] {
				return fmt.Errorf("reference to %s requires depends_on in %s", m[1], s.ID)
			}
		case map[string]any:
			for _, v := range x {
				if e := check(v); e != nil {
					return e
				}
			}
		case []any:
			for _, v := range x {
				if e := check(v); e != nil {
					return e
				}
			}
		}
		return nil
	}
	for _, arg := range s.Args {
		if e := check(arg); e != nil {
			return e
		}
	}
	if len(s.Body) > 0 {
		var v any
		if e := json.Unmarshal(s.Body, &v); e != nil {
			return e
		}
		return check(v)
	}
	return nil
}
