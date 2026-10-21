package cli

import (
	"errors"
	"path/filepath"
	"strconv"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/spf13/cobra"
)

type packageFailure struct{ Diagnostic *packagefmt.Diagnostic }

func (e *packageFailure) Error() string { return e.Diagnostic.Error() }

func packageError(err error) error {
	var diagnostic *packagefmt.Diagnostic
	if !errors.As(err, &diagnostic) {
		diagnostic = &packagefmt.Diagnostic{Code: "PACKAGE_PATH_INVALID", Message: "Package input could not be read safely"}
	}
	return &packageFailure{diagnostic}
}

func packageFlags(cmd *cobra.Command, allowed ...string) error {
	permitted := map[string]bool{}
	for _, name := range allowed {
		permitted[name] = true
	}
	for _, name := range []string{"file", "input-format", "query", "secret-file", "if-match", "idempotency-key", "schema-sha256", "validate-body", "validate-parameters", "yes", "runtime-credential"} {
		if cmd.Flags().Changed(name) && !permitted[name] {
			return output.New(2, "--"+name+" is incompatible with this package command")
		}
	}
	return nil
}

func loadPackage(source string, locked bool) (*packagebundle.Bundle, error) {
	if strings.HasSuffix(source, ".tar.gz") || strings.HasSuffix(source, ".tgz") {
		bundle, err := packagebundle.LoadArchive(source, locked)
		if err != nil {
			return nil, packageError(err)
		}
		return bundle, nil
	}
	bundle, err := packagebundle.Load(source, locked)
	if err != nil {
		return nil, packageError(err)
	}
	return bundle, nil
}

func (a *App) packageCommands() {
	group := a.group("package")
	a.packageDoctorCommand(group)
	var locked bool
	var structureOnly bool
	validate := &cobra.Command{
		Use: "validate SOURCE", Short: "Validate a portable package locally without credentials or HTTP",
		Long:    "SOURCE accepts a package directory, its woobe.yaml, or a .tar.gz/.tgz archive. YAML uses one document without anchors, aliases or custom tags. Validate current schemas, references, paths and limits offline. By default a present captured lock is also verified; --locked requires that lock. Use --structure-only while editing to skip captured-lock verification explicitly. Structural success does not certify snapshot integrity, server semantics or import readiness. Validation never rewrites the source or its lock.",
		Example: "woobe package validate ./edited --structure-only\nwoobe package validate ./captured --locked\nwoobe package edit ./captured --destination ./author",
		Args:    cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			if err := packageFlags(cmd, "yes"); err != nil {
				return err
			}
			if locked && structureOnly {
				return output.New(2, "--structure-only and --locked are mutually exclusive")
			}
			var bundle *packagebundle.Bundle
			var err error
			mode := "structure_and_present_lock"
			if structureOnly {
				mode = "structure_only"
				if strings.HasSuffix(args[0], ".tar.gz") || strings.HasSuffix(args[0], ".tgz") {
					bundle, err = packagebundle.LoadArchiveStructure(args[0])
				} else {
					bundle, err = packagebundle.LoadStructure(args[0])
				}
				if err != nil {
					err = packageError(err)
				}
			} else {
				bundle, err = loadPackage(args[0], locked)
			}
			if err != nil {
				return err
			}
			defer bundle.Close()
			return a.emit(map[string]any{
				"package_schema_version": "1.0", "schema_catalog_sha256": packagefmt.CatalogDigest(),
				"valid": true, "artifact_digest": bundle.ArtifactDigest,
				"validation_mode": mode, "capture_integrity": bundle.LockIntegrity,
				"inventory": bundle.Inventory, "entrypoint": packagefmt.Object(bundle.Graph.Manifest["spec"])["entrypoint"],
				"materialization_order": bundle.Graph.Order, "diagnostics": []any{},
				"authorization": "not_evaluated", "semantic_validation": "server_required", "executed": false,
			})
		},
	}
	validate.Flags().BoolVar(&locked, "locked", false, "Require and verify woobe.lock.json without rewriting it")
	validate.Flags().BoolVar(&structureOnly, "structure-only", false, "Check edited schemas/references without evaluating the captured lock (read-only)")
	group.AddCommand(validate)
	for _, action := range []string{"edit", "seal"} {
		var destination string
		cmd := &cobra.Command{Use: action + " SOURCE", Args: cobra.ExactArgs(1), Short: action + " a separate portable package copy offline", Long: "edit verifies a sealed source and creates an editable copy without its captured lock. seal validates an author directory and creates a new sealed copy with a new inventory lock. Neither changes the source, overwrites destinations, calls the backend or validates server semantics. --destination must name a new directory under an existing parent.", Example: "woobe package edit ./captured --destination ./author\nwoobe package validate ./author\nwoobe package seal ./author --destination ./sealed\nwoobe package validate ./sealed --locked", RunE: func(cmd *cobra.Command, args []string) error {
			if err := packageFlags(cmd); err != nil {
				return err
			}
			if destination == "" {
				return output.New(2, "--destination requires a new separate directory")
			}
			bundle, err := loadPackage(args[0], action == "edit")
			if err != nil {
				return err
			}
			defer bundle.Close()
			absolute, err := filepath.Abs(destination)
			if err != nil {
				return err
			}
			if !a.DryRun {
				if action == "edit" {
					err = bundle.PublishAuthor(absolute)
				} else {
					err = bundle.Publish(absolute)
				}
				if err != nil {
					return packageError(err)
				}
			}
			next := "woobe package validate " + strconv.Quote(absolute)
			if action == "seal" {
				next += " --locked"
			}
			return a.emit(map[string]any{"action": action, "destination": absolute, "artifact_digest": bundle.ArtifactDigest, "source_retained": true, "sealed": action == "seal", "executed": !a.DryRun, "next_command": next, "authorization": "not_evaluated", "semantic_validation": "server_required"})
		}}
		cmd.Flags().StringVar(&destination, "destination", "", "New author or sealed package directory")
		group.AddCommand(cmd)
	}
	a.packageBindingsCommand(group)
	a.packageOperationCommands(group)
	a.packagePlanningCommands(group)
	a.packageImportCommands(group)
	a.packageExportCommands(group)
}

func packageHTTPCommand(path string) bool {
	switch path {
	case "package plan", "package import", "package export agent", "package export network", "package status", "package resume", "package cancel":
		return true
	}
	return false
}
