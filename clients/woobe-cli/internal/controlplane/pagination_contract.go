package controlplane

import (
	"encoding/json"
	"net/url"
	"strconv"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

// PaginationContract describes a reviewed response protocol, never an inferred
// collection shape. All body protocols use data.items in the server envelope.
type PaginationContract string

const (
	LinkPages        PaginationContract = "link"
	CursorComplete   PaginationContract = "cursor-complete"
	CursorHasNext    PaginationContract = "cursor-has-next"
	RevisionComplete PaginationContract = "revision-complete"
)

func (p PaginationContract) Valid() bool {
	return p == LinkPages || p == CursorComplete || p == CursorHasNext || p == RevisionComplete
}

func (p PaginationContract) Marker() string {
	if p == RevisionComplete {
		return "before_revision"
	}
	if p == CursorComplete || p == CursorHasNext {
		return "cursor"
	}
	return ""
}

// PageState preserves the explicit continuation and whether enumeration began
// after a caller-supplied marker. Completion is live traversal, not a snapshot.
type PageState struct {
	Protocol           PaginationContract `json:"protocol"`
	TraversalComplete  bool               `json:"traversal_complete"`
	CollectionComplete string             `json:"collection_complete"`
	StartedFromMarker  bool               `json:"started_from_marker"`
	NextQuery          url.Values         `json:"next_query,omitempty"`
}

func (p PageState) Metadata() map[string]any {
	return map[string]any{
		"complete":            p.CollectionComplete == "verified",
		"pagination":          p.Protocol,
		"traversal_complete":  p.TraversalComplete,
		"collection_complete": p.CollectionComplete,
		"started_from_marker": p.StartedFromMarker,
		"consistency":         "live",
		"next_query":          p.NextQuery,
	}
}

func cloneQuery(q url.Values) url.Values {
	copy := url.Values{}
	for key, values := range q {
		copy[key] = append([]string(nil), values...)
	}
	return copy
}

func validatePageQuery(q url.Values, p PaginationContract) error {
	for _, key := range []string{"limit", p.Marker()} {
		if key == "" {
			continue
		}
		values := q[key]
		if len(values) > 1 || (len(values) == 1 && (strings.TrimSpace(values[0]) == "" || len(values[0]) > 8192)) {
			return output.New(2, "pagination query "+key+" must have one nonempty value")
		}
		if len(values) == 1 && (key == "limit" || key == "before_revision") {
			n, e := strconv.Atoi(values[0])
			if e != nil || n < 1 {
				return output.New(2, "pagination query "+key+" must be a positive integer")
			}
			if key == "limit" {
				maximum := 200
				if p == CursorHasNext {
					maximum = 100
				}
				if p != LinkPages && n > maximum {
					return output.New(2, "pagination limit exceeds the reviewed contract")
				}
			}
		}
	}
	return nil
}

func InitialPageState(q url.Values, p PaginationContract) PageState {
	return PageState{Protocol: p, CollectionComplete: "partial", StartedFromMarker: p.Marker() != "" && q.Get(p.Marker()) != ""}
}

// InspectPage refuses inconsistent/missing markers instead of declaring a
// truncated collection complete. It does not inspect arbitrary nested data.
func InspectPage(v any, q url.Values, p PaginationContract) (PageState, error) {
	state := InitialPageState(q, p)
	if !p.Valid() || p == LinkPages {
		return state, output.New(9, "body pagination requires a supported explicit contract")
	}
	if e := validatePageQuery(q, p); e != nil {
		return state, e
	}
	envelope, ok := v.(map[string]any)
	if !ok || envelope["success"] != true {
		return state, output.New(9, "pagination requires a successful server envelope")
	}
	data, ok := envelope["data"].(map[string]any)
	if !ok {
		return state, output.New(9, "pagination requires data.items and continuation metadata")
	}
	items, ok := data["items"].([]any)
	if !ok {
		return state, output.New(9, "pagination data.items must be an array")
	}
	terminalField, markerField := "complete", "next_cursor"
	if p == RevisionComplete {
		markerField = "next_revision"
	}
	if p == CursorHasNext {
		terminalField = "has_next"
	}
	flag, ok := data[terminalField].(bool)
	if !ok {
		return state, output.New(9, "pagination requires boolean "+terminalField)
	}
	terminal := flag
	if p == CursorHasNext {
		terminal = !flag
	}
	marker, exists := data[markerField]
	if !exists {
		return state, output.New(9, "pagination requires explicit "+markerField)
	}
	if terminal {
		if marker != nil {
			return state, output.New(9, "terminal page has a continuation marker")
		}
		state.TraversalComplete = true
		state.CollectionComplete = "verified"
		if state.StartedFromMarker {
			state.CollectionComplete = "remaining"
		}
		return state, nil
	}
	if len(items) == 0 {
		return state, output.New(9, "nonterminal page must contain items")
	}
	var next string
	if p == RevisionComplete {
		number, ok := marker.(json.Number)
		if !ok {
			return state, output.New(9, "next_revision must be a positive integer")
		}
		n, e := strconv.ParseInt(string(number), 10, 64)
		if e != nil || n < 1 {
			return state, output.New(9, "next_revision must be a positive integer")
		}
		next = strconv.FormatInt(n, 10)
		if current := q.Get(p.Marker()); current != "" {
			before, e := strconv.ParseInt(current, 10, 64)
			if e != nil || n >= before {
				return state, output.New(9, "revision pagination did not move backwards")
			}
		}
	} else {
		var ok bool
		next, ok = marker.(string)
		if !ok || strings.TrimSpace(next) == "" || len(next) > 8192 {
			return state, output.New(9, "next_cursor must be a nonempty bounded string")
		}
	}
	if next == q.Get(p.Marker()) {
		return state, output.New(9, "pagination marker did not advance")
	}
	state.NextQuery = cloneQuery(q)
	state.NextQuery.Set(p.Marker(), next)
	return state, nil
}
