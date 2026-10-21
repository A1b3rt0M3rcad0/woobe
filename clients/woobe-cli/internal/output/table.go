package output

import (
	"encoding/json"
	"fmt"
	"io"
	"sort"
	"strings"
	"text/tabwriter"
)

func renderTable(w io.Writer, data any, err error) error {
	if err != nil {
		e := Normalize(err)
		_, writeErr := fmt.Fprintf(w, "ERROR %d: %s\n", e.Code, e.Message)
		return writeErr
	}
	// Normalize DTOs without mutating output data. Secrets were redacted before rendering.
	b, e := json.Marshal(data)
	if e != nil {
		return e
	}
	var v any
	if e = json.Unmarshal(b, &v); e != nil {
		return e
	}
	if obj, ok := v.(map[string]any); ok {
		if nested, ok := obj["data"]; ok {
			v = nested
		}
	}
	tw := tabwriter.NewWriter(w, 0, 4, 2, ' ', 0)
	cell := func(v any) string {
		if s, ok := v.(string); ok {
			return strings.NewReplacer("\t", " ", "\r", " ", "\n", " ").Replace(s)
		}
		b, _ := json.Marshal(v)
		return string(b)
	}
	switch x := v.(type) {
	case []any:
		columns := map[string]bool{}
		objects := true
		for _, row := range x {
			obj, ok := row.(map[string]any)
			if !ok {
				objects = false
				break
			}
			for k := range obj {
				columns[k] = true
			}
		}
		if len(x) == 0 {
			_, e = fmt.Fprintln(tw, "No results.")
			break
		}
		if !objects {
			_, e = fmt.Fprintln(tw, "VALUE")
			for _, row := range x {
				if e != nil {
					break
				}
				_, e = fmt.Fprintln(tw, cell(row))
			}
			break
		}
		headers := []string{}
		for k := range columns {
			headers = append(headers, k)
		}
		sort.Strings(headers)
		_, e = fmt.Fprintln(tw, strings.ToUpper(strings.Join(headers, "\t")))
		for _, row := range x {
			if e != nil {
				break
			}
			obj := row.(map[string]any)
			cells := make([]string, len(headers))
			for i, key := range headers {
				cells[i] = cell(obj[key])
			}
			_, e = fmt.Fprintln(tw, strings.Join(cells, "\t"))
		}
	case map[string]any:
		_, e = fmt.Fprintln(tw, "FIELD\tVALUE")
		keys := []string{}
		for k := range x {
			keys = append(keys, k)
		}
		sort.Strings(keys)
		for _, k := range keys {
			if e != nil {
				break
			}
			_, e = fmt.Fprintf(tw, "%s\t%s\n", k, cell(x[k]))
		}
	default:
		_, e = fmt.Fprintln(tw, cell(v))
	}
	if e != nil {
		return e
	}
	return tw.Flush()
}
