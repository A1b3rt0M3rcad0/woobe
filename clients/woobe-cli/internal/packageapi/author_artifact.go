package packageapi

import (
	"bytes"
	"compress/gzip"
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"net/url"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

const MaxAuthorBytes = 128 << 20

type AuthorReceipt struct {
	PackageSchemaVersion string `json:"package_schema_version"`
	SchemaVersion        string `json:"schema_version"`
	ProjectID            string `json:"project_id"`
	Kind                 string `json:"kind"`
	ResourceID           string `json:"resource_id"`
	ResourceUID          string `json:"resource_uid"`
	RevisionID           string `json:"revision_id"`
	RecordDigest         string `json:"record_digest"`
	AuthorDigest         string `json:"author_digest"`
	TransportDigest      string `json:"transport_digest"`
	UploadID             string `json:"author_upload_id"`
	SizeBytes            int64  `json:"size_bytes"`
	Verification         string `json:"verification"`
	Complete             bool   `json:"complete"`
}

func (c *Client) UploadAuthor(ctx context.Context, raw []byte, digest, uid string) (string, error) {
	if len(raw) == 0 || len(raw) > MaxAuthorBytes {
		return "", output.New(2, "Author source exceeds its bounded limit")
	}
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	part, err := form.CreateFormFile("file", "author.json.gz")
	if err != nil {
		return "", err
	}
	compressed := gzip.NewWriter(part)
	if _, err = compressed.Write(raw); err != nil {
		return "", err
	}
	if err = compressed.Close(); err != nil {
		return "", err
	}
	if err = form.Close(); err != nil {
		return "", err
	}
	value, _, err := c.Control.RequestReader(ctx, http.MethodPost, c.path("/author-uploads"), nil, &body, form.FormDataContentType())
	if err != nil {
		return "", err
	}
	envelope, ok := value.(map[string]any)
	if !ok || envelope["success"] != true {
		return "", output.New(9, "Invalid author custody envelope")
	}
	encoded, _ := json.Marshal(envelope["data"])
	var receipt AuthorReceipt
	if json.Unmarshal(encoded, &receipt) != nil || receipt.PackageSchemaVersion != "1.0" || receipt.ProjectID != c.ProjectID || receipt.ResourceUID != uid || receipt.AuthorDigest != digest || !uuidIdentifier.MatchString(receipt.UploadID) || receipt.Verification != "canonical_source_custody" || !receipt.Complete {
		return "", output.New(9, "Author custody receipt differs from uploaded source")
	}
	return receipt.UploadID, nil
}

func (c *Client) HydrateAuthor(ctx context.Context, expected AuthorReceipt) ([]byte, error) {
	if (expected.Kind != "Agent" && expected.Kind != "Network") || !uuidIdentifier.MatchString(expected.ResourceID) || !identifier.MatchString(expected.RevisionID) || expected.ProjectID != c.ProjectID || !digestPattern.MatchString(strings.TrimPrefix(expected.AuthorDigest, "sha256:")) {
		return nil, output.New(2, "Invalid author hydration identity")
	}
	path := fmt.Sprintf("/projects/%s/%ss/%s/asac/revisions/%s/author", url.PathEscape(c.ProjectID), strings.ToLower(expected.Kind), url.PathEscape(expected.ResourceID), url.PathEscape(expected.RevisionID))
	var receipt AuthorReceipt
	if err := c.requestPath(ctx, http.MethodGet, path+"/receipt", nil, &receipt); err != nil {
		return nil, err
	}
	if receipt.SchemaVersion != "1.0" || receipt.ProjectID != expected.ProjectID || receipt.Kind != expected.Kind || receipt.ResourceID != expected.ResourceID || receipt.ResourceUID != expected.ResourceUID || receipt.RevisionID != expected.RevisionID || receipt.RecordDigest != expected.RecordDigest || receipt.AuthorDigest != expected.AuthorDigest || receipt.Verification != "canonical_source_custody" || !receipt.Complete || !digestPattern.MatchString(receipt.TransportDigest) || receipt.SizeBytes <= 0 || receipt.SizeBytes > MaxAuthorBytes {
		return nil, output.New(9, "Author receipt differs from selected revision")
	}
	request, err := http.NewRequestWithContext(ctx, http.MethodGet, c.Control.Base+path, nil)
	if err != nil {
		return nil, err
	}
	request.Header = c.Control.Headers.Clone()
	request.Header.Del("If-Match")
	request.Header.Del("Idempotency-Key")
	request.Header.Set("Accept", "application/gzip")
	if c.Control.Token != "" {
		request.Header.Set("Authorization", "Bearer "+c.Control.Token)
	}
	response, err := c.Control.HTTP.Do(request)
	if err != nil {
		return nil, output.New(7, "Author source download failed")
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return nil, output.New(7, "Server rejected author source download")
	}
	if c.Control.ResponseHook != nil {
		if err = c.Control.ResponseHook(response); err != nil {
			return nil, output.New(10, "Author response session could not be persisted")
		}
	}
	if response.Header.Get("Content-Length") != fmt.Sprint(receipt.SizeBytes) || response.Header.Get("X-Woobe-Record-Digest") != receipt.RecordDigest || response.Header.Get("X-Woobe-Author-Digest") != receipt.AuthorDigest || response.Header.Get("X-Woobe-Transport-Sha256") != receipt.TransportDigest {
		return nil, output.New(9, "Author download headers differ from receipt")
	}
	content, err := io.ReadAll(io.LimitReader(response.Body, receipt.SizeBytes+1))
	actual := sha256.Sum256(content)
	if err != nil || int64(len(content)) != receipt.SizeBytes || hex.EncodeToString(actual[:]) != receipt.TransportDigest {
		return nil, output.New(9, "Author transport integrity mismatch")
	}
	stream, err := gzip.NewReader(bytes.NewReader(content))
	if err != nil {
		return nil, output.New(9, "Invalid author compression")
	}
	defer stream.Close()
	raw, err := io.ReadAll(io.LimitReader(stream, MaxAuthorBytes+1))
	if err != nil || len(raw) > MaxAuthorBytes {
		return nil, output.New(9, "Author source exceeds bounded limit")
	}
	return raw, nil
}
