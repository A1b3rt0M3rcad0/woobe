package asac

// Signatures attest owner data; they do not confer grants, currentness or
// executable availability. Trust is established with an operator-pinned root.
import (
	"bytes"
	"crypto/ed25519"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"io"
	"regexp"
	"time"
)

type VerificationKey struct {
	ID     string `json:"key_id"`
	Public string `json:"public_key"`
	Status string `json:"status"`
	Before string `json:"not_before"`
	After  string `json:"not_after"`
}
type TrustManifest struct {
	Format          string            `json:"format"`
	Version         string            `json:"schema_version"`
	Instance        string            `json:"instance_id"`
	Epoch           int64             `json:"epoch"`
	Expires         string            `json:"expires_at"`
	RootPublic      string            `json:"root_public_key"`
	RootFingerprint string            `json:"root_fingerprint"`
	Keys            []VerificationKey `json:"keys"`
	Digest          string            `json:"record_digest"`
	Signature       string            `json:"signature"`
}
type SignedPayload struct {
	Format   string         `json:"format"`
	Version  string         `json:"schema_version"`
	Instance string         `json:"instance_id"`
	Project  string         `json:"project_id"`
	Resource string         `json:"resource_id"`
	Kind     string         `json:"kind"`
	Category string         `json:"category"`
	Issued   string         `json:"issued_at"`
	KeyID    string         `json:"key_id"`
	Receipt  map[string]any `json:"receipt"`
}
type SignedReceipt struct {
	Payload   SignedPayload `json:"payload"`
	Digest    string        `json:"record_digest"`
	Signature string        `json:"signature"`
	Trust     TrustManifest `json:"trust"`
	Complete  bool          `json:"complete,omitempty"`
}
type PinnedTrust struct {
	Format          string        `json:"format"`
	Version         string        `json:"schema_version"`
	RootFingerprint string        `json:"root_fingerprint"`
	Manifest        TrustManifest `json:"manifest"`
}

var signingUUID = regexp.MustCompile(`^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$`)
var signingDigest = regexp.MustCompile(`^sha256:[a-f0-9]{64}$`)

