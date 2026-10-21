package schemacheck

import (
	"net/url"
	"strconv"
	"strings"
)

func Resolve(doc any, ref string) (any, error) {
	if ref == "#" {
		return doc, nil
	}
	if !strings.HasPrefix(ref, "#/") {
		return nil, unsupported("$", "external schema references and anchors are not fetched")
	}
	fragment, e := url.PathUnescape(ref[1:])
	if e != nil {
		return nil, unsupported("$", "invalid reference fragment")
	}
	cur := doc
	for _, part := range strings.Split(fragment[1:], "/") {
		for i := 0; i < len(part); i++ {
			if part[i] == '~' {
				if i+1 >= len(part) || (part[i+1] != '0' && part[i+1] != '1') {
					return nil, unsupported("$", "invalid JSON pointer escape")
				}
				i++
			}
		}
		part = strings.ReplaceAll(strings.ReplaceAll(part, "~1", "/"), "~0", "~")
		switch x := cur.(type) {
		case map[string]any:
			var ok bool
			cur, ok = x[part]
			if !ok {
				return nil, unsupported("$", "unresolved local schema reference")
			}
		case []any:
			i, e := strconv.Atoi(part)
			if e != nil || i < 0 || i >= len(x) || strconv.Itoa(i) != part {
				return nil, unsupported("$", "unresolved array schema reference")
			}
			cur = x[i]
		default:
			return nil, unsupported("$", "unresolved local schema reference")
		}
	}
	return cur, nil
}
