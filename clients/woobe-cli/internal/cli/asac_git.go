package cli

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"net/url"
	"strings"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/asac"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/spf13/cobra"
)

func (a *App) asacGitCommands() {
	for _, kind := range []string{"agent", "network"} {
		var revision, commit, repository, publication, issuer, instance, workflow, keyFile, destination, nativeID string
		sign := &cobra.Command{Use: "git-proof REFERENCE", Short: "Verify committed author bytes and sign CI provenance offline", Args: cobra.ExactArgs(1), Long: "Only a trusted CI pipeline should hold this separate private signing seed. Verify the sealed revision's retained author closure against exact regular Git blobs and the canonical compiler, then sign a one-hour claim for an existing Publication. Does not publish, deploy, commit files or confer authority; the server must independently authorize this issuer, key, repository, Project and Control Key principal. Output is a separate exclusive YAML/JSON file, avoiding circular commit hashes.", RunE: func(cmd *cobra.Command, args []string) error {
			if a.DryRun || a.File != "" {
				return output.New(2, "git-proof uses --path and explicit proof flags; no --dry-run or --file")
			}
			for _, value := range []string{revision, commit, repository, publication, issuer, instance, workflow, keyFile, destination} {
				if value == "" {
					return output.New(2, "Supply revision, commit, repository, publication, issuer, instance, workflow-run, signing-key-file and path")
				}
			}
			if !uuidReference(publication) || !uuidReference(instance) || !uuidReference(a.Project) || !uuidReference(nativeID) {
				return output.New(2, "Explicit --project, --resource-id, --publication and --instance UUIDs are required")
			}
			c, err := a.developmentConfig(true)
			if err != nil {
				return err
			}
			resource, err := c.Resolve(strings.Title(kind), args[0])
			if err != nil {
				return output.New(2, err.Error())
			}
			record, err := c.ReadRevision(*resource, revision)
			if err != nil {
				return output.New(2, err.Error())
			}
			graph, err := devworkspace.LoadGraph(c)
			if err != nil {
				return output.New(2, err.Error())
			}
			if err = graph.VerifyGitRevision(*resource, record, commit); err != nil {
				return output.New(9, err.Error())
			}
			// A native resource UUID is explicit. No credentials/private registry state
			// need to be copied from a developer machine into the CI checkout.
			raw, err := packagecheckpoint.ReadPrivate(keyFile)
			if err != nil {
				return output.New(2, "Signing seed must be a private regular file")
			}
			defer func() {
				for i := range raw {
					raw[i] = 0
				}
			}()
			seed, err := base64.RawURLEncoding.DecodeString(strings.TrimSpace(string(raw)))
			if err != nil {
				return output.New(2, "Signing seed must be base64url encoded")
			}
			now := time.Now().Unix()
			proof, err := asac.SignGit(asac.GitPayload{Format: "woobe-git-attestation", Version: "1.0", Issuer: issuer, Instance: instance, Project: a.Project, Resource: nativeID, Kind: strings.Title(kind), Publication: publication, Revision: record.ID, RecordDigest: record.RecordDigest, DefinitionDigest: record.DefinitionDigest, AuthorDigest: record.AuthorDigest, Repository: repository, Commit: commit, Workflow: workflow, Issued: now, Expires: now + 3600}, seed)
			for i := range seed {
				seed[i] = 0
			}
			for i := range raw {
				raw[i] = 0
			}
			if err != nil {
				return output.New(2, err.Error())
			}
			if err = writeReceiptFile(destination, proof); err != nil {
				return err
			}
			return a.emit(map[string]any{"path": destination, "git_status": "pipeline_signed_not_server_verified", "definition_digest": record.DefinitionDigest, "remote_changed": false})
		}}
		sign.Flags().StringVar(&nativeID, "resource-id", "", "Native Agent/Network UUID independently confirmed from the Publication")
		sign.Flags().StringVar(&revision, "revision", "", "Sealed local revision ID")
		sign.Flags().StringVar(&commit, "commit", "", "Exact existing Git commit SHA containing the author closure")
		sign.Flags().StringVar(&repository, "repository", "", "Exact repository identity authorized by the instance operator")
		sign.Flags().StringVar(&publication, "publication", "", "Existing native Publication UUID")
		sign.Flags().StringVar(&issuer, "issuer", "", "Configured trusted pipeline issuer")
		sign.Flags().StringVar(&instance, "instance", "", "Authorized instance UUID")
		sign.Flags().StringVar(&workflow, "workflow-run", "", "Pipeline run identity for audit")
		sign.Flags().StringVar(&keyFile, "signing-key-file", "", "Private CI seed file (base64url Ed25519 seed)")
		sign.Flags().StringVar(&destination, "path", "", "Exclusive public signed-proof YAML/JSON destination")
		a.group("develop " + kind).AddCommand(sign)
		attach := &cobra.Command{Use: "git-attest REFERENCE", Short: "Attach a trusted pipeline proof to an existing Publication", Args: cobra.ExactArgs(1), Long: "Requires a signed --file proof and --idempotency-key operation UUID. No publication or deployment is performed, and the original Publication receipt is never rewritten. On timeout inspect project agent/network git-attestation get RESOURCE_UUID ORIGINAL_OPERATION_UUID; never submit a new operation until the original is known.", RunE: func(cmd *cobra.Command, args []string) error {
			if a.File == "" || !uuidReference(a.IdempotencyKey) {
				return output.New(2, "Supply --file signed-proof.yaml and --idempotency-key UUID")
			}
			var proof asac.SignedGit
			if err := readSignedFile(a.File, &proof); err != nil {
				return err
			}
			id, err := a.nativeReference(kind+"_id", args[0])
			if err != nil {
				return err
			}
			control, err := a.client()
			if err != nil {
				return err
			}
			if proof.Payload.Resource != id || proof.Payload.Project != a.Project || proof.Payload.Kind != strings.Title(kind) {
				return output.New(2, "Git proof belongs to another destination")
			}
			path := fmt.Sprintf("/projects/%s/%ss/%s/asac/git-attestations", url.PathEscape(a.Project), kind, url.PathEscape(id))
			if a.DryRun {
				return a.emit(map[string]any{"path": path, "method": "POST", "executed": false})
			}
			body, _ := json.Marshal(map[string]any{"operation_id": a.IdempotencyKey, "attestation": proof})
			response, _, err := control.Request(cmd.Context(), "POST", path, nil, body)
			if err != nil {
				return err
			}
			data, err := developmentResponseData(response)
			if err != nil {
				return err
			}
			rawReceipt, err := json.Marshal(data)
			if err != nil {
				return output.New(9, "Git receipt unavailable; inspect the original operation")
			}
			receipt, err := asac.ValidateGitReceipt(rawReceipt, proof, a.IdempotencyKey)
			if err != nil {
				return output.New(9, "Git receipt incompatible; inspect the original operation")
			}
			return a.emit(receipt)
		}}
		a.group("develop " + kind).AddCommand(attach)
	}
}
