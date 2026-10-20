package devworkspace

import (
	"reflect"
	"sort"
	"strings"
)

type Change struct {
	Path   string `json:"path"`
	Status string `json:"status"`
}
type Conflict struct {
	Path string `json:"path"`
}
type field struct {
	value  any
	exists bool
}

// Merge compares values and presence separately. Independent object edits merge;
// lists are atomic so node order, duplicates and JSON null retain their meaning.
func Merge(base, local, remote map[string]any) (map[string]any, []Conflict) {
	conflicts := []Conflict{}
	var merge func(field, field, field, string) field
	equal := func(a, b field) bool { return a.exists == b.exists && reflect.DeepEqual(a.value, b.value) }
	merge = func(b, l, r field, p string) field {
		if equal(l, r) {
			return l
		}
		if equal(l, b) {
			return r
		}
		if equal(r, b) {
			return l
		}
		bm, bok := b.value.(map[string]any)
		lm, lok := l.value.(map[string]any)
		rm, rok := r.value.(map[string]any)
		if lok && rok && (bok || !b.exists) {
			result := map[string]any{}
			keys := map[string]bool{}
			for k := range bm {
				keys[k] = true
			}
			for k := range lm {
				keys[k] = true
			}
			for k := range rm {
				keys[k] = true
			}
			ordered := []string{}
			for k := range keys {
				ordered = append(ordered, k)
			}
			sort.Strings(ordered)
			for _, k := range ordered {
				bv, be := bm[k]
				lv, le := lm[k]
				rv, re := rm[k]
				escaped := strings.ReplaceAll(strings.ReplaceAll(k, "~", "~0"), "/", "~1")
				next := merge(field{bv, be}, field{lv, le}, field{rv, re}, p+"/"+escaped)
				if next.exists {
					result[k] = next.value
				}
			}
			return field{result, true}
		}
		conflicts = append(conflicts, Conflict{p})
		return l
	}
	result := merge(field{base, true}, field{local, true}, field{remote, true}, "")
	return result.value.(map[string]any), conflicts
}

func Diff(base, next map[string]any) []Change {
	changes := []Change{}
	var visit func(field, field, string)
	visit = func(a, b field, p string) {
		if a.exists == b.exists && reflect.DeepEqual(a.value, b.value) {
			return
		}
		am, ao := a.value.(map[string]any)
		bm, bo := b.value.(map[string]any)
		if ao && bo {
			keys := map[string]bool{}
			for k := range am {
				keys[k] = true
			}
			for k := range bm {
				keys[k] = true
			}
			ordered := []string{}
			for k := range keys {
				ordered = append(ordered, k)
			}
			sort.Strings(ordered)
			for _, k := range ordered {
				av, ae := am[k]
				bv, be := bm[k]
				visit(field{av, ae}, field{bv, be}, p+"/"+strings.ReplaceAll(strings.ReplaceAll(k, "~", "~0"), "/", "~1"))
			}
			return
		}
		status := "modified"
		if !a.exists {
			status = "added"
		}
		if !b.exists {
			status = "removed"
		}
		changes = append(changes, Change{p, status})
	}
	visit(field{base, true}, field{next, true}, "")
	return changes
}
