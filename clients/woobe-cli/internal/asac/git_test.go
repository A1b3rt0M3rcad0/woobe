package asac

import (
	"crypto/ed25519"
	"encoding/base64"
	"encoding/json"
	"os"
	"testing"
)

func gitGolden(t *testing.T) SignedGit {
	t.Helper()
	raw, err := os.ReadFile("../../testdata/asac/git-attestation.json")
	if err != nil {
		t.Fatal(err)
	}
	var proof SignedGit
	if err = DecodeSigned(raw, &proof); err != nil {
		t.Fatal(err)
	}
	return proof
}
func TestGitSignatureMatchesPythonGolden(t *testing.T) {
	golden := gitGolden(t)
	seed := make([]byte, 32)
	for i := range seed {
		seed[i] = byte(i)
	}
	proof, err := SignGit(golden.Payload, seed)
	if err != nil || proof != golden {
		t.Fatal("Go/Python Git proof differs", err)
	}
	signature, _ := base64.RawURLEncoding.DecodeString(proof.Signature)
	if !ed25519.Verify(ed25519.NewKeyFromSeed(seed).Public().(ed25519.PublicKey), []byte(proof.Digest), signature) {
		t.Fatal("signature invalid")
	}
	changed := proof.Payload
	changed.Commit = "e" + changed.Commit[1:]
	digest, _ := Digest("git-attestation", changed)
	if ed25519.Verify(ed25519.NewKeyFromSeed(seed).Public().(ed25519.PublicKey), []byte(digest), signature) {
		t.Fatal("tampered commit accepted")
	}
}
func TestGitProofRejectsUnsafeRepositoryMovingCommitAndUnboundedValidity(t *testing.T) {
	golden := gitGolden(t)
	for _, mutate := range []func(*GitPayload){
		func(p *GitPayload) { p.Repository = "https://secret@github.com/owner/repo" },
		func(p *GitPayload) { p.Repository = "https://github.com/owner/repo?token=secret" },
		func(p *GitPayload) { p.Commit = "HEAD" },
		func(p *GitPayload) { p.Expires = p.Issued + 3601 },
		func(p *GitPayload) { p.Resource = "not-a-uuid" },
	} {
		payload := golden.Payload
		mutate(&payload)
		if _, err := SignGit(payload, make([]byte, 32)); err == nil {
			raw, _ := json.Marshal(payload)
			t.Fatalf("invalid proof accepted: %s", raw)
		}
	}
	if _, err := SignGit(golden.Payload, []byte("too-short")); err == nil {
		t.Fatal("invalid key accepted")
	}
}

func TestGitReceiptChecksOriginalIdentityProofAndDigest(t *testing.T) {
	proof := gitGolden(t)
	payload := map[string]any{
		"schema_version": "1.0", "attestation_id": proof.Payload.Publication, "publication_id": proof.Payload.Publication,
		"project_id": proof.Payload.Project, "resource_id": proof.Payload.Resource, "kind": proof.Payload.Kind,
		"git":         map[string]any{"status": "verified", "repository": proof.Payload.Repository, "commit": proof.Payload.Commit, "issuer": proof.Payload.Issuer, "workflow_run": proof.Payload.Workflow},
		"attestation": proof, "verified_at": "2026-10-09T06:00:00+00:00", "verification_scope": "trusted_pipeline_at_acceptance",
		"published": false, "production_changed": false, "original_publication_unchanged": true, "complete": true,
	}
	digest, err := Digest("git-attestation-receipt", payload)
	if err != nil {
		t.Fatal(err)
	}
	payload["receipt_digest"] = digest
	payload["operation_id"] = proof.Payload.Publication
	payload["write_outcome"] = "committed"
	raw, _ := json.Marshal(payload)
	if _, err = ValidateGitReceipt(raw, proof, proof.Payload.Publication); err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{"operation_id", "publication_id", "receipt_digest", "verification_scope"} {
		changed := map[string]any{}
		for k, v := range payload {
			changed[k] = v
		}
		changed[key] = "different"
		raw, _ = json.Marshal(changed)
		if _, err = ValidateGitReceipt(raw, proof, proof.Payload.Publication); err == nil {
			t.Fatal("tampered receipt accepted", key)
		}
	}
	payload["production_changed"] = true
	raw, _ = json.Marshal(payload)
	if _, err = ValidateGitReceipt(raw, proof, proof.Payload.Publication); err == nil {
		t.Fatal("unexpected deployment accepted")
	}
}
