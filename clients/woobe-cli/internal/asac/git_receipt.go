package asac

import (
	"bytes"
	"encoding/json"
	"fmt"
	"time"
)

type GitReceipt struct {
	Version     string `json:"schema_version"`
	ID          string `json:"attestation_id"`
	Publication string `json:"publication_id"`
	Project     string `json:"project_id"`
	Resource    string `json:"resource_id"`
	Kind        string `json:"kind"`
	Git         struct {
		Status     string `json:"status"`
		Repository string `json:"repository"`
		Commit     string `json:"commit"`
		Issuer     string `json:"issuer"`
		Workflow   string `json:"workflow_run"`
	} `json:"git"`
	Attestation       SignedGit `json:"attestation"`
	Verified          string    `json:"verified_at"`
	Scope             string    `json:"verification_scope"`
	Published         bool      `json:"published"`
	ProductionChanged bool      `json:"production_changed"`
	OriginalUnchanged bool      `json:"original_publication_unchanged"`
	Complete          bool      `json:"complete"`
	Digest            string    `json:"receipt_digest"`
	Operation         string    `json:"operation_id"`
	Outcome           string    `json:"write_outcome"`
}

func ValidateGitReceipt(raw []byte, proof SignedGit, operation string) (GitReceipt, error) {
	var receipt GitReceipt
	if err := DecodeSigned(raw, &receipt); err != nil {
		return receipt, err
	}
	p := proof.Payload
	if receipt.Version != "1.0" || receipt.ID != operation || receipt.Operation != operation || receipt.Outcome != "committed" || receipt.Publication != p.Publication || receipt.Project != p.Project || receipt.Resource != p.Resource || receipt.Kind != p.Kind || receipt.Attestation != proof || receipt.Git.Status != "verified" || receipt.Git.Repository != p.Repository || receipt.Git.Commit != p.Commit || receipt.Git.Issuer != p.Issuer || receipt.Git.Workflow != p.Workflow || receipt.Scope != "trusted_pipeline_at_acceptance" || receipt.Published || receipt.ProductionChanged || !receipt.OriginalUnchanged || !receipt.Complete {
		return receipt, fmt.Errorf("Git receipt differs from original operation or sealed proof")
	}
	if _, err := time.Parse(time.RFC3339Nano, receipt.Verified); err != nil {
		return receipt, fmt.Errorf("Git verification timestamp unavailable")
	}
	var payload map[string]any
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	if err := decoder.Decode(&payload); err != nil {
		return receipt, err
	}
	for _, key := range []string{"published", "production_changed", "original_publication_unchanged", "complete"} {
		value, present := payload[key]
		if !present || value == nil {
			return receipt, fmt.Errorf("Git receipt is incomplete")
		}
	}
	for _, key := range []string{"operation_id", "write_outcome", "receipt_digest"} {
		delete(payload, key)
	}
	digest, err := Digest("git-attestation-receipt", payload)
	if err != nil || digest != receipt.Digest {
		return receipt, fmt.Errorf("Git receipt digest differs")
	}
	return receipt, nil
}
