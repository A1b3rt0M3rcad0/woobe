package controlplane

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"
	"unicode/utf8"
)

type Client struct {
	Base         string
	Token        string
	HTTP         *http.Client
	Headers      http.Header
	ResponseHook func(*http.Response) error
}

func New(base, token string, timeout time.Duration) (*Client, error) {
	u, e := url.Parse(base)
	if e != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") || u.User != nil || u.RawQuery != "" || u.Fragment != "" {
		return nil, output.New(2, "api URL must be an HTTP(S) origin without credentials, query or fragment")
	}
	if u.EscapedPath() != "" {
		if e := ValidatePath(u.EscapedPath()); e != nil {
			return nil, e
		}
	}
	h := &http.Client{Transport: sharedNoReplayTransport, Timeout: timeout, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	return &Client{Base: strings.TrimRight(base, "/"), Token: token, HTTP: h, Headers: make(http.Header)}, nil
}
func (c *Client) Request(ctx context.Context, method, path string, q url.Values, body []byte) (any, http.Header, error) {
	var reader io.Reader
	if body != nil {
		reader = bytes.NewReader(body)
	}
	return c.RequestReader(ctx, method, path, q, reader, "application/json")
}
func (c *Client) RequestReader(ctx context.Context, method, path string, q url.Values, body io.Reader, contentType string) (any, http.Header, error) {
	if e := ValidatePath(path); e != nil {
		return nil, nil, e
	}
	raw := c.Base + path
	if len(q) > 0 {
		raw += "?" + q.Encode()
	}
	req, e := http.NewRequestWithContext(ctx, method, raw, body)
	if e != nil {
		return nil, nil, output.New(2, "invalid request")
	}
	req.Header = c.Headers.Clone()
	if method == "GET" || method == "HEAD" {
		req.Header.Del("If-Match")
		req.Header.Del("Idempotency-Key")
	}
	req.Header.Set("Accept", "application/json")
	if c.Token != "" {
		req.Header.Set("Authorization", "Bearer "+c.Token)
	}
	if body != nil {
		req.Header.Set("Content-Type", contentType)
	}
	resp, e := c.HTTP.Do(req)
	if e != nil {
		err := output.Normalize(e)
		if err.Code == 1 {
			err.Code = 7
			err.Message = "HTTP connection failed"
		}
		if method != "GET" && method != "HEAD" {
			err.Outcome = "unknown"
		}
		return nil, nil, err
	}
	defer resp.Body.Close()
	if c.ResponseHook != nil {
		if e = c.ResponseHook(resp); e != nil {
			return nil, resp.Header, &output.Error{Code: 10, Message: "server responded but session persistence failed", Outcome: "unknown"}
		}
	}
	b, e := io.ReadAll(io.LimitReader(resp.Body, 32<<20+1))
	if e != nil {
		return nil, resp.Header, responseError(method, resp, 7, "response could not be read")
	}
	if len(b) > 32<<20 {
		return nil, resp.Header, responseError(method, resp, 9, "response exceeds limit")
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		code := 7
		switch resp.StatusCode {
		case 400, 422:
			code = 2
		case 401:
			code = 3
		case 403:
			code = 4
		case 404:
			code = 5
		case 409, 412:
			code = 6
		case 408, 504:
			code = 8
		case 405, 501:
			code = 9
		}
		outcome := "rejected"
		if resp.StatusCode >= 500 {
			outcome = "unknown"
		}
		failure := &output.Error{Code: code, Message: "server rejected request", Status: resp.StatusCode, RequestID: resp.Header.Get("X-Request-ID"), Outcome: outcome}
		if configurationDiagnostic(b, failure) {
			return nil, resp.Header, failure
		}
		// Package owns stable diagnostics. Preserve only bounded machine fields;
		// provider messages, input snapshots and protected values are omitted.
		if (strings.Contains(path, "/packages/") || asacDiagnosticPath(path)) && jsoninput.Validate(b) == nil {
			var envelope struct {
				Data struct {
					Version     string `json:"package_schema_version"`
					ASaCVersion string `json:"asac_schema_version"`
					Diagnostics []struct {
						Kind             string `json:"kind"`
						ResourceID       string `json:"resource_id"`
						ExpectedRevision string `json:"expected_revision"`
						ObservedRevision string `json:"observed_revision"`
						Code             string `json:"code"`
						File             string `json:"file"`
						Path             string `json:"path"`
						Message          string `json:"message"`
					} `json:"diagnostics"`
				} `json:"data"`
			}
			if json.Unmarshal(b, &envelope) == nil && ((envelope.Data.Version == "1.0" || envelope.Data.Version == "2.0") && strings.Contains(path, "/packages/") || envelope.Data.ASaCVersion == "1.0" && asacDiagnosticPath(path)) && len(envelope.Data.Diagnostics) <= 32 {
				prefix := "PACKAGE_"
				if asacDiagnosticPath(path) {
					prefix = "ASAC_"
				}
				machineCode := regexp.MustCompile(`^` + prefix + `[A-Z0-9_]{1,80}$`)
				safePath := regexp.MustCompile(`^[A-Za-z0-9_./~ -]*$`)
				for _, diagnostic := range envelope.Data.Diagnostics {
					if !machineCode.MatchString(diagnostic.Code) {
						continue
					}
					if len(diagnostic.File) > 1024 || !safePath.MatchString(diagnostic.File) {
						diagnostic.File = ""
					}
					if len(diagnostic.Path) > 1024 || !safePath.MatchString(diagnostic.Path) {
						diagnostic.Path = ""
					}
					bounded := output.DomainDiagnostic{Code: diagnostic.Code, File: diagnostic.File, Path: diagnostic.Path}
					revisionPattern := regexp.MustCompile(`^[A-Za-z0-9:+._-]{1,128}$`)
					if diagnostic.Code == "PACKAGE_REVISION_CONFLICT" {
						for _, kind := range []string{"Agent", "Network", "Model", "Tool", "Skill", "Knowledge", "Prompt", "Contract"} {
							if diagnostic.Kind == kind {
								bounded.Kind = kind
							}
						}
						if regexp.MustCompile(`^[a-fA-F0-9-]{36}$`).MatchString(diagnostic.ResourceID) {
							bounded.ResourceID = diagnostic.ResourceID
						}
						if revisionPattern.MatchString(diagnostic.ExpectedRevision) {
							bounded.ExpectedRevision = diagnostic.ExpectedRevision
						}
						if revisionPattern.MatchString(diagnostic.ObservedRevision) {
							bounded.ObservedRevision = diagnostic.ObservedRevision
						}
						failure.Message = "A dependency changed since the accepted local base; pull its owning Agent/Network, review the diff and plan again. package doctor checks compatibility; it does not refresh revisions"
					}
					failure.Diagnostics = append(failure.Diagnostics, bounded)
					if message := packageExportIncompleteMessage(diagnostic.Code, diagnostic.Message); message != "" && failure.Message == "server rejected request" {
						failure.Message = message
					}
				}
				if len(failure.Diagnostics) != 0 {
					failure.DomainCode = failure.Diagnostics[0].Code
				}
			}
		}
		return nil, resp.Header, failure
	}
	if method == "HEAD" || len(bytes.TrimSpace(b)) == 0 {
		return nil, resp.Header, nil
	}
	if jsoninput.Validate(b) != nil {
		return nil, resp.Header, responseError(method, resp, 9, "server returned ambiguous or invalid JSON")
	}
	var v any
	d := json.NewDecoder(bytes.NewReader(b))
	d.UseNumber()
	if e = d.Decode(&v); e != nil {
		return nil, resp.Header, responseError(method, resp, 9, "server returned non-JSON response")
	}
	if env, ok := v.(map[string]any); ok {
		if success, ok := env["success"].(bool); ok && !success {
			return nil, resp.Header, responseError(method, resp, 7, "server returned unsuccessful response")
		}
	}
	var extra any
	if d.Decode(&extra) != io.EOF {
		return nil, resp.Header, responseError(method, resp, 9, "server returned multiple JSON values")
	}
	return v, resp.Header, nil
}

