package cli

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/schemacheck"
	"github.com/spf13/cobra"
	"os"
	"path/filepath"
	"regexp"
	"time"
)

func (a *App) requestReleaseTest(cmd *cobra.Command, client *controlplane.Client, path string, data []byte) (any, error) {
	var body map[string]any
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	if decoder.Decode(&body) != nil {
		return nil, output.New(2, "Release testcase must be an object")
	}
	// Do not claim recoverable identity against an older backend that silently
	// discards unknown DTO fields. This preflight is read-only and needs no registry.
	_, doc, _, definition, err := a.serverOperation(cmd.Context(), "project agent release run-test")
	if err != nil {
		return nil, err
	}
	requestBody, _ := definition["requestBody"].(map[string]any)
	content, _ := requestBody["content"].(map[string]any)
	media, _ := content["application/json"].(map[string]any)
	schema, _ := media["schema"].(map[string]any)
	for depth := 0; depth < 8; depth++ {
		ref, _ := schema["$ref"].(string)
		if ref == "" {
			break
		}
		resolved, resolveErr := schemacheck.Resolve(doc, ref)
		if resolveErr != nil {
			return nil, output.New(9, "Test identity schema could not be resolved")
		}
		schema, _ = resolved.(map[string]any)
	}
	properties, _ := schema["properties"].(map[string]any)
	if _, exists := properties["test_id"]; !exists {
		return nil, output.New(9, "Backend does not advertise recoverable release-test identity; update Woobe before executing")
	}
	if body["project_id"] == nil {
		body["project_id"] = a.Project
	}
	safeIdentifier := regexp.MustCompile(`^[A-Za-z0-9_-]{1,128}$`)
	for _, field := range []string{"project_id", "agent_id", "release_id"} {
		value, ok := body[field].(string)
		if !ok || !safeIdentifier.MatchString(value) {
			return nil, output.New(2, "Release testcase requires valid project_id, agent_id and release_id")
		}
	}
	id, _ := body["test_id"].(string)
	if supplied, exists := body["test_id"]; exists && supplied != nil {
		if _, ok := supplied.(string); !ok || id == "" {
			return nil, output.New(2, "test_id must be a UUID")
		}
	}
	if id == "" {
		nonce := make([]byte, 16)
		if _, err := rand.Read(nonce); err != nil {
			return nil, err
		}
		nonce[6] = (nonce[6] & 15) | 64
		nonce[8] = (nonce[8] & 63) | 128
		h := hex.EncodeToString(nonce)
		id = h[:8] + "-" + h[8:12] + "-" + h[12:16] + "-" + h[16:20] + "-" + h[20:]
		body["test_id"] = id
	}
	if !uuidReference(id) {
		return nil, output.New(2, "test_id must be a UUID")
	}
	encoded, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	digest := fmt.Sprintf("%x", sha256.Sum256(encoded))
	folder := filepath.Join(filepath.Dir(a.ConfigPath), "release-test-intents")
	if err = packagecheckpoint.EnsurePrivateDirectory(folder); err != nil {
		return nil, err
	}
	recovery := fmt.Sprintf("woobe project agent release tests %v %v --fields \"id,status,validation_errors\"", body["agent_id"], body["release_id"]) + " --project " + body["project_id"].(string)
	intent := map[string]any{"schema_version": "1", "test_id": id, "api_origin": client.Base, "project_id": body["project_id"], "agent_id": body["agent_id"], "release_id": body["release_id"], "request_sha256": digest, "recovery_command": recovery}
	receipt, _ := json.Marshal(intent)
	destination := filepath.Join(folder, id+".json")
	if existing, readErr := packagecheckpoint.ReadPrivate(destination); readErr == nil {
		if string(existing) != string(receipt) {
			return nil, output.New(9, "Test identity belongs to another request; observe its result before starting a new test")
		}
	} else {
		// ReadPrivate deliberately normalizes missing files; use Lstat only to
		// distinguish absence before publishing the protected receipt.
		if _, statErr := os.Lstat(destination); !os.IsNotExist(statErr) {
			return nil, readErr
		}
		if err = packagecheckpoint.WritePrivateExclusive(destination, receipt); err != nil {
			return nil, err
		}
	}
	if !a.Root.PersistentFlags().Changed("timeout") {
		client.HTTP.Timeout = 2 * time.Minute
	}
	result, _, err := client.Request(cmd.Context(), "POST", path, nil, encoded)
	if err != nil {
		failure := output.Normalize(err)
		if failure.Outcome == "unknown" || failure.Code == 8 || failure.Code == 130 || cmd.Context().Err() == context.Canceled {
			failure.TestID = id
			failure.RecoveryCommand = recovery
			failure.Message = "Test response was not observed; remote status is unknown. Test " + id + "; inspect " + recovery + ". Do not repeat the POST"
			failure.Outcome = "unknown"
		}
		return nil, failure
	}
	return result, nil
}
