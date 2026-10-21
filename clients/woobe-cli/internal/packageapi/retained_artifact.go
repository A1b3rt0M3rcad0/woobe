package packageapi

import (
	"context"
	"fmt"
	"net/http"
	"net/url"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
)

type RetainedArtifactReceipt struct {
	PackageSchemaVersion string                        `json:"package_schema_version"`
	SchemaVersion        string                        `json:"schema_version"`
	ProjectID            string                        `json:"project_id"`
	Kind                 string                        `json:"kind"`
	ResourceID           string                        `json:"resource_id"`
	ResourceUID          string                        `json:"resource_uid"`
	RevisionID           string                        `json:"revision_id"`
	RecordDigest         string                        `json:"record_digest"`
	ArtifactDigest       string                        `json:"artifact_digest"`
	DefinitionDigest     string                        `json:"definition_digest"`
	TransportDigest      string                        `json:"transport_digest"`
	SizeBytes            int64                         `json:"size_bytes"`
	Inventory            []packagebundle.InventoryFile `json:"inventory"`
	AuthorStatus         string                        `json:"author_artifact_status"`
	Complete             bool                          `json:"complete"`
}

func (c *Client) HydrateRevision(ctx context.Context, expected RetainedArtifactReceipt) (*packagebundle.Bundle, string, error) {
	if (expected.Kind != "Agent" && expected.Kind != "Network") || !identifier.MatchString(expected.ResourceID) || !identifier.MatchString(expected.RevisionID) || expected.ResourceUID == "" || expected.ProjectID != c.ProjectID {
		return nil, "", output.New(2, "Invalid retained revision destination")
	}
	for _, digest := range []string{expected.RecordDigest, expected.ArtifactDigest, expected.DefinitionDigest} {
		if !strings.HasPrefix(digest, "sha256:") || !digestPattern.MatchString(strings.TrimPrefix(digest, "sha256:")) {
			return nil, "", output.New(2, "Invalid retained revision digest")
		}
	}
	path := fmt.Sprintf("/projects/%s/%ss/%s/asac/revisions/%s/artifact", url.PathEscape(c.ProjectID), strings.ToLower(expected.Kind), url.PathEscape(expected.ResourceID), url.PathEscape(expected.RevisionID))
	var receipt RetainedArtifactReceipt
	if err := c.requestPath(ctx, http.MethodGet, path+"/receipt", nil, &receipt); err != nil {
		return nil, "", err
	}
	if receipt.SchemaVersion != "1.0" || receipt.ProjectID != expected.ProjectID || receipt.Kind != expected.Kind || receipt.ResourceID != expected.ResourceID || receipt.ResourceUID != expected.ResourceUID || receipt.RevisionID != expected.RevisionID || receipt.RecordDigest != expected.RecordDigest || receipt.ArtifactDigest != expected.ArtifactDigest || receipt.DefinitionDigest != expected.DefinitionDigest || !receipt.Complete || !strings.HasPrefix(receipt.ArtifactDigest, "sha256:") || !digestPattern.MatchString(strings.TrimPrefix(receipt.ArtifactDigest, "sha256:")) || !digestPattern.MatchString(receipt.TransportDigest) || receipt.SizeBytes <= 0 || receipt.SizeBytes > packagebundle.MaxArchiveBytes || len(receipt.Inventory) == 0 || len(receipt.Inventory) > 1024 {
		return nil, "", output.New(9, "Retained artifact receipt differs from the selected immutable revision")
	}
	bundle, err := c.downloadArchive(ctx, path, ExportReceipt{PackageSchemaVersion: receipt.PackageSchemaVersion, ProjectID: c.ProjectID, ArtifactDigest: strings.TrimPrefix(receipt.ArtifactDigest, "sha256:"), TransportDigest: receipt.TransportDigest, SizeBytes: receipt.SizeBytes, Inventory: receipt.Inventory}, receipt.RecordDigest)
	return bundle, receipt.AuthorStatus, err
}
