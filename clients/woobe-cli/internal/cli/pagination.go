package cli

import (
	"net/url"
	"strconv"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
)

// These contracts were reviewed against Woobe 77c53832 (2026-10-05).
// Unknown endpoints retain explicit Link traversal, without a body heuristic.
var paginationRoutes = map[string]controlplane.PaginationContract{
	"/identity/workspaces/{workspace_id}/authority-categories":                        controlplane.CursorComplete,
	"/identity/workspaces/{workspace_id}/authority-categories/{category_id}/versions": controlplane.RevisionComplete,
	"/identity/workspaces/{workspace_id}/authority-audit":                             controlplane.CursorComplete,
	"/runtime/agents/{agent_id}/sessions":                                             controlplane.CursorHasNext,
}

func paginationForPath(path string) controlplane.PaginationContract {
	for route, contract := range paginationRoutes {
		expected, actual := strings.Split(route, "/"), strings.Split(path, "/")
		if len(expected) != len(actual) {
			continue
		}
		match := true
		for i, segment := range expected {
			if strings.HasPrefix(segment, "{") && actual[i] != "" {
				continue
			}
			if segment != actual[i] {
				match = false
				break
			}
		}
		if match {
			return contract
		}
	}
	return ""
}

type paginationOptions struct {
	all             bool
	limit, maxPages int
	marker          string
}

func (p *paginationOptions) flags(cmd *cobra.Command, contract controlplane.PaginationContract) {
	cmd.Flags().BoolVar(&p.all, "all", false, "Traverse every remaining page under the reviewed endpoint contract")
	cmd.Flags().IntVar(&p.limit, "limit", 0, "Page size; otherwise retain the server default")
	cmd.Flags().IntVar(&p.maxPages, "max-pages", 20, "Bounded page count for --all (1 to 100)")
	cmd.Flags().StringVar(&p.marker, strings.ReplaceAll(contract.Marker(), "_", "-"), "", "Explicit continuation marker")
}

func (p paginationOptions) validate(cmd *cobra.Command, contract controlplane.PaginationContract) error {
	maximum := 200
	if contract == controlplane.CursorHasNext {
		maximum = 100
	}
	if cmd.Flags().Changed("limit") && (p.limit < 1 || p.limit > maximum) {
		return output.New(2, "limit must be between 1 and "+strconv.Itoa(maximum))
	}
	if p.maxPages < 1 || p.maxPages > 100 {
		return output.New(2, "max-pages must be between 1 and 100")
	}
	if cmd.Flags().Changed("max-pages") && !p.all {
		return output.New(2, "max-pages requires --all")
	}
	markerFlag := strings.ReplaceAll(contract.Marker(), "_", "-")
	if cmd.Flags().Changed(markerFlag) && strings.TrimSpace(p.marker) == "" {
		return output.New(2, "continuation marker must not be empty")
	}
	if contract == controlplane.RevisionComplete && p.marker != "" {
		n, e := strconv.ParseInt(p.marker, 10, 64)
		if e != nil || n < 1 {
			return output.New(2, "before-revision must be a positive integer")
		}
	}
	return nil
}

func (p paginationOptions) query(q url.Values, contract controlplane.PaginationContract) error {
	for _, pair := range [][2]string{{"limit", strconv.Itoa(p.limit)}, {contract.Marker(), p.marker}} {
		if (pair[0] == "limit" && p.limit == 0) || pair[1] == "" {
			continue
		}
		if values, exists := q[pair[0]]; exists && (len(values) != 1 || values[0] != pair[1]) {
			return output.New(2, "conflicting pagination query "+pair[0])
		}
		q.Set(pair[0], pair[1])
	}
	maximum := 200
	if contract == controlplane.CursorHasNext {
		maximum = 100
	}
	if values, exists := q["limit"]; exists {
		if len(values) != 1 {
			return output.New(2, "limit requires a single value")
		}
		n, e := strconv.Atoi(values[0])
		if e != nil || n < 1 || n > maximum {
			return output.New(2, "limit must be between 1 and "+strconv.Itoa(maximum))
		}
	}
	if values, exists := q[contract.Marker()]; exists {
		if len(values) != 1 || strings.TrimSpace(values[0]) == "" {
			return output.New(2, "continuation marker requires a single nonempty value")
		}
		if contract == controlplane.RevisionComplete {
			n, e := strconv.ParseInt(values[0], 10, 64)
			if e != nil || n < 1 {
				return output.New(2, "before_revision must be a positive integer")
			}
		}
	}
	return nil
}

func (a *App) paginatedCall(cmd *cobra.Command, path string, options paginationOptions, contract controlplane.PaginationContract) error {
	if e := controlplane.ValidatePath(path); e != nil {
		return e
	}
	q, e := a.query()
	if e != nil {
		return e
	}
	if e = options.query(q, contract); e != nil {
		return e
	}
	if a.DryRun {
		return a.emit(map[string]any{"method": "GET", "path": path, "query": q, "pagination": contract, "all": options.all, "max_pages": options.maxPages, "executed": false})
	}
	client, e := a.client()
	if e != nil {
		return e
	}
	if options.all {
		pages, err := client.RequestPagesWithContract(cmd.Context(), path, q, options.maxPages, contract)
		return a.emitPages(pages, err)
	}
	v, _, e := client.Request(cmd.Context(), "GET", path, q, nil)
	if e != nil {
		return e
	}
	state, e := controlplane.InspectPage(v, q, contract)
	if e != nil {
		return pageFailure(v, state.Metadata(), e)
	}
	return a.writeOutput(a.Out, output.Redact(v), map[string]string{"workspace_id": a.Workspace, "project_id": a.Project}, nil, state.Metadata())
}

func pageFailure(data any, meta map[string]any, err error) error {
	cause := output.Normalize(err)
	code := 10
	if cause.Code == 130 || cause.Code == 8 {
		code = cause.Code
	}
	return &partialPages{Code: code, Data: data, Meta: meta, Cause: cause, Message: "page traversal stopped: " + cause.Message}
}

func (a *App) emitPages(pages controlplane.Pages, err error) error {
	if err != nil {
		if pages.Count == 0 {
			return err
		}
		return pageFailure(pages, pages.Metadata(), err)
	}
	return a.writeOutput(a.Out, output.Redact(pages), map[string]string{"workspace_id": a.Workspace, "project_id": a.Project}, nil, pages.Metadata())
}
