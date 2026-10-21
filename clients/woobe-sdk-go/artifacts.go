package woobe

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strconv"
	"strings"
	"time"
)

// ArtifactEnvironment selects one isolated Project Environment. It does not
// imply access: every operation is authorized again by Woobe for the supplied
// Runtime Key and current Artifact grants.
type ArtifactEnvironment string

const (
	ArtifactDraft      ArtifactEnvironment = "draft"
	ArtifactStaging    ArtifactEnvironment = "staging"
	ArtifactProduction ArtifactEnvironment = "production"
)

// ArtifactsClient is scoped to one Project, Environment, and Runtime Key. It
// never accepts or falls back to an administrative Control Key.
type ArtifactsClient struct {
	client      *Client
	projectID   string
	environment ArtifactEnvironment
	runtimeKey  string
}

var artifactIdentifierPattern = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$`)

// Artifacts returns a direct Artifacts API client using a Runtime Key with the
// artifacts interface and explicit grants. No request Run or Session is made.
func (c *Client) Artifacts(projectID, runtimeKey string, environment ArtifactEnvironment) (*ArtifactsClient, error) {
	projectID = strings.TrimSpace(projectID)
	runtimeKey = strings.TrimSpace(runtimeKey)
	switch environment {
	case ArtifactDraft, ArtifactStaging, ArtifactProduction:
	default:
		return nil, &ProtocolError{Message: "artifact environment must be draft, staging, or production"}
	}
	if !artifactIdentifierPattern.MatchString(projectID) {
		return nil, &ProtocolError{Message: "projectID must be a valid opaque identifier"}
	}
	if runtimeKey == "" {
		return nil, &ProtocolError{Message: "Runtime Key must not be empty"}
	}
	return &ArtifactsClient{client: c, projectID: projectID, environment: environment, runtimeKey: runtimeKey}, nil
}

type ArtifactWorkspace struct {
	SchemaVersion          string              `json:"schema_version"`
	ID                     string              `json:"id"`
	ProjectID              string              `json:"project_id"`
	Environment            ArtifactEnvironment `json:"environment"`
	ExternalNamespace      string              `json:"external_namespace"`
	ExternalKey            string              `json:"external_key"`
	Name                   string              `json:"name"`
	Status                 string              `json:"status"`
	StorageProfile         string              `json:"storage_profile"`
	QuotaBytes             int64               `json:"quota_bytes"`
	UsedBytes              int64               `json:"used_bytes"`
	ReservedBytes          int64               `json:"reserved_bytes"`
	RetentionDays          int                 `json:"retention_days"`
	Version                int64               `json:"version"`
	CatalogVersion         int64               `json:"catalog_version"`
	DefaultProfileID       *string             `json:"default_profile_id"`
	DefaultProfileRevision *int64              `json:"default_profile_revision"`
	Labels                 map[string]string   `json:"labels"`
}

type CreateArtifactWorkspaceRequest struct {
	SchemaVersion     string              `json:"schema_version,omitempty"`
	Environment       ArtifactEnvironment `json:"environment,omitempty"`
	ExternalNamespace string              `json:"external_namespace"`
	ExternalKey       string              `json:"external_key"`
	Name              string              `json:"name"`
	StorageProfile    string              `json:"storage_profile,omitempty"`
	QuotaBytes        int64               `json:"quota_bytes,omitempty"`
	RetentionDays     int                 `json:"retention_days,omitempty"`
	Labels            map[string]string   `json:"labels,omitempty"`
}

type UpdateArtifactWorkspaceRequest struct {
	ExpectedVersion int64             `json:"expected_version"`
	Name            *string           `json:"name,omitempty"`
	Status          *string           `json:"status,omitempty"`
	Labels          map[string]string `json:"labels,omitempty"`
}

type ArtifactWorkspacePage struct {
	SchemaVersion string              `json:"schema_version"`
	Items         []ArtifactWorkspace `json:"items"`
	HasMore       bool                `json:"has_more"`
	NextCursor    string              `json:"next_cursor"`
	Truncated     bool                `json:"truncated"`
}

type ArtifactCapabilities struct {
	SchemaVersion      string   `json:"schema_version"`
	Processors         []string `json:"processors"`
	Indexers           []string `json:"indexers"`
	MediaTypes         []string `json:"media_types"`
	TransferModes      []string `json:"transfer_modes"`
	MaxUploadBytes     int64    `json:"max_upload_bytes"`
	MaxReadBytes       int64    `json:"max_read_bytes"`
	MaxPageSize        int      `json:"max_page_size"`
	MaxUploadPartBytes int64    `json:"max_upload_part_bytes"`
	MaxUploadParts     int      `json:"max_upload_parts"`
	MaxInlineBytes     int64    `json:"max_inline_bytes"`
	MaxRequestBytes    int64    `json:"max_request_bytes"`
	Downloads          []string `json:"downloads"`
	SignedUploadURLs   bool     `json:"signed_upload_urls"`
	StorageReadiness   string   `json:"storage_readiness"`
}

type ArtifactRevision struct {
	SchemaVersion string  `json:"schema_version"`
	ID            string  `json:"id"`
	ArtifactID    string  `json:"artifact_id"`
	ContentType   string  `json:"content_type"`
	SizeBytes     int64   `json:"size_bytes"`
	SHA256        string  `json:"sha256"`
	Origin        string  `json:"origin"`
	ProducerID    *string `json:"producer_id"`
	OperationID   *string `json:"operation_id"`
	RunID         *string `json:"run_id"`
	NodeID        *string `json:"node_id"`
}

type Artifact struct {
	SchemaVersion string            `json:"schema_version"`
	ID            string            `json:"id"`
	WorkspaceID   string            `json:"workspace_id"`
	Path          string            `json:"path"`
	Kind          string            `json:"kind"`
	RevisionID    *string           `json:"revision_id"`
	Version       int64             `json:"version"`
	Deleted       bool              `json:"deleted"`
	Revision      *ArtifactRevision `json:"revision"`
}

type ArtifactPage struct {
	SchemaVersion string     `json:"schema_version"`
	Items         []Artifact `json:"items"`
	HasMore       bool       `json:"has_more"`
	NextCursor    string     `json:"next_cursor"`
	Truncated     bool       `json:"truncated"`
}

type ArtifactUpload struct {
	SchemaVersion string             `json:"schema_version"`
	ID            string             `json:"id"`
	WorkspaceID   string             `json:"workspace_id"`
	OperationID   string             `json:"operation_id"`
	ExpectedSize  int64              `json:"expected_size"`
	Status        string             `json:"status"`
	Offset        int64              `json:"offset"`
	ExpiresAt     time.Time          `json:"expires_at"`
	Receipt       *ArtifactReference `json:"receipt"`
}

type ArtifactReference struct {
	ArtifactID string `json:"artifact_id"`
	RevisionID string `json:"revision_id"`
}

type BeginArtifactUploadRequest struct {
	SchemaVersion    string  `json:"schema_version,omitempty"`
	OperationID      string  `json:"operation_id"`
	Path             string  `json:"path"`
	SizeBytes        int64   `json:"size_bytes"`
	SHA256           string  `json:"sha256"`
	ContentType      string  `json:"content_type"`
	ArtifactID       *string `json:"artifact_id,omitempty"`
	ExpectedRevision *string `json:"expected_revision,omitempty"`
}

type ArtifactSearchHit struct {
	ArtifactID    string         `json:"artifact_id"`
	RevisionID    string         `json:"revision_id"`
	Path          string         `json:"path"`
	Kind          string         `json:"kind"`
	MatchLocation string         `json:"match_location"`
	Snippet       string         `json:"snippet"`
	Coverage      string         `json:"coverage"`
	Source        ArtifactSource `json:"source"`
}

type ArtifactSearchPage struct {
	SchemaVersion  string              `json:"schema_version"`
	Query          string              `json:"query"`
	Mode           string              `json:"mode"`
	CatalogVersion int64               `json:"catalog_version"`
	Items          []ArtifactSearchHit `json:"items"`
	HasMore        bool                `json:"has_more"`
	NextCursor     string              `json:"next_cursor"`
	Truncated      bool                `json:"truncated"`
}

type ArtifactSourceLocator struct {
	BlockID           *string   `json:"block_id,omitempty"`
	PageIndex         *int      `json:"page_index,omitempty"`
	PageNumber        *int      `json:"page_number,omitempty"`
	LineStart         *int      `json:"line_start,omitempty"`
	LineEnd           *int      `json:"line_end,omitempty"`
	CharStart         *int      `json:"char_start,omitempty"`
	CharEnd           *int      `json:"char_end,omitempty"`
	BBox              []float64 `json:"bbox,omitempty"`
	ByteStart         *int64    `json:"byte_start,omitempty"`
	ByteEnd           *int64    `json:"byte_end,omitempty"`
	CharSpace         string    `json:"char_space,omitempty"`
	SourceEncoding    *string   `json:"source_encoding,omitempty"`
	TextNormalization string    `json:"text_normalization,omitempty"`
	ImageBBox         []float64 `json:"image_bbox,omitempty"`
	PageLabel         *string   `json:"page_label,omitempty"`
}

type ArtifactSource struct {
	ArtifactID          string                 `json:"artifact_id"`
	RevisionID          string                 `json:"revision_id"`
	SourceSHA256        string                 `json:"source_sha256"`
	RepresentationSetID *string                `json:"representation_set_id,omitempty"`
	DocumentIndexID     *string                `json:"document_index_id,omitempty"`
	NodeID              *string                `json:"node_id,omitempty"`
	Locator             *ArtifactSourceLocator `json:"locator,omitempty"`
	ExcerptSHA256       *string                `json:"excerpt_sha256,omitempty"`
}

type ArtifactSourceReadRequest struct {
	Source   ArtifactSource `json:"source"`
	Offset   int64          `json:"offset,omitempty"`
	MaxChars int            `json:"max_chars,omitempty"`
}

type ArtifactSourceRead struct {
	SchemaVersion string         `json:"schema_version"`
	Source        ArtifactSource `json:"source"`
	Text          string         `json:"text"`
	Offset        int64          `json:"offset"`
	NextOffset    *int64         `json:"next_offset"`
	Truncated     bool           `json:"truncated"`
	Coverage      string         `json:"coverage"`
	PageLabel     *string        `json:"page_label"`
}

type ArtifactProcessingRequest struct {
	SchemaVersion   string  `json:"schema_version,omitempty"`
	OperationID     string  `json:"operation_id"`
	RevisionID      string  `json:"revision_id"`
	ProfileID       *string `json:"profile_id,omitempty"`
	ProfileRevision *int64  `json:"profile_revision,omitempty"`
}

type ArtifactProcessingResult struct {
	Mode                string   `json:"mode"`
	ProcessingPerformed bool     `json:"processing_performed"`
	SourceSHA256        string   `json:"source_sha256"`
	Coverage            *string  `json:"coverage"`
	RepresentationSetID *string  `json:"representation_set_id"`
	DocumentIndexID     *string  `json:"document_index_id"`
	BlockCount          int64    `json:"block_count"`
	PageCount           int64    `json:"page_count"`
	Diagnostics         []string `json:"diagnostics"`
}

type ArtifactProcessingJob struct {
	SchemaVersion     string                    `json:"schema_version"`
	ID                string                    `json:"id"`
	WorkspaceID       string                    `json:"workspace_id"`
	OperationID       string                    `json:"operation_id"`
	Source            ArtifactReference         `json:"source"`
	ProfileID         *string                   `json:"profile_id"`
	ProfileRevision   *int64                    `json:"profile_revision"`
	RecipeFingerprint string                    `json:"recipe_fingerprint"`
	Status            string                    `json:"status"`
	Attempt           int                       `json:"attempt"`
	CompletedStages   []string                  `json:"completed_stages"`
	Result            *ArtifactProcessingResult `json:"result"`
	ErrorCode         *string                   `json:"error_code"`
	Retryable         bool                      `json:"retryable"`
}

type ArtifactIndex struct {
	SchemaVersion         string    `json:"schema_version"`
	ID                    string    `json:"id"`
	WorkspaceID           string    `json:"workspace_id"`
	ArtifactID            string    `json:"artifact_id"`
	RevisionID            string    `json:"revision_id"`
	RepresentationSetID   string    `json:"representation_set_id"`
	SourceSHA256          string    `json:"source_sha256"`
	RecipeFingerprint     string    `json:"recipe_fingerprint"`
	ProcessingFingerprint string    `json:"processing_fingerprint"`
	Engine                string    `json:"engine"`
	EngineVersion         string    `json:"engine_version"`
	Status                string    `json:"status"`
	TreeKind              string    `json:"tree_kind"`
	Coverage              string    `json:"coverage"`
	RootNodeID            string    `json:"root_node_id"`
	NodeCount             int64     `json:"node_count"`
	SourceBlockCount      int64     `json:"source_block_count"`
	MaxDepth              int       `json:"max_depth"`
	ManifestSHA256        string    `json:"manifest_sha256"`
	CreatedAt             time.Time `json:"created_at"`
	ReadOnly              bool      `json:"read_only"`
}

type ArtifactDocumentNode struct {
	SchemaVersion       string          `json:"schema_version"`
	ID                  string          `json:"id"`
	DocumentIndexID     string          `json:"document_index_id"`
	RepresentationSetID string          `json:"representation_set_id"`
	ParentID            *string         `json:"parent_id"`
	Title               string          `json:"title"`
	Kind                string          `json:"kind"`
	Ordinal             int64           `json:"ordinal"`
	Depth               int             `json:"depth"`
	ChildrenCount       int64           `json:"children_count"`
	SourceRanges        [][]int64       `json:"source_ranges"`
	Source              *ArtifactSource `json:"source"`
	HasOwnText          bool            `json:"has_own_text"`
	Inferred            bool            `json:"inferred"`
	ExtractionMethod    *string         `json:"extraction_method"`
}

type ArtifactDocumentNodePage struct {
	SchemaVersion string                 `json:"schema_version"`
	Items         []ArtifactDocumentNode `json:"items"`
	HasMore       bool                   `json:"has_more"`
	NextCursor    string                 `json:"next_cursor"`
	Truncated     bool                   `json:"truncated"`
}

type ArtifactProcessingProfile struct {
	SchemaVersion string              `json:"schema_version"`
	ID            string              `json:"id"`
	Revision      int64               `json:"revision"`
	ProjectID     string              `json:"project_id"`
	Environment   ArtifactEnvironment `json:"environment"`
	Fingerprint   string              `json:"fingerprint"`
	Ready         bool                `json:"ready"`
	Diagnostics   []string            `json:"diagnostics"`
	Recipe        map[string]any      `json:"recipe"`
}

type ArtifactProcessingProfilePage struct {
	SchemaVersion string                      `json:"schema_version"`
	Items         []ArtifactProcessingProfile `json:"items"`
	HasMore       bool                        `json:"has_more"`
	NextCursor    string                      `json:"next_cursor"`
	Truncated     bool                        `json:"truncated"`
}

type ArtifactProcessingSelection struct {
	SchemaVersion string                     `json:"schema_version"`
	Profile       *ArtifactProcessingProfile `json:"profile"`
	Recipe        map[string]any             `json:"recipe"`
	Ready         bool                       `json:"ready"`
	Diagnostics   []string                   `json:"diagnostics"`
	Fingerprint   string                     `json:"fingerprint"`
	Mode          string                     `json:"mode"`
}

type CreateArtifactProcessingProfileRequest struct {
	SchemaVersion string         `json:"schema_version,omitempty"`
	ID            string         `json:"id"`
	Revision      int64          `json:"revision"`
	Recipe        map[string]any `json:"recipe"`
}

type ArtifactProcessingProfileBinding struct {
	ExpectedVersion int64   `json:"expected_version"`
	ProfileID       *string `json:"profile_id,omitempty"`
	ProfileRevision *int64  `json:"profile_revision,omitempty"`
}

type ArtifactDownload struct {
	Body         io.ReadCloser
	StatusCode   int
	ContentType  string
	ContentRange string
	ETag         string
	SHA256       string
}

func (a *ArtifactsClient) scopedPath(path string, extra url.Values) string {
	query := url.Values{}
	query.Set("project_id", a.projectID)
	query.Set("environment", string(a.environment))
	for key, values := range extra {
		for _, value := range values {
			query.Add(key, value)
		}
	}
	return path + "?" + query.Encode()
}

func (a *ArtifactsClient) request(ctx context.Context, method, path string, query url.Values, body any, idempotencyKey string, out any) error {
	var reader io.Reader
	if body != nil {
		encoded, err := json.Marshal(body)
		if err != nil {
			return &ProtocolError{Message: "could not encode Artifact request", Cause: err}
		}
		reader = bytes.NewReader(encoded)
	}
	req, err := http.NewRequestWithContext(ctx, method, a.client.endpoint(a.scopedPath(path, query)), reader)
	if err != nil {
		return &ProtocolError{Message: "could not build Artifact request", Cause: err}
	}
	authHeaders(req, a.runtimeKey, "application/json")
	if method != http.MethodGet && method != http.MethodHead {
		// A key may make a request replayable to net/http. Mutations with a lost
		// response are reconciled by operation ID, never transparently repeated.
		if req.Body == nil {
			req.Body = io.NopCloser(strings.NewReader(""))
			req.ContentLength = 0
		}
		req.GetBody = nil
	}
	if idempotencyKey != "" {
		req.Header.Set("Idempotency-Key", idempotencyKey)
	}
	resp, err := a.do(req)
	if err != nil {
		return &ConnectionError{Message: "Woobe Artifacts request failed; if this was a mutation its outcome may be uncertain", Cause: err}
	}
	defer resp.Body.Close()
	if err := raiseForStatus(resp); err != nil {
		return err
	}
	if out == nil {
		return nil
	}
	if err := json.NewDecoder(resp.Body).Decode(out); err != nil {
		return &ProtocolError{Message: "Woobe Artifacts response contains invalid JSON", Cause: err}
	}
	return nil
}

// do preserves the configured transport, timeout, jar, and tracing hooks while
// refusing redirects. Artifact credentials and mutation bodies never follow a
// provider-controlled redirect.
func (a *ArtifactsClient) do(req *http.Request) (*http.Response, error) {
	client := *a.client.httpClient
	client.CheckRedirect = func(_ *http.Request, _ []*http.Request) error {
		return http.ErrUseLastResponse
	}
	return client.Do(req)
}

func (a *ArtifactsClient) Capabilities(ctx context.Context) (*ArtifactCapabilities, error) {
	var out ArtifactCapabilities
	if err := a.request(ctx, http.MethodGet, "/v1/artifact-capabilities", nil, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) CreateProcessingProfile(ctx context.Context, in CreateArtifactProcessingProfileRequest) (*ArtifactProcessingProfile, error) {
	if err := requiredArtifactID("profileID", in.ID); err != nil {
		return nil, err
	}
	if in.Revision < 1 {
		return nil, &ProtocolError{Message: "processing profile revision must be positive"}
	}
	if in.SchemaVersion == "" {
		in.SchemaVersion = "1"
	}
	var out ArtifactProcessingProfile
	if err := a.request(ctx, http.MethodPost, "/v1/artifact-processing-profiles", nil, in, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) ListProcessingProfiles(ctx context.Context, limit int, cursor string) (*ArtifactProcessingProfilePage, error) {
	query := url.Values{}
	if limit > 0 {
		query.Set("limit", strconv.Itoa(limit))
	}
	if cursor != "" {
		query.Set("cursor", cursor)
	}
	var out ArtifactProcessingProfilePage
	if err := a.request(ctx, http.MethodGet, "/v1/artifact-processing-profiles", query, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) GetProcessingProfile(ctx context.Context, profileID string, revision int64) (*ArtifactProcessingProfile, error) {
	if err := requiredArtifactID("profileID", profileID); err != nil {
		return nil, err
	}
	if revision < 1 {
		return nil, &ProtocolError{Message: "processing profile revision must be positive"}
	}
	path := "/v1/artifact-processing-profiles/" + url.PathEscape(profileID) + "/revisions/" + strconv.FormatInt(revision, 10)
	var out ArtifactProcessingProfile
	if err := a.request(ctx, http.MethodGet, path, nil, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) BindProcessingProfile(ctx context.Context, workspaceID string, in ArtifactProcessingProfileBinding) (*ArtifactWorkspace, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if in.ExpectedVersion < 1 {
		return nil, &ProtocolError{Message: "expected workspace version must be positive"}
	}
	if (in.ProfileID == nil) != (in.ProfileRevision == nil) {
		return nil, &ProtocolError{Message: "profile ID and revision must be set together"}
	}
	path := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/processing-profile"
	var out ArtifactWorkspace
	if err := a.request(ctx, http.MethodPut, path, nil, in, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) SelectProcessingProfile(ctx context.Context, workspaceID, profileID string, revision int64) (*ArtifactProcessingSelection, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	query := url.Values{}
	if profileID != "" {
		if err := requiredArtifactID("profileID", profileID); err != nil {
			return nil, err
		}
		if revision < 1 {
			return nil, &ProtocolError{Message: "processing profile revision must be positive"}
		}
		query.Set("profile_id", profileID)
		query.Set("profile_revision", strconv.FormatInt(revision, 10))
	} else if revision != 0 {
		return nil, &ProtocolError{Message: "profile revision requires a profile ID"}
	}
	path := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/processing-profile"
	var out ArtifactProcessingSelection
	if err := a.request(ctx, http.MethodGet, path, query, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) CreateWorkspace(ctx context.Context, in CreateArtifactWorkspaceRequest) (*ArtifactWorkspace, error) {
	if in.Environment != "" && in.Environment != a.environment {
		return nil, &ProtocolError{Message: "workspace environment must match the Artifacts client scope"}
	}
	in.Environment = a.environment
	if in.SchemaVersion == "" {
		in.SchemaVersion = "1"
	}
	var out ArtifactWorkspace
	if err := a.request(ctx, http.MethodPost, "/v1/artifact-workspaces", nil, in, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) ListWorkspaces(ctx context.Context, limit int, cursor, externalNamespace string) (*ArtifactWorkspacePage, error) {
	query := url.Values{}
	if limit > 0 {
		query.Set("limit", strconv.Itoa(limit))
	}
	if cursor != "" {
		query.Set("cursor", cursor)
	}
	if externalNamespace != "" {
		query.Set("external_namespace", externalNamespace)
	}
	var out ArtifactWorkspacePage
	if err := a.request(ctx, http.MethodGet, "/v1/artifact-workspaces", query, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) ResolveWorkspace(ctx context.Context, namespace, externalKey string) (*ArtifactWorkspace, error) {
	query := url.Values{"external_namespace": {namespace}, "external_key": {externalKey}}
	var out ArtifactWorkspace
	if err := a.request(ctx, http.MethodGet, "/v1/artifact-workspaces/resolve", query, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) GetWorkspace(ctx context.Context, workspaceID string) (*ArtifactWorkspace, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	var out ArtifactWorkspace
	if err := a.request(ctx, http.MethodGet, "/v1/artifact-workspaces/"+url.PathEscape(workspaceID), nil, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) UpdateWorkspace(ctx context.Context, workspaceID string, in UpdateArtifactWorkspaceRequest) (*ArtifactWorkspace, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if in.ExpectedVersion < 1 {
		return nil, &ProtocolError{Message: "expected workspace version must be positive"}
	}
	var out ArtifactWorkspace
	if err := a.request(ctx, http.MethodPatch, "/v1/artifact-workspaces/"+url.PathEscape(workspaceID), nil, in, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) ListArtifacts(ctx context.Context, workspaceID, directory string, limit int, cursor string) (*ArtifactPage, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	query := url.Values{"directory": {directory}}
	if limit > 0 {
		query.Set("limit", strconv.Itoa(limit))
	}
	if cursor != "" {
		query.Set("cursor", cursor)
	}
	var out ArtifactPage
	path := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/artifacts"
	if err := a.request(ctx, http.MethodGet, path, query, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) GetArtifact(ctx context.Context, workspaceID, artifactID string) (*Artifact, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("artifactID", artifactID); err != nil {
		return nil, err
	}
	var out Artifact
	path := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/artifacts/" + url.PathEscape(artifactID)
	if err := a.request(ctx, http.MethodGet, path, nil, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) GetRevision(ctx context.Context, workspaceID, artifactID, revisionID string) (*ArtifactRevision, error) {
	for name, value := range map[string]string{"workspaceID": workspaceID, "artifactID": artifactID, "revisionID": revisionID} {
		if err := requiredArtifactID(name, value); err != nil {
			return nil, err
		}
	}
	query := url.Values{"artifact_workspace_id": {workspaceID}}
	path := "/v1/artifacts/" + url.PathEscape(artifactID) + "/revisions/" + url.PathEscape(revisionID)
	var out ArtifactRevision
	if err := a.request(ctx, http.MethodGet, path, query, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) CreateText(ctx context.Context, workspaceID, operationID, path, text string) (*ArtifactUpload, error) {
	if err := validateArtifactMutation(workspaceID, operationID); err != nil {
		return nil, err
	}
	body := map[string]any{"schema_version": "1", "operation_id": operationID, "kind": "text", "path": path, "text": text}
	var out ArtifactUpload
	endpoint := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/artifacts"
	if err := a.request(ctx, http.MethodPost, endpoint, nil, body, operationID, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) UpdateText(ctx context.Context, workspaceID, artifactID, operationID, revisionID, path, text string) (*ArtifactUpload, error) {
	if err := validateArtifactMutation(workspaceID, operationID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("artifactID", artifactID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("revisionID", revisionID); err != nil {
		return nil, err
	}
	body := map[string]any{"operation_id": operationID, "expected_revision": revisionID, "path": path, "text": text}
	var out ArtifactUpload
	endpoint := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/artifacts/" + url.PathEscape(artifactID) + "/content"
	if err := a.request(ctx, http.MethodPut, endpoint, nil, body, operationID, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) MakeDirectory(ctx context.Context, workspaceID, operationID, path string) (*Artifact, error) {
	if err := validateArtifactMutation(workspaceID, operationID); err != nil {
		return nil, err
	}
	body := map[string]any{"schema_version": "1", "operation_id": operationID, "kind": "directory", "path": path}
	var out Artifact
	endpoint := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/artifacts"
	if err := a.request(ctx, http.MethodPost, endpoint, nil, body, operationID, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) MoveArtifact(ctx context.Context, workspaceID, artifactID, operationID, path string, expectedVersion int64) (*Artifact, error) {
	if err := validateArtifactMutation(workspaceID, operationID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("artifactID", artifactID); err != nil {
		return nil, err
	}
	if expectedVersion < 1 {
		return nil, &ProtocolError{Message: "expected artifact version must be positive"}
	}
	body := map[string]any{"operation_id": operationID, "expected_version": expectedVersion, "path": path}
	var out Artifact
	endpoint := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/artifacts/" + url.PathEscape(artifactID)
	if err := a.request(ctx, http.MethodPatch, endpoint, nil, body, operationID, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) DeleteArtifact(ctx context.Context, workspaceID, artifactID, operationID string, expectedVersion int64) (*Artifact, error) {
	if err := validateArtifactMutation(workspaceID, operationID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("artifactID", artifactID); err != nil {
		return nil, err
	}
	if expectedVersion < 1 {
		return nil, &ProtocolError{Message: "expected artifact version must be positive"}
	}
	query := url.Values{"expected_version": {strconv.FormatInt(expectedVersion, 10)}}
	var out Artifact
	endpoint := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/artifacts/" + url.PathEscape(artifactID)
	if err := a.request(ctx, http.MethodDelete, endpoint, query, nil, operationID, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) BeginUpload(ctx context.Context, workspaceID string, in BeginArtifactUploadRequest) (*ArtifactUpload, error) {
	if err := validateArtifactMutation(workspaceID, in.OperationID); err != nil {
		return nil, err
	}
	if in.SizeBytes < 0 || len(in.SHA256) != 64 || strings.ToLower(in.SHA256) != in.SHA256 {
		return nil, &ProtocolError{Message: "upload requires a nonnegative size and lowercase SHA-256"}
	}
	if _, err := hex.DecodeString(in.SHA256); err != nil {
		return nil, &ProtocolError{Message: "upload requires a lowercase hexadecimal SHA-256 digest", Cause: err}
	}
	if in.SchemaVersion == "" {
		in.SchemaVersion = "1"
	}
	var out ArtifactUpload
	endpoint := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/uploads"
	if err := a.request(ctx, http.MethodPost, endpoint, nil, in, in.OperationID, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) UploadStatus(ctx context.Context, workspaceID, uploadID string) (*ArtifactUpload, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("uploadID", uploadID); err != nil {
		return nil, err
	}
	var out ArtifactUpload
	endpoint := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/uploads/" + url.PathEscape(uploadID)
	if err := a.request(ctx, http.MethodGet, endpoint, nil, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) UploadPart(ctx context.Context, workspaceID, uploadID string, offset int64, part io.Reader, size int64) (*ArtifactUpload, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("uploadID", uploadID); err != nil {
		return nil, err
	}
	if offset < 0 || size < 0 || part == nil {
		return nil, &ProtocolError{Message: "upload part requires a reader and nonnegative offset and size"}
	}
	return a.uploadPart(ctx, workspaceID, uploadID, offset, part, size)
}

func (a *ArtifactsClient) uploadPart(ctx context.Context, workspaceID, uploadID string, offset int64, part io.Reader, size int64) (*ArtifactUpload, error) {
	query := url.Values{"offset": {strconv.FormatInt(offset, 10)}}
	path := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/uploads/" + url.PathEscape(uploadID) + "/parts"
	req, err := http.NewRequestWithContext(ctx, http.MethodPut, a.client.endpoint(a.scopedPath(path, query)), io.LimitReader(part, size))
	if err != nil {
		return nil, &ProtocolError{Message: "could not build Artifact upload-part request", Cause: err}
	}
	authHeaders(req, a.runtimeKey, "application/json")
	req.Header.Set("Content-Type", "application/octet-stream")
	req.ContentLength = size
	resp, err := a.do(req)
	if err != nil {
		return nil, &ConnectionError{Message: "Woobe Artifact upload-part outcome may be uncertain", Cause: err}
	}
	defer resp.Body.Close()
	if err := raiseForStatus(resp); err != nil {
		return nil, err
	}
	var out ArtifactUpload
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return nil, &ProtocolError{Message: "Woobe upload-part response contains invalid JSON", Cause: err}
	}
	return &out, nil
}

func (a *ArtifactsClient) FinalizeUpload(ctx context.Context, workspaceID, uploadID string) (*ArtifactUpload, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("uploadID", uploadID); err != nil {
		return nil, err
	}
	var out ArtifactUpload
	path := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/uploads/" + url.PathEscape(uploadID) + "/finalize"
	if err := a.request(ctx, http.MethodPost, path, nil, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) AbortUpload(ctx context.Context, workspaceID, uploadID string) (*ArtifactUpload, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("uploadID", uploadID); err != nil {
		return nil, err
	}
	var out ArtifactUpload
	path := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/uploads/" + url.PathEscape(uploadID)
	if err := a.request(ctx, http.MethodDelete, path, nil, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

// Upload streams one file using bounded offset parts. The caller supplies the
// expected size and hash so a checksum can be declared before any bytes are
// sent. Lost acknowledgements are returned to the caller for explicit status
// reconciliation; the SDK never resubmits a part or finalization.
func (a *ArtifactsClient) Upload(ctx context.Context, workspaceID string, in BeginArtifactUploadRequest, source io.Reader) (*ArtifactUpload, error) {
	if source == nil {
		return nil, &ProtocolError{Message: "upload source must not be nil"}
	}
	capabilities, err := a.Capabilities(ctx)
	if err != nil {
		return nil, err
	}
	partLimit := capabilities.MaxUploadPartBytes
	if partLimit <= 0 || partLimit > 8*1024*1024 {
		return nil, &ProtocolError{Message: "server advertised an invalid Artifact upload-part limit"}
	}
	if in.SizeBytes > capabilities.MaxUploadBytes {
		return nil, &ProtocolError{Message: "upload exceeds the server's advertised Artifact size limit"}
	}
	parts := int64(0)
	if in.SizeBytes > 0 {
		parts = (in.SizeBytes + partLimit - 1) / partLimit
	}
	if capabilities.MaxUploadParts <= 0 || parts > int64(capabilities.MaxUploadParts) {
		return nil, &ProtocolError{Message: "upload exceeds the server's advertised Artifact part limit"}
	}
	upload, err := a.BeginUpload(ctx, workspaceID, in)
	if err != nil {
		return nil, err
	}
	buffer := make([]byte, partLimit)
	hasher := sha256.New()
	var offset int64
	for offset < in.SizeBytes {
		want := int64(len(buffer))
		if remaining := in.SizeBytes - offset; remaining < want {
			want = remaining
		}
		if _, err := io.ReadFull(source, buffer[:int(want)]); err != nil {
			_, abortErr := a.AbortUpload(ctx, workspaceID, upload.ID)
			return upload, fmt.Errorf("artifact upload source ended before declared size: %w (abort: %v)", err, abortErr)
		}
		part := buffer[:want]
		_, _ = hasher.Write(part)
		if latest, err := a.uploadPart(ctx, workspaceID, upload.ID, offset, bytes.NewReader(part), want); err != nil {
			return upload, err
		} else {
			upload = latest
		}
		offset += want
	}
	if got := hex.EncodeToString(hasher.Sum(nil)); got != in.SHA256 {
		_, abortErr := a.AbortUpload(ctx, workspaceID, upload.ID)
		return upload, fmt.Errorf("artifact upload SHA-256 mismatch (abort: %v)", abortErr)
	}
	completed, err := a.FinalizeUpload(ctx, workspaceID, upload.ID)
	if err != nil {
		return upload, err
	}
	return completed, nil
}

// Download returns a streaming response body for an exact immutable revision.
// The caller owns and must close the body.
func (a *ArtifactsClient) Download(ctx context.Context, workspaceID, artifactID, revisionID, rangeHeader string) (*ArtifactDownload, error) {
	for name, value := range map[string]string{"workspaceID": workspaceID, "artifactID": artifactID, "revisionID": revisionID} {
		if err := requiredArtifactID(name, value); err != nil {
			return nil, err
		}
	}
	query := url.Values{"artifact_workspace_id": {workspaceID}}
	path := "/v1/artifacts/" + url.PathEscape(artifactID) + "/revisions/" + url.PathEscape(revisionID) + "/content"
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, a.client.endpoint(a.scopedPath(path, query)), nil)
	if err != nil {
		return nil, &ProtocolError{Message: "could not build Artifact download request", Cause: err}
	}
	authHeaders(req, a.runtimeKey, "application/octet-stream")
	if rangeHeader != "" {
		req.Header.Set("Range", rangeHeader)
	}
	resp, err := a.do(req)
	if err != nil {
		return nil, &ConnectionError{Message: "Woobe Artifact download failed", Cause: err}
	}
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		defer resp.Body.Close()
		if err := raiseForStatus(resp); err != nil {
			return nil, err
		}
	}
	return &ArtifactDownload{Body: resp.Body, StatusCode: resp.StatusCode, ContentType: resp.Header.Get("Content-Type"), ContentRange: resp.Header.Get("Content-Range"), ETag: resp.Header.Get("ETag"), SHA256: resp.Header.Get("X-Woobe-Source-Sha256")}, nil
}

func (a *ArtifactsClient) Search(ctx context.Context, workspaceID, query, mode, cursor string, limit int) (*ArtifactSearchPage, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	params := url.Values{"query": {query}}
	if mode != "" {
		params.Set("mode", mode)
	}
	if cursor != "" {
		params.Set("cursor", cursor)
	}
	if limit > 0 {
		params.Set("limit", strconv.Itoa(limit))
	}
	var out ArtifactSearchPage
	path := "/v1/artifact-workspaces/" + url.PathEscape(workspaceID) + "/search"
	if err := a.request(ctx, http.MethodGet, path, params, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) ReadSource(ctx context.Context, workspaceID string, in ArtifactSourceReadRequest) (*ArtifactSourceRead, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if in.Offset < 0 || in.MaxChars < 0 || in.MaxChars > 65536 {
		return nil, &ProtocolError{Message: "invalid source-read bounds"}
	}
	var out ArtifactSourceRead
	query := url.Values{"artifact_workspace_id": {workspaceID}}
	if err := a.request(ctx, http.MethodPost, "/v1/artifact-sources/read", query, in, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) RequestProcessing(ctx context.Context, workspaceID, artifactID string, in ArtifactProcessingRequest) (*ArtifactProcessingJob, error) {
	if err := validateArtifactMutation(workspaceID, in.OperationID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("artifactID", artifactID); err != nil {
		return nil, err
	}
	if in.RevisionID == "" {
		return nil, &ProtocolError{Message: "processing requires an exact revisionID"}
	}
	if in.SchemaVersion == "" {
		in.SchemaVersion = "1"
	}
	query := url.Values{"artifact_workspace_id": {workspaceID}}
	var out ArtifactProcessingJob
	path := "/v1/artifacts/" + url.PathEscape(artifactID) + "/processing"
	if err := a.request(ctx, http.MethodPost, path, query, in, in.OperationID, &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) ProcessingJob(ctx context.Context, workspaceID, artifactID, jobID string) (*ArtifactProcessingJob, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("artifactID", artifactID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("jobID", jobID); err != nil {
		return nil, err
	}
	query := url.Values{"artifact_workspace_id": {workspaceID}}
	var out ArtifactProcessingJob
	path := "/v1/artifacts/" + url.PathEscape(artifactID) + "/processing/" + url.PathEscape(jobID)
	if err := a.request(ctx, http.MethodGet, path, query, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) CancelProcessing(ctx context.Context, workspaceID, artifactID, jobID string) (*ArtifactProcessingJob, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("artifactID", artifactID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("jobID", jobID); err != nil {
		return nil, err
	}
	query := url.Values{"artifact_workspace_id": {workspaceID}}
	var out ArtifactProcessingJob
	path := "/v1/artifacts/" + url.PathEscape(artifactID) + "/processing/" + url.PathEscape(jobID) + "/cancel"
	if err := a.request(ctx, http.MethodPost, path, query, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) DocumentIndex(ctx context.Context, workspaceID, indexID string) (*ArtifactIndex, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("indexID", indexID); err != nil {
		return nil, err
	}
	query := url.Values{"artifact_workspace_id": {workspaceID}}
	var out ArtifactIndex
	if err := a.request(ctx, http.MethodGet, "/v1/document-indexes/"+url.PathEscape(indexID), query, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) GetDocumentNode(ctx context.Context, workspaceID, indexID, nodeID string) (*ArtifactDocumentNode, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("indexID", indexID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("nodeID", nodeID); err != nil {
		return nil, err
	}
	query := url.Values{"artifact_workspace_id": {workspaceID}}
	path := "/v1/document-indexes/" + url.PathEscape(indexID) + "/nodes/" + url.PathEscape(nodeID)
	var out ArtifactDocumentNode
	if err := a.request(ctx, http.MethodGet, path, query, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) ListDocumentNodes(ctx context.Context, workspaceID, indexID, parentID, cursor string, limit int) (*ArtifactDocumentNodePage, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("indexID", indexID); err != nil {
		return nil, err
	}
	query := url.Values{"artifact_workspace_id": {workspaceID}}
	if parentID != "" {
		query.Set("parent_id", parentID)
	}
	if cursor != "" {
		query.Set("cursor", cursor)
	}
	if limit > 0 {
		query.Set("limit", strconv.Itoa(limit))
	}
	var out ArtifactDocumentNodePage
	path := "/v1/document-indexes/" + url.PathEscape(indexID) + "/nodes"
	if err := a.request(ctx, http.MethodGet, path, query, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func (a *ArtifactsClient) ReadDocumentNode(ctx context.Context, workspaceID, indexID, nodeID string, offset int64, maxChars int) (*ArtifactSourceRead, error) {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("indexID", indexID); err != nil {
		return nil, err
	}
	if err := requiredArtifactID("nodeID", nodeID); err != nil {
		return nil, err
	}
	if offset < 0 || maxChars < 0 || maxChars > 65536 {
		return nil, &ProtocolError{Message: "invalid document-node read bounds"}
	}
	query := url.Values{"artifact_workspace_id": {workspaceID}, "offset": {strconv.FormatInt(offset, 10)}}
	if maxChars > 0 {
		query.Set("max_chars", strconv.Itoa(maxChars))
	}
	var out ArtifactSourceRead
	path := "/v1/document-indexes/" + url.PathEscape(indexID) + "/nodes/" + url.PathEscape(nodeID) + "/content"
	if err := a.request(ctx, http.MethodGet, path, query, nil, "", &out); err != nil {
		return nil, err
	}
	return &out, nil
}

func requiredArtifactID(name, value string) error {
	if !artifactIdentifierPattern.MatchString(value) {
		return &ProtocolError{Message: name + " is not a valid opaque identifier"}
	}
	return nil
}

func validateArtifactMutation(workspaceID, operationID string) error {
	if err := requiredArtifactID("workspaceID", workspaceID); err != nil {
		return err
	}
	if err := requiredArtifactID("operationID", operationID); err != nil {
		return err
	}
	return nil
}
