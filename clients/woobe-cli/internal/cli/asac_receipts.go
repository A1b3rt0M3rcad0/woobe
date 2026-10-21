package cli

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/asac"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/requestinput"
	"github.com/spf13/cobra"
)

func readSignedFile(path string, target any) error {
	file, err := os.Open(path)
	if err != nil {
		return output.New(2, "Cannot read receipt or trust file")
	}
	defer file.Close()
	info, err := file.Stat()
	if err != nil || !info.Mode().IsRegular() {
		return output.New(2, "Receipt and trust inputs must be regular files")
	}
	raw, err := io.ReadAll(io.LimitReader(file, 4*1024*1024+1))
	if err != nil {
		return output.New(2, "Cannot read receipt or trust file")
	}
	raw, err = requestinput.Decode(raw, path, "auto")
	if err != nil {
		return output.New(2, "Receipt and trust input must be bounded YAML or JSON")
	}
	if err = asac.DecodeSigned(raw, target); err != nil {
		return output.New(9, err.Error())
	}
	return nil
}
func readTrustInput(path string) (asac.TrustManifest, error) {
	// A signed export can carry the manifest. A standalone root-signed manifest
	// is accepted too, without trusting either until its pinned root is checked.
	var envelope asac.SignedReceipt
	if err := readSignedFile(path, &envelope); err == nil && envelope.Trust.Format != "" {
		return envelope.Trust, nil
	}
	var manifest asac.TrustManifest
	err := readSignedFile(path, &manifest)
	return manifest, err
}
func writeReceiptFile(path string, value any) error {
	data, err := json.MarshalIndent(value, "", "  ")
	if err != nil {
		return output.New(9, "Cannot encode receipt")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	var document map[string]any
	if err = decoder.Decode(&document); err != nil {
		return output.New(9, "Cannot encode receipt")
	}
	data, err = devworkspace.EncodeFile(document, path)
	if err != nil {
		return output.New(9, "Cannot encode bounded receipt")
	}
	// Export is exclusive: an existing or symlink destination is never followed.
	file, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0644)
	if err != nil {
		return output.New(2, "Destination exists or cannot be created; choose a new receipt path")
	}
	ok := false
	defer func() {
		file.Close()
		if !ok {
			os.Remove(path)
		}
	}()
	if _, err = file.Write(data); err == nil {
		err = file.Sync()
	}
	if err != nil {
		return output.New(2, "Cannot save receipt")
	}
	if err = file.Close(); err != nil {
		return output.New(2, "Cannot save receipt")
	}
	ok = true
	return nil
}
func (a *App) asacReceiptCommands() {
	var pinPath, fingerprint string
	pin := &cobra.Command{Use: "pin INPUT", Short: "Pin an operator-confirmed instance root for offline verification", Args: cobra.ExactArgs(1), Long: "INPUT is a signed receipt export or root-signed manifest. Confirm the root fingerprint through the instance operator before pinning it; an API response does not establish trust by itself. Creates a new public YAML/JSON trust file without replacing an existing pin. Does not copy keys or credentials.", RunE: func(cmd *cobra.Command, args []string) error {
		if a.File != "" || a.DryRun {
			return output.New(2, "trust pin is local; use its INPUT and --path")
		}
		manifest, err := readTrustInput(args[0])
		if err != nil {
			return err
		}
		if err = asac.ValidateTrust(manifest, fingerprint, time.Now()); err != nil {
			return output.New(9, err.Error())
		}
		pinned := asac.PinnedTrust{Format: "woobe-pinned-asac-trust", Version: asac.Version, RootFingerprint: fingerprint, Manifest: manifest}
		if err = writeReceiptFile(pinPath, pinned); err != nil {
			return err
		}
		return a.emit(map[string]any{"path": pinPath, "instance_id": manifest.Instance, "root_fingerprint": fingerprint, "trust_epoch": manifest.Epoch, "trust_expires_at": manifest.Expires, "remote_changed": false})
	}}
	pin.Flags().StringVar(&pinPath, "path", "", "New public trust file (required)")
	pin.MarkFlagRequired("path")
	pin.Flags().StringVar(&fingerprint, "root-fingerprint", "", "Operator-confirmed SHA-256 root fingerprint (required)")
	pin.MarkFlagRequired("root-fingerprint")
	a.group("trust").AddCommand(pin)
	var oldPath, newPath string
	refresh := &cobra.Command{Use: "refresh INPUT", Short: "Verify a rotated manifest against an existing pinned root", Args: cobra.ExactArgs(1), Long: "Verifies the root signature, instance, expiry and monotonic manifest epoch. Rejects same-epoch rewrites, root replacements and epoch rollback. Saves to a new --path so changes to trust and revocation can be reviewed before replacing the existing --trust file. Offline verification uses the explicit manifest watermark and cannot discover later revocation without refresh.", RunE: func(cmd *cobra.Command, args []string) error {
		if a.File != "" || a.DryRun {
			return output.New(2, "trust refresh is local; use INPUT, --trust and --path")
		}
		var old asac.PinnedTrust
		if err := readSignedFile(oldPath, &old); err != nil {
			return err
		}
		next, err := readTrustInput(args[0])
		if err != nil {
			return err
		}
		refreshed, err := asac.RefreshTrust(old, next, time.Now())
		if err != nil {
			return output.New(9, err.Error())
		}
		if err = writeReceiptFile(newPath, refreshed); err != nil {
			return err
		}
		return a.emit(map[string]any{"path": newPath, "instance_id": next.Instance, "trust_epoch": next.Epoch, "trust_expires_at": next.Expires, "root_changed": false, "remote_changed": false})
	}}
	refresh.Flags().StringVar(&oldPath, "trust", "", "Existing pinned trust file (required)")
	refresh.MarkFlagRequired("trust")
	refresh.Flags().StringVar(&newPath, "path", "", "New public trust file for review (required)")
	refresh.MarkFlagRequired("path")
	a.group("trust").AddCommand(refresh)
	var trustPath string
	verify := &cobra.Command{Use: "verify FILE", Short: "Verify an owner receipt offline against an explicitly pinned root", Args: cobra.ExactArgs(1), Long: "Checks the exact signed payload, scope, instance, key validity, revocation and the pinned trust manifest signature/expiry. Does not authenticate credentials, grant permissions, assert current environment selection or turn declared Git metadata into verified provenance. No network or .woobe-config is needed.", RunE: func(cmd *cobra.Command, args []string) error {
		var receipt asac.SignedReceipt
		var pin asac.PinnedTrust
		if a.File != "" || a.DryRun {
			return output.New(2, "receipt verify is local; use FILE and --trust")
		}
		if err := readSignedFile(args[0], &receipt); err != nil {
			return err
		}
		if err := readSignedFile(trustPath, &pin); err != nil {
			return err
		}
		if err := asac.VerifyReceipt(receipt, pin, time.Now()); err != nil {
			return output.New(9, err.Error())
		}
		return a.emit(map[string]any{"verified": true, "authenticity": "instance_signature", "instance_id": receipt.Payload.Instance, "project_id": receipt.Payload.Project, "resource_id": receipt.Payload.Resource, "category": receipt.Payload.Category, "record_digest": receipt.Digest, "trust_epoch": pin.Manifest.Epoch, "trust_expires_at": pin.Manifest.Expires, "current_selection": "not_observed", "git_provenance": "not_upgraded"})
	}}
	verify.Flags().StringVar(&trustPath, "trust", "", "Explicitly pinned trust file (required)")
	verify.MarkFlagRequired("trust")
	a.group("receipt").AddCommand(verify)
	for _, kind := range []string{"agent", "network"} {
		var path, environment string
		command := &cobra.Command{Use: "receipt REFERENCE CATEGORY RECEIPT_ID", Short: "Export a server-signed immutable owner receipt", Args: cobra.ExactArgs(3), Long: "Read an authorized revision, evaluation, publication or deployment and obtain its instance signature. --path saves an exclusive YAML or JSON file, according to its extension. Pin the operator-confirmed root separately before offline verification. The original owner record and operation are unchanged. Native UUID use does not require development configuration.", RunE: func(cmd *cobra.Command, args []string) error {
			switch args[1] {
			case "revision", "evaluation", "publication", "deployment":
			default:
				return output.New(2, "Use revision, evaluation, publication or deployment")
			}
			if a.File != "" {
				return output.New(2, "Receipt export is read-only; use --path for the destination")
			}
			id, err := a.nativeReference(kind+"_id", args[0])
			if err != nil {
				return err
			}
			if err = resourceID(id); err != nil {
				return err
			}
			if _, err = a.resolve(); err != nil {
				return err
			}
			endpoint := fmt.Sprintf("/projects/%s/%ss/%s/asac/signed-receipts/%s/%s", url.PathEscape(a.Project), kind, url.PathEscape(id), args[1], url.PathEscape(args[2]))
			if a.DryRun {
				return a.emit(map[string]any{"method": "GET", "path": endpoint, "executed": false})
			}
			control, err := a.client()
			if err != nil {
				return err
			}
			response, _, err := control.Request(cmd.Context(), "GET", endpoint, url.Values{"environment": {environment}}, nil)
			if err != nil {
				return err
			}
			data, err := developmentResponseData(response)
			if err != nil {
				return err
			}
			raw, err := json.Marshal(data)
			if err != nil {
				return output.New(9, "Invalid signed receipt")
			}
			var signed asac.SignedReceipt
			if err = asac.DecodeSigned(raw, &signed); err != nil {
				return output.New(9, err.Error())
			}
			if signed.Payload.Project != a.Project || signed.Payload.Resource != id || signed.Payload.Kind != stringsTitle(kind) || signed.Payload.Category != args[1] {
				return output.New(9, "Signed receipt belongs to another owner or destination")
			}
			if path == "" {
				return a.emit(data)
			}
			if err = writeReceiptFile(path, signed); err != nil {
				return err
			}
			absolute, _ := filepath.Abs(path)
			return a.emit(map[string]any{"path": absolute, "category": args[1], "record_digest": signed.Digest, "authenticity": "signature_not_yet_verified", "root_fingerprint": signed.Trust.RootFingerprint})
		}}
		command.Flags().StringVar(&path, "path", "", "Exclusive YAML/JSON destination for the signed receipt")
		command.Flags().StringVar(&environment, "env", "production", "Deployment read authority: staging or production")
		a.group("develop " + kind).AddCommand(command)
	}
}
func stringsTitle(kind string) string {
	if kind == "agent" {
		return "Agent"
	}
	return "Network"
}