func responseError(method string, resp *http.Response, code int, message string) *output.Error {
	outcome := ""
	if method != "GET" && method != "HEAD" {
		outcome = "unknown"
	}
	return &output.Error{Code: code, Message: message, Status: resp.StatusCode, RequestID: resp.Header.Get("X-Request-ID"), Outcome: outcome}
}

func ValidatePath(path string) error {
	if !strings.HasPrefix(path, "/") || strings.HasPrefix(path, "//") || strings.ContainsAny(path, "?#\\") {
		return output.New(2, "request path must be origin-relative; use --query for query parameters")
	}
	if !utf8.ValidString(path) {
		return output.New(2, "invalid path encoding")
	}
	for _, segment := range strings.Split(path, "/") {
		decoded, e := url.PathUnescape(segment)
		if e != nil || !utf8.ValidString(decoded) {
			return output.New(2, "invalid path escape")
		}
		if decoded == "." || decoded == ".." || strings.ContainsAny(decoded, "/\\%") {
			return output.New(2, "request path contains ambiguous segments")
		}
		for _, r := range decoded {
			if r < 32 || r == 127 {
				return output.New(2, "request path contains control characters")
			}
		}
	}
	return nil
}

// Legacy lifecycle endpoints expose the same bounded ASaC gate diagnostics.
// Preserve codes, never arbitrary server messages, bodies or protected values.
func asacDiagnosticPath(path string) bool {
	if strings.Contains(path, "/asac/") {
		return true
	}
	uuid := `[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}`
	routes := []string{
		`^/core/projects/` + uuid + `/lifecycle-policy(?:/operations/` + uuid + `)?$`,
		`^/ai/agents/` + uuid + `/releases(?:/` + uuid + `(?:/(?:promote|rollback))?)?$`,
		`^/network/` + uuid + `/(?:promotions(?:/preview)?|production/activations|rollback)$`,
	}
	for _, route := range routes {
		if regexp.MustCompile(route).MatchString(path) {
			return true
		}
	}
	return false
}
