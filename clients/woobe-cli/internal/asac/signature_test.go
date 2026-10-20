package asac

import (
	"crypto/ed25519"
	"encoding/base64"
	"os"
	"testing"
	"time"
)

func signedFixture(t *testing.T) (SignedReceipt, PinnedTrust, time.Time) {
	t.Helper()
	raw, err := os.ReadFile("testdata/asac-signed-receipt.json")
	if err != nil {
		t.Fatal(err)
	}
	var f struct {
		Now    string        `json:"now"`
		Signed SignedReceipt `json:"signed"`
		Pin    PinnedTrust   `json:"pin"`
	}
	if err = DecodeSigned(raw, &f); err != nil {
		t.Fatal(err)
	}
	now, err := time.Parse(time.RFC3339, f.Now)
	if err != nil {
		t.Fatal(err)
	}
	return f.Signed, f.Pin, now
}
func resignManifest(t *testing.T, m *TrustManifest) {
	t.Helper()
	seed := make([]byte, 32)
	for i := range seed {
		seed[i] = byte(i)
	}
	digest, err := Digest("trust-manifest", unsignedManifest(*m))
	if err != nil {
		t.Fatal(err)
	}
	m.Digest = digest
	m.Signature = base64.RawURLEncoding.EncodeToString(ed25519.Sign(ed25519.NewKeyFromSeed(seed), []byte(digest)))
}
func TestPythonOwnerSignaturePreservesUnicodeAndLargeIntegers(t *testing.T) {
	s, p, now := signedFixture(t)
	if err := VerifyReceipt(s, p, now); err != nil {
		t.Fatal(err)
	}
	if got := s.Payload.Receipt["fixture_number"].(interface{ String() string }).String(); got != "9007199254740993" {
		t.Fatal(got)
	}
	// The signature authenticates a declared Git claim; it does not upgrade it.
	if s.Payload.Receipt["origin"].(map[string]any)["git_status"] != "declared" {
		t.Fatal("Git claim upgraded")
	}
}
func TestSignedReceiptCannotTamperOrReplacePinnedRoot(t *testing.T) {
	for _, scenario := range []string{"payload", "digest", "signature", "root", "instance", "future", "expired", "scope"} {
		t.Run(scenario, func(t *testing.T) {
			s, p, now := signedFixture(t)
			switch scenario {
			case "payload":
				s.Payload.Receipt["state"] = "tamper"
			case "digest":
				s.Digest = "sha256:" + string(make([]byte, 64))
			case "signature":
				s.Signature = "bad"
			case "root":
				p.RootFingerprint = "sha256:foreign"
			case "instance":
				s.Payload.Instance = "foreign"
			case "future":
				s.Payload.Issued = now.Add(time.Hour).Format(time.RFC3339)
			case "expired":
				now = now.AddDate(1, 0, 0)
			case "scope":
				s.Payload.Project = "foreign"
			}
			if err := VerifyReceipt(s, p, now); err == nil {
				t.Fatal("forged receipt accepted")
			}
		})
	}
}
func TestTrustRotationRevocationAndEpochRollback(t *testing.T) {
	s, p, now := signedFixture(t)
	next := p.Manifest
	next.Keys = append([]VerificationKey(nil), p.Manifest.Keys...)
	next.Epoch++
	next.Keys[0].Status = "retired"
	resignManifest(t, &next)
	refreshed, err := RefreshTrust(p, next, now)
	if err != nil {
		t.Fatal(err)
	}
	if err = VerifyReceipt(s, refreshed, now); err != nil {
		t.Fatal("retired historical key rejected", err)
	}
	if _, err = RefreshTrust(refreshed, p.Manifest, now); err == nil {
		t.Fatal("epoch rollback accepted")
	}
	sameEpoch := next
	sameEpoch.Expires = "2026-11-02T00:00:00Z"
	resignManifest(t, &sameEpoch)
	if _, err = RefreshTrust(refreshed, sameEpoch, now); err == nil {
		t.Fatal("same epoch rewrite accepted")
	}
	revoked := next
	revoked.Keys = append([]VerificationKey(nil), next.Keys...)
	revoked.Keys[0].Status = "revoked"
	revoked.Epoch++
	resignManifest(t, &revoked)
	refreshed, err = RefreshTrust(refreshed, revoked, now)
	if err != nil {
		t.Fatal(err)
	}
	if err = VerifyReceipt(s, refreshed, now); err == nil {
		t.Fatal("revoked historical key accepted")
	}
}

func TestNewerSignedManifestRequiresExplicitTrustRefresh(t *testing.T) {
	s, p, now := signedFixture(t)
	s.Trust.Epoch++
	resignManifest(t, &s.Trust)
	if err := VerifyReceipt(s, p, now); err == nil {
		t.Fatal("new manifest silently trusted")
	}
}
func TestMalformedOrAmbiguousSignedJSONIsRejected(t *testing.T) {
	for _, raw := range []string{`{"payload":{},"payload":{}}`, `{} {}`, `null`, `{"unknown":true}`} {
		var s SignedReceipt
		if err := DecodeSigned([]byte(raw), &s); err == nil {
			t.Fatal("ambiguous signed data accepted", raw)
		}
	}
}
