package cli

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/spf13/cobra"
	"os"
	"path/filepath"
)

func (a *App) automaticPackageCheckpoint(ctx context.Context, source, plan, lifecycle string) (string, error) {
	client, err := a.packageClient(ctx, "apply")
	if err != nil {
		return "", err
	}
	capabilities, err := client.Capabilities(ctx)
	if err != nil {
		return "", err
	}
	input := source
	if plan != "" {
		input = plan
	}
	if plan == "" && filepath.Base(input) == "woobe.yaml" {
		input = filepath.Dir(input)
	}
	input, err = filepath.Abs(input)
	if err != nil {
		return "", err
	}
	identity, err := json.Marshal([]string{client.Control.Base, client.ProjectID, capabilities.PrincipalFingerprint, input, lifecycle})
	if err != nil {
		return "", err
	}
	digest := sha256.Sum256(identity)
	directory := filepath.Join(filepath.Dir(a.ConfigPath), "package-imports")
	if err = packagecheckpoint.EnsurePrivateDirectory(directory); err != nil {
		return "", err
	}
	return filepath.Join(directory, hex.EncodeToString(digest[:])+".json"), nil
}

func (a *App) packageBindingsCommand(group *cobra.Command) {
	var destination string
	command := &cobra.Command{Use: "bindings SOURCE", Short: "Generate a destination bindings YAML template offline", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
		if a.DryRun && destination != "" {
			return output.New(2, "Bindings --dry-run cannot write a destination; omit --destination to preview YAML")
		}
		if err := packageFlags(cmd, "yes"); err != nil {
			return err
		}
		bundle, err := loadPackage(args[0], false)
		if err != nil {
			return err
		}
		defer bundle.Close()
		requires := packagefmt.Requirements(bundle.Graph.Manifest)
		version := packagefmt.Text(bundle.Graph.Manifest["schema_version"])
		spec := map[string]any{}
		for _, group := range []string{"credentials", "project_environment", "secrets", "knowledge"} {
			bindings := map[string]any{}
			items, _ := requires[group].([]any)
			for _, item := range items {
				requirement := packagefmt.Object(item)
				alias := packagefmt.Text(requirement["ref"])
				binding := map[string]any{}
				switch group {
				case "credentials":
					binding["credential_id"] = "REPLACE_WITH_DESTINATION_CREDENTIAL_UUID"
				case "knowledge":
					binding["vector_snapshot_id"] = "REPLACE_WITH_DESTINATION_VECTOR_SNAPSHOT_UUID"
				case "project_environment":
					alias = packagefmt.Text(requirement["key"])
					binding["protected_ref"] = "REPLACE_WITH_PRIVATE_CREDENTIAL_REFERENCE"
				case "secrets":
					binding["protected_ref"] = "REPLACE_WITH_PRIVATE_CREDENTIAL_REFERENCE"
				}
				if version == "2.0" && (group == "credentials" || group == "project_environment") {
					binding = map[string]any{"create": true}
				}
				bindings[alias] = binding
			}
			spec[group] = bindings
		}
		if version == "2.0" {
			delete(spec, "secrets")
		}
		document := map[string]any{"format": "woobe-package", "schema_version": version, "kind": "ImportBindings", "metadata": map[string]string{"name": "Destination"}, "spec": spec}
		data, err := devworkspace.Encode(document)
		if err != nil {
			return err
		}
		if destination == "" {
			_, err = a.Out.Write(data)
			return err
		}
		absolute, err := filepath.Abs(destination)
		if err != nil {
			return err
		}
		if err = excludePackageOperationalFiles(args[0], bundle, absolute); err != nil {
			return err
		}
		file, err := os.OpenFile(absolute, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
		if err != nil {
			return output.New(2, "Bindings destination already exists or cannot be created")
		}
		_, writeErr := file.Write(data)
		closeErr := file.Close()
		if writeErr != nil {
			return writeErr
		}
		if closeErr != nil {
			return closeErr
		}
		next := "Fill placeholders, then run woobe package plan SOURCE --bindings " + absolute
		if version == "2.0" {
			next = "Review create/reuse choices, then run woobe package plan SOURCE --structural --bindings " + absolute
		}
		return a.emit(map[string]any{"destination": absolute, "template": true, "ready": false, "next_command": next})
	}}
	command.Flags().StringVar(&destination, "destination", "", "New YAML file; otherwise print the template")
	group.AddCommand(command)
}
