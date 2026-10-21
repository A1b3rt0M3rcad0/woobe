package asac

import (
	"crypto/ed25519"
	"encoding/base64"
	"fmt"
	"net/url"
	"regexp"
	"strings"
	"unicode"
)

type GitPayload struct {
	Format           string `json:"format"`
	Version          string `json:"schema_version"`
	Issuer           string `json:"issuer"`
	Instance         string `json:"instance_id"`
	Project          string `json:"project_id"`
	Resource         string `json:"resource_id"`
	Kind             string `json:"kind"`
	Publication      string `json:"publication_id"`
	Revision         string `json:"revision_id"`
	RecordDigest     string `json:"record_digest"`
	DefinitionDigest string `json:"definition_digest"`
	AuthorDigest     string `json:"author_artifact_digest"`
	Repository       string `json:"repository"`
	Commit           string `json:"commit"`
	Workflow         string `json:"workflow_run"`
	Issued           int64  `json:"issued_at"`
	Expires          int64  `json:"expires_at"`
}
type SignedGit struct {
	Payload   GitPayload `json:"payload"`
	Digest    string     `json:"payload_digest"`
	Signature string     `json:"signature"`
}

func validateGitPayload(payload GitPayload) error {
	validRepository := payload.Repository != "" && len(payload.Repository) <= 512 && strings.IndexFunc(payload.Repository, unicode.IsSpace) == -1
	if strings.Contains(payload.Repository, "://") {
		parsed, err := url.Parse(payload.Repository)
		validRepository = validRepository && err == nil && parsed.Scheme == "https" && parsed.Hostname() != "" && parsed.User == nil && parsed.RawQuery == "" && parsed.Fragment == ""
	} else {
		validRepository = validRepository && strings.Count(payload.Repository, "/") == 1 && !strings.ContainsAny(payload.Repository, ":@")
	}
	if !validRepository || !regexp.MustCompile(`^(?:[a-f0-9]{40}|[a-f0-9]{64})$`).MatchString(payload.Commit) {
		return fmt.Errorf("Use an exact Git commit and public repository identity without credentials")
	}
	uuid := regexp.MustCompile(`^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$`)
	for _, id := range []string{payload.Instance, payload.Project, payload.Resource, payload.Publication} {
		if !uuid.MatchString(id) {
			return fmt.Errorf("Git proof requires canonical destination UUIDs")
		}
	}
	digest := regexp.MustCompile(`^sha256:[a-f0-9]{64}$`)
	for _, value := range []string{payload.RecordDigest, payload.DefinitionDigest, payload.AuthorDigest} {
		if !digest.MatchString(value) {
			return fmt.Errorf("Git proof requires exact sealed digests")
		}
	}
	if payload.Format != "woobe-git-attestation" || payload.Version != "1.0" || (payload.Kind != "Agent" && payload.Kind != "Network") || !strings.HasPrefix(payload.Revision, "rv_") || !uuid.MatchString(strings.TrimPrefix(payload.Revision, "rv_")) || len(payload.Issuer) < 1 || len(payload.Issuer) > 128 || len(payload.Workflow) < 1 || len(payload.Workflow) > 256 || payload.Issued < 1 || payload.Expires <= payload.Issued || payload.Expires-payload.Issued > 3600 {
		return fmt.Errorf("Git proof has an invalid scope or validity period")
	}
	return nil
}

func SignGit(payload GitPayload, seed []byte) (SignedGit, error) {
	if err := validateGitPayload(payload); err != nil {
		return SignedGit{}, err
	}
	if len(seed) != ed25519.SeedSize {
		return SignedGit{}, fmt.Errorf("Git signing seed must be exactly 32 bytes")
	}
	digest, err := Digest("git-attestation", payload)
	if err != nil {
		return SignedGit{}, err
	}
	signature := ed25519.Sign(ed25519.NewKeyFromSeed(seed), []byte(digest))
	return SignedGit{payload, digest, base64.RawURLEncoding.EncodeToString(signature)}, nil
}