func DecodeSigned(data []byte, target any) error {
	if len(data) > 4*1024*1024 {
		return fmt.Errorf("ASAC_SIGNATURE_INVALID: receipt exceeds bound")
	}
	trimmed := bytes.TrimSpace(data)
	if len(trimmed) == 0 || trimmed[0] != '{' {
		return fmt.Errorf("ASAC_SIGNATURE_INVALID: receipt must be an object")
	}
	if err := jsoninput.Validate(data); err != nil {
		return fmt.Errorf("ASAC_SIGNATURE_INVALID: ambiguous receipt JSON")
	}
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	d.UseNumber()
	if err := d.Decode(target); err != nil {
		return fmt.Errorf("ASAC_SIGNATURE_INVALID: malformed receipt")
	}
	if err := d.Decode(new(any)); err != io.EOF {
		return fmt.Errorf("ASAC_SIGNATURE_INVALID: trailing receipt data")
	}
	return nil
}
func keyBytes(text string, size int) ([]byte, error) {
	b, err := base64.RawURLEncoding.Strict().DecodeString(text)
	if err != nil || len(b) != size || base64.RawURLEncoding.EncodeToString(b) != text {
		return nil, fmt.Errorf("ASAC_SIGNATURE_INVALID: invalid Ed25519 encoding")
	}
	return b, nil
}
func publicFingerprint(public []byte) string {
	h := sha256.Sum256(public)
	return "sha256:" + hex.EncodeToString(h[:])
}
func unsignedManifest(m TrustManifest) map[string]any {
	return map[string]any{
		"format": m.Format, "schema_version": m.Version, "instance_id": m.Instance, "epoch": m.Epoch,
		"expires_at": m.Expires, "root_public_key": m.RootPublic, "root_fingerprint": m.RootFingerprint, "keys": m.Keys,
	}
}
func verifyBytes(scope string, data any, digest, signature string, public []byte) error {
	expected, err := Digest(scope, data)
	if err != nil || expected != digest {
		return fmt.Errorf("ASAC_SIGNATURE_INVALID: signed digest mismatch")
	}
	sig, err := keyBytes(signature, ed25519.SignatureSize)
	if err != nil {
		return err
	}
	if !ed25519.Verify(public, []byte(digest), sig) {
		return fmt.Errorf("ASAC_SIGNATURE_INVALID: signature verification failed")
	}
	return nil
}
func ValidateTrust(m TrustManifest, expectedRoot string, now time.Time) error {
	if m.Format != "woobe-asac-trust" || m.Version != Version || !signingUUID.MatchString(m.Instance) || m.Epoch < 1 || len(m.Keys) < 1 || len(m.Keys) > 64 {
		return fmt.Errorf("ASAC_TRUST_INVALID: invalid trust manifest")
	}
	root, err := keyBytes(m.RootPublic, ed25519.PublicKeySize)
	if err != nil {
		return err
	}
	if expectedRoot == "" || publicFingerprint(root) != expectedRoot || m.RootFingerprint != expectedRoot {
		return fmt.Errorf("ASAC_TRUST_ROOT_MISMATCH: explicit operator fingerprint required")
	}
	if err = verifyBytes("trust-manifest", unsignedManifest(m), m.Digest, m.Signature, root); err != nil {
		return err
	}
	expiry, err := time.Parse(time.RFC3339Nano, m.Expires)
	if err != nil || !now.Before(expiry) {
		return fmt.Errorf("ASAC_TRUST_EXPIRED: refresh the root-signed manifest")
	}
	seen := map[string]bool{}
	for _, key := range m.Keys {
		public, err := keyBytes(key.Public, ed25519.PublicKeySize)
		if err != nil {
			return err
		}
		before, e1 := time.Parse(time.RFC3339Nano, key.Before)
		after, e2 := time.Parse(time.RFC3339Nano, key.After)
		if seen[key.ID] || publicFingerprint(public) != key.ID || bytes.Equal(public, root) || e1 != nil || e2 != nil || !before.Before(after) ||
			(key.Status != "active" && key.Status != "retired" && key.Status != "revoked") {
			return fmt.Errorf("ASAC_TRUST_INVALID: invalid verification key")
		}
		seen[key.ID] = true
	}
	return nil
}
func RefreshTrust(old PinnedTrust, next TrustManifest, now time.Time) (PinnedTrust, error) {
	if old.Format != "woobe-pinned-asac-trust" || old.Version != Version {
		return old, fmt.Errorf("ASAC_TRUST_INVALID: invalid pinned root")
	}
	// An expired old manifest may be refreshed, but its signature must still
	// verify. Validate at an instant before its expiry, then validate next now.
	expiry, err := time.Parse(time.RFC3339Nano, old.Manifest.Expires)
	if err != nil {
		return old, err
	}
	if err = ValidateTrust(old.Manifest, old.RootFingerprint, expiry.Add(-time.Nanosecond)); err != nil {
		return old, err
	}
	if err = ValidateTrust(next, old.RootFingerprint, now); err != nil {
		return old, err
	}
	if next.Instance != old.Manifest.Instance || next.Epoch < old.Manifest.Epoch ||
		(next.Epoch == old.Manifest.Epoch && next.Digest != old.Manifest.Digest) {
		return old, fmt.Errorf("ASAC_TRUST_ROLLBACK: instance or manifest epoch differs")
	}
	old.Manifest = next
	return old, nil
}
func VerifyReceipt(s SignedReceipt, pin PinnedTrust, now time.Time) error {
	if pin.Format != "woobe-pinned-asac-trust" || pin.Version != Version {
		return fmt.Errorf("ASAC_TRUST_INVALID: an explicitly pinned root is required")
	}
	if err := ValidateTrust(pin.Manifest, pin.RootFingerprint, now); err != nil {
		return err
	}
	// Embedded trust is independently root-signed; it never replaces the pin.
	embeddedExpiry, err := time.Parse(time.RFC3339Nano, s.Trust.Expires)
	if err != nil {
		return fmt.Errorf("ASAC_TRUST_INVALID: invalid embedded manifest")
	}
	validateAt := now
	if !now.Before(embeddedExpiry) {
		validateAt = embeddedExpiry.Add(-time.Nanosecond)
	}
	if err = ValidateTrust(s.Trust, pin.RootFingerprint, validateAt); err != nil {
		return err
	}
	if s.Trust.Instance != pin.Manifest.Instance {
		return fmt.Errorf("ASAC_TRUST_ROOT_MISMATCH: embedded instance differs")
	}
	if s.Trust.Epoch > pin.Manifest.Epoch {
		return fmt.Errorf("ASAC_TRUST_REFRESH_REQUIRED: receipt carries a newer root-signed manifest")
	}
	if s.Trust.Epoch == pin.Manifest.Epoch && s.Trust.Digest != pin.Manifest.Digest {
		return fmt.Errorf("ASAC_TRUST_ROLLBACK: conflicting manifests at the same epoch")
	}
	p := s.Payload
	if p.Format != "woobe-signed-asac-receipt" || p.Version != Version || p.Instance != pin.Manifest.Instance ||
		!signingUUID.MatchString(p.Project) || !signingUUID.MatchString(p.Resource) || (p.Kind != "Agent" && p.Kind != "Network") || p.Receipt == nil {
		return fmt.Errorf("ASAC_SIGNATURE_INVALID: receipt scope is invalid")
	}
	switch p.Category {
	case "revision", "evaluation", "publication", "deployment", "history":
	default:
		return fmt.Errorf("ASAC_SIGNATURE_INVALID: invalid receipt category")
	}
	if p.Category == "deployment" {
		if _, private := p.Receipt["leases"]; private {
			return fmt.Errorf("ASAC_SIGNATURE_INVALID: private lease proof is not portable")
		}
		digest, ok := p.Receipt["owner_receipt_digest"].(string)
		if p.Receipt["projection_scope"] != "public-owner-deployment@1" || !ok || !signingDigest.MatchString(digest) {
			return fmt.Errorf("ASAC_SIGNATURE_INVALID: explicit public deployment projection required")
		}
	}
	issued, err := time.Parse(time.RFC3339Nano, p.Issued)
	if err != nil || issued.After(now.Add(5*time.Minute)) {
		return fmt.Errorf("ASAC_SIGNATURE_INVALID: invalid receipt issue time")
	}
	for _, key := range pin.Manifest.Keys {
		if key.ID == p.KeyID {
			if key.Status == "revoked" {
				return fmt.Errorf("ASAC_SIGNING_KEY_REVOKED: receipt key is revoked")
			}
			before, _ := time.Parse(time.RFC3339Nano, key.Before)
			after, _ := time.Parse(time.RFC3339Nano, key.After)
			if issued.Before(before) || !issued.Before(after) {
				return fmt.Errorf("ASAC_SIGNING_KEY_EXPIRED: receipt was issued outside key validity")
			}
			public, err := keyBytes(key.Public, ed25519.PublicKeySize)
			if err != nil {
				return err
			}
			if err = verifyBytes("signed-receipt", p, s.Digest, s.Signature, public); err != nil {
				return err
			}
			for _, scope := range []struct{ field, expected string }{{"project_id", p.Project}, {"resource_id", p.Resource}} {
				if value, ok := p.Receipt[scope.field]; ok && value != scope.expected {
					return fmt.Errorf("ASAC_SIGNATURE_INVALID: owner receipt scope mismatch")
				}
			}
			return nil
		}
	}
	return fmt.Errorf("ASAC_SIGNING_KEY_UNKNOWN: refresh pinned trust explicitly")
}
