package cli

import (
	"context"
	"strconv"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/spf13/cobra"
)

func (a *App) packageExportCommands(group *cobra.Command) {
	export := &cobra.Command{Use: "export", Short: "Export a complete portable native snapshot"}
	for _, kind := range []string{"agent", "network"} {
		var destination, source, environment, snapshot, knowledge, name, version, packageVersion, packageSchema string
		var deadline time.Duration
		command := &cobra.Command{Use: kind + " NAME_OR_UUID", Short: "Capture an exact " + kind + " source and all portable dependencies", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
			if err := packageFlags(cmd, "yes", "validate-body", "validate-parameters", "schema-sha256"); err != nil {
				return err
			}
			if a.DryRun || deadline <= 0 {
				return output.New(2, "Export requires a positive deadline and does not support --dry-run")
			}
			legacy := cmd.Flags().Changed("source") || cmd.Flags().Changed("snapshot-id")
			if cmd.Flags().Changed("env") && legacy {
				return output.New(2, "Use --env or a legacy --source/--snapshot-id selector, not both")
			}
			if legacy {
				if (source == "") == (snapshot == "") {
					return output.New(2, "Use exactly one of --source or --snapshot-id")
				}
				if packageVersion == "" {
					packageVersion = version
				}
			} else {
				source = environment
				if source == "release" && version == "" {
					return output.New(2, "Release export requires --version; example: woobe package export "+kind+" UUID --env release --version v1.0.20261007.01")
				}
				if source != "release" && version != "" {
					return output.New(2, "--version selects a release; use --env release or --package-version for package metadata")
				}
			}
			switch source {
			case "", "draft", "staging", "release", "production":
			default:
				return output.New(2, "Invalid Package export source")
			}
			if knowledge != "portable" && knowledge != "binding" {
				return output.New(2, "Knowledge mode must be portable or binding")
			}
			var absolute string
			var err error
			if destination != "" {
				absolute, err = packageDestination(destination)
				if err != nil {
					return err
				}
			}
			ctx, cancel := context.WithTimeout(cmd.Context(), deadline)
			defer cancel()
			client, err := a.packageClient(ctx, "export")
			if err != nil {
				return err
			}
			targetKind := "Agent"
			if kind == "network" {
				targetKind = "Network"
			}
			targetID, err := a.packageTarget(ctx, client, kind, args[0])
			if err != nil {
				return err
			}
			request := packageapi.ExportRequest{PackageSchemaVersion: packageSchema, Kind: targetKind, TargetID: targetID, Knowledge: knowledge, Name: name, Version: packageVersion}
			if !legacy && source == "release" {
				request.ReleaseVersion = version
			}
			if source != "" {
				request.Source = &source
			} else {
				request.SnapshotID = &snapshot
			}
			var schema map[string]any
			if a.ValidateBody || a.ValidateParameters {
				schema, err = a.loadServerSchema(ctx)
				if err != nil {
					return err
				}
				if err = a.validatePackageRequest(schema, "POST", "/export", map[string]string{"project_id": client.ProjectID}, nil, request); err != nil {
					return err
				}
			}
			receipt, err := client.Export(ctx, request)
			if err != nil {
				return err
			}
			if schema != nil {
				if err = a.validatePackageRequest(schema, "GET", "/exports/{export_id}/artifact", map[string]string{"project_id": client.ProjectID, "export_id": receipt.ExportID}, nil, nil); err != nil {
					return err
				}
			}
			bundle, err := client.Download(ctx, receipt)
			if err != nil {
				return packageError(err)
			}
			defer bundle.Close()
			metadata := packagefmt.Object(bundle.Graph.Manifest["metadata"])
			if absolute == "" {
				absolute, err = packageDestination(packageSlug(packagefmt.Text(metadata["name"])))
				if err != nil {
					return err
				}
			}
			if err = ctx.Err(); err != nil {
				return output.New(8, "Package export deadline expired before publication")
			}
			if err = bundle.Publish(absolute); err != nil {
				return packageError(err)
			}
			return a.emit(map[string]any{"package_schema_version": receipt.PackageSchemaVersion, "destination": absolute, "export_id": receipt.ExportID, "artifact_digest": receipt.ArtifactDigest, "transport_digest": receipt.TransportDigest, "inventory": receipt.Inventory, "closure_complete": receipt.ClosureComplete, "self_contained": receipt.SelfContained, "knowledge": receipt.Knowledge, "name": metadata["name"], "version": metadata["version"], "source": receipt.Source, "integrity": "verified", "next_command": "woobe package validate " + strconv.Quote(absolute) + " --locked"})
		}}
		command.Flags().StringVar(&packageSchema, "package-schema", "1.0", "Package contract: 1.0 (legacy) or 2.0 (remote configuration declarations)")
		command.Flags().StringVar(&destination, "destination", "", "New directory; defaults to ./normalized-resource-name")
		command.Flags().StringVar(&environment, "env", "draft", "Environment: draft (default), staging, release or production; release requires --version")
		command.Flags().StringVar(&source, "source", "", "Legacy environment selector; --version remains package metadata with --source")
		command.Flags().StringVar(&snapshot, "snapshot-id", "", "Exact native snapshot belonging to the target")
		command.Flags().StringVar(&knowledge, "knowledge", "portable", "Knowledge portability: portable or binding")
		command.Flags().StringVar(&name, "name", "", "Portable package name")
		command.Flags().StringVar(&version, "version", "", "Release version with --env release; legacy package version with --source/--snapshot-id")
		command.Flags().StringVar(&packageVersion, "package-version", "", "Optional package metadata version; otherwise derived from the captured source")
		command.Flags().DurationVar(&deadline, "deadline", 5*time.Minute, "Total capture/download deadline")
		export.AddCommand(command)
	}
	group.AddCommand(export)
}
