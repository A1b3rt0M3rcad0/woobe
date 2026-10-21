package cli

import (
	"crypto/ed25519"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/asac"
)

func commandSignedFixture(t *testing.T) asac.SignedReceipt {
	t.Helper()
	raw, err := os.ReadFile("../asac/testdata/asac-signed-receipt.json")
	if err != nil {
		t.Fatal(err)
	}
	var f struct {
		Now    string             `json:"now"`
		Signed asac.SignedReceipt `json:"signed"`
		Pin    asac.PinnedTrust   `json:"pin"`
	}
	if err = asac.DecodeSigned(raw, &f); err != nil {
		t.Fatal(err)
	}
	s := f.Signed
	now := time.Now().UTC()
	s.Payload.Issued = now.Add(-time.Hour).Format(time.RFC3339Nano)
	s.Trust.Expires = now.Add(12 * time.Hour).Format(time.RFC3339Nano)
	s.Trust.Keys[0].Before = now.Add(-2 * time.Hour).Format(time.RFC3339Nano)
	s.Trust.Keys[0].After = now.Add(24 * time.Hour).Format(time.RFC3339Nano)
	signCommandManifest(t, &s.Trust)
	seed := make([]byte, 32)
	for i := range seed {
		seed[i] = byte(i + 32)
	}
	s.Digest, err = asac.Digest("signed-receipt", s.Payload)
	if err != nil {
		t.Fatal(err)
	}
	s.Signature = base64.RawURLEncoding.EncodeToString(ed25519.Sign(ed25519.NewKeyFromSeed(seed), []byte(s.Digest)))
	s.Complete = true
	return s
}
func signCommandManifest(t *testing.T, m *asac.TrustManifest) {
	t.Helper()
	raw, _ := json.Marshal(m)
	var document map[string]any
	decoder := json.NewDecoder(strings.NewReader(string(raw)))
	decoder.UseNumber()
	if err := decoder.Decode(&document); err != nil {
		t.Fatal(err)
	}
	delete(document, "record_digest")
	delete(document, "signature")
	digest, err := asac.Digest("trust-manifest", document)
	if err != nil {
		t.Fatal(err)
	}
	seed := make([]byte, 32)
	for i := range seed {
		seed[i] = byte(i)
	}
	m.Digest = digest
	m.Signature = base64.RawURLEncoding.EncodeToString(ed25519.Sign(ed25519.NewKeyFromSeed(seed), []byte(digest)))
}
func TestOfflineReceiptCommandsPinVerifyAndRevocationWithoutConnection(t *testing.T) {
	dir := t.TempDir()
	signed := commandSignedFixture(t)
	input := filepath.Join(dir, "receipt.json")
	pin := filepath.Join(dir, "trust.yaml")
	raw, _ := json.Marshal(signed)
	if err := os.WriteFile(input, raw, 0644); err != nil {
		t.Fatal(err)
	}
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { requests++; w.WriteHeader(500) }))
	defer server.Close()
	flags := []string{"--api-url", server.URL, "--no-project-config", "--output", "json"}
	run := func(args ...string) (int, map[string]any) { return invoke(t, append(args, flags...), "") }
	if code, _ := run("trust", "pin", input, "--root-fingerprint", "sha256:foreign", "--path", pin); code != 9 {
		t.Fatal("foreign root accepted", code)
	}
	if _, err := os.Stat(pin); !os.IsNotExist(err) {
		t.Fatal("failed pin wrote a file")
	}
	if code, result := run("trust", "pin", input, "--root-fingerprint", signed.Trust.RootFingerprint, "--path", pin); code != 0 {
		t.Fatal(code, result)
	}
	content, err := os.ReadFile(pin)
	if err != nil || strings.HasPrefix(strings.TrimSpace(string(content)), "{") {
		t.Fatal("trust file must be readable block YAML", err)
	}
	if code, result := run("receipt", "verify", input, "--trust", pin); code != 0 || result["data"].(map[string]any)["verified"] != true {
		t.Fatal(code, result)
	}
	if code, _ := run("trust", "pin", input, "--root-fingerprint", signed.Trust.RootFingerprint, "--path", pin); code != 2 {
		t.Fatal("pin overwritten", code)
	}
	signed.Payload.Receipt["state"] = "forged"
	raw, _ = json.Marshal(signed)
	os.WriteFile(input, raw, 0644)
	if code, _ := run("receipt", "verify", input, "--trust", pin); code != 9 {
		t.Fatal("forged receipt accepted", code)
	}
	signed = commandSignedFixture(t)
	signed.Trust.Epoch++
	signed.Trust.Keys[0].Status = "revoked"
	signCommandManifest(t, &signed.Trust)
	raw, _ = json.Marshal(signed)
	os.WriteFile(input, raw, 0644)
	next := filepath.Join(dir, "trust-next.yaml")
	if code, result := run("trust", "refresh", input, "--trust", pin, "--path", next); code != 0 {
		t.Fatal(code, result)
	}
	if code, _ := run("receipt", "verify", input, "--trust", next); code != 9 {
		t.Fatal("revoked key accepted", code)
	}
	if requests != 0 {
		t.Fatal("offline command accessed the network", requests)
	}
}
func TestSignedReceiptExportUsesOwnerRouteAndNeverOverwrites(t *testing.T) {
	signed := commandSignedFixture(t)
	signed.Payload.Category = "publication"
	signed.Payload.Kind = "Agent"
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != "GET" || !strings.Contains(r.URL.Path, "/agents/"+signed.Payload.Resource+"/asac/signed-receipts/publication/") {
			t.Error("wrong owner request", r.Method, r.URL.Path)
		}
		json.NewEncoder(w).Encode(map[string]any{"success": true, "data": signed})
	}))
	defer server.Close()
	t.Setenv("WOOBE_CONTROL_KEY", "test-control")
	file := filepath.Join(t.TempDir(), "publication.yaml")
	args := []string{"agent", signed.Payload.Resource, "receipt", "publication", "00000000-0000-4000-8000-000000000004", "--path", file, "--api-url", server.URL, "--project", signed.Payload.Project, "--workspace", "00000000-0000-4000-8000-000000000005", "--no-project-config", "--output", "json"}
	if code, result := invoke(t, args, ""); code != 0 {
		t.Fatal(code, result)
	}
	var exported asac.SignedReceipt
	if err := readSignedFile(file, &exported); err != nil || exported.Digest != signed.Digest {
		t.Fatal("export altered signed payload", err)
	}
	if code, _ := invoke(t, args, ""); code != 2 {
		t.Fatal("existing signed receipt overwritten", code)
	}
}
