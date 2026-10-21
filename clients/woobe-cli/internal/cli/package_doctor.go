package cli

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"os"

	privateconfig "github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/spf13/cobra"
)

func validPackagePrincipal(value string) bool {
	decoded, err := hex.DecodeString(value)
	return err == nil && len(decoded) == sha256.Size
}

func packageCatalogLineEndings(capabilities packageapi.Capabilities) string {
	if capabilities.SchemaCatalogSHA256 == packagefmt.CatalogDigest() {
		return "compatible"
	}
	catalog := bytes.ReplaceAll(packagefmt.CatalogBytes(), []byte("\r\n"), []byte("\n"))
	crlf := sha256.Sum256(bytes.ReplaceAll(catalog, []byte("\n"), []byte("\r\n")))
	if capabilities.SchemaCatalogSHA256 == hex.EncodeToString(crlf[:]) {
		return "windows_crlf"
	}
	return "different_catalog"
}

func packageCatalogCompatibility(client *packageapi.Client, capabilities packageapi.Capabilities) error {
	reason := packageCatalogLineEndings(capabilities)
	if reason == "compatible" {
		return nil
	}
	hint := "Update the backend and CLI to matching Package schemas"
	if reason == "windows_crlf" {
		hint = "Server catalog has Windows CRLF line endings; update the Woobe backend with the LF-normalized catalog digest fix and restart the API"
	}
	return output.New(9, fmt.Sprintf("Package catalog mismatch at %s: expected %s, server %s. %s. Run woobe package doctor; --context NAME overrides the connection pinned in .woobe-config", client.Control.Base, packagefmt.CatalogDigest(), capabilities.SchemaCatalogSHA256, hint))
}

func (a *App) packageDoctorCommand(group *cobra.Command) {
	group.AddCommand(&cobra.Command{
		Use: "doctor", Short: "Read Package compatibility and the effective development connection",
		Long: "Read server Package capabilities without importing, exporting or modifying local state. Use the same optional .woobe-config connection as managed pull/push. An explicit --context overrides it; --no-project-config ignores it. Authority fingerprints are validated but never displayed.",
		Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			config, err := a.developmentConfig(false)
			if err != nil {
				return err
			}
			configPath, pinned := "", ""
			if config != nil {
				configPath, pinned = config.File, config.Context
				if a.ContextName == "" && os.Getenv("WOOBE_CONTEXT") == "" {
					a.ContextName = pinned
				}
			}
			control, err := a.client()
			if err != nil {
				return err
			}
			client, err := packageapi.New(control, a.Project)
			if err != nil {
				return err
			}
			capabilities, err := client.Capabilities(cmd.Context())
			if err != nil {
				return err
			}
			schema := packageCatalogLineEndings(capabilities)
			authority := validPackagePrincipal(capabilities.PrincipalFingerprint)
			managed := false
			for _, operation := range capabilities.SupportedOperations {
				if operation == "sync" {
					managed = true
				}
			}
			effectiveContext := a.ContextName
			if effectiveContext == "" {
				effectiveContext = os.Getenv("WOOBE_CONTEXT")
			}
			if effectiveContext == "" {
				saved, err := privateconfig.Load(a.ConfigPath)
				if err != nil {
					return err
				}
				effectiveContext = saved.Current
			}
			result := map[string]any{
				"client_version": Version, "client_commit": Commit,
				"api_url": control.Base, "project_id": a.Project,
				"context": effectiveContext, "project_config": configPath, "pinned_context": pinned,
				"expected_catalog_sha256": packagefmt.CatalogDigest(),
				"server_catalog_sha256":   capabilities.SchemaCatalogSHA256,
				"catalog_status":          schema, "authority_fingerprint_valid": authority,
				"managed_development_supported": managed,
				"compatible":                    schema == "compatible" && authority && managed,
				"executed":                      false,
			}
			if result["compatible"] != true {
				return &diagnosticPartial{Data: result}
			}
			return a.emit(result)
		},
	})
}
