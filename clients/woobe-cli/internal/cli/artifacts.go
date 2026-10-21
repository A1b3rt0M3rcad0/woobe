package cli

import (
	"bytes"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"mime"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	sdk "github.com/A1b3rt0M3rcad0/woobe-sdk-go"
	"github.com/spf13/cobra"
)

func artifactCLIError(err error) error {
	if err == nil {
		return nil
	}
	var authentication *sdk.AuthenticationError
	if errors.As(err, &authentication) {
		return &output.Error{Code: 3, Message: "Artifact Runtime Key authentication failed", Status: authentication.StatusCode}
	}
	var request *sdk.RequestError
	if errors.As(err, &request) {
		return runtimeError(err)
	}
	var connection *sdk.ConnectionError
	if errors.As(err, &connection) {
		return output.New(8, "Artifact transport failed; reconcile mutation or upload status before retrying")
	}
	var protocol *sdk.ProtocolError
	if errors.As(err, &protocol) {
		return output.New(7, "Artifact response violated the public contract")
	}
	return output.Normalize(err)
}

func artifactBeginError(err error, checkpointPath string) error {
	var authentication *sdk.AuthenticationError
	if errors.As(err, &authentication) {
		return artifactCheckpointError(err, checkpointPath)
	}
	var request *sdk.RequestError
	if errors.As(err, &request) && !request.Retryable() {
		return artifactCheckpointError(err, checkpointPath)
	}
	var protocol *sdk.ProtocolError
	if errors.As(err, &protocol) {
		return artifactCheckpointError(err, checkpointPath)
	}
	return output.New(8, "upload start outcome is uncertain; reconcile with artifacts upload resume --checkpoint "+checkpointPath)
}

func artifactCheckpointError(err error, checkpointPath string) error {
	normalized := artifactCLIError(err)
	var cliError *output.Error
	if errors.As(normalized, &cliError) {
		copy := *cliError
		copy.Message += "; private checkpoint preserved at " + checkpointPath + " for later resume"
		return &copy
	}
	return normalized
}

func artifactMutationError(err error, operationID string) error {
	var request *sdk.RequestError
	var connection *sdk.ConnectionError
	if !errors.As(err, &connection) && (!errors.As(err, &request) || !request.Retryable()) {
		return artifactCLIError(err)
	}
	normalized := artifactCLIError(err)
	var cliError *output.Error
	if errors.As(normalized, &cliError) {
		copy := *cliError
		copy.Message += "; for reconciliation, repeat the exact request with --operation-id " + operationID
		return &copy
	}
	return normalized
}

func (a *App) artifactClients(cmd *cobra.Command, environment string) (context.Context, context.CancelFunc, *sdk.Client, *sdk.ArtifactsClient, error) {
	v, err := a.resolve()
	if err != nil {
		return nil, nil, nil, nil, err
	}
	if v.Project == "" {
		return nil, nil, nil, nil, output.New(2, "explicit --project or a project-bound context is required")
	}
	key := os.Getenv("WOOBE_RUNTIME_KEY")
	if v.RuntimeCredential != "" {
		key, err = a.store().Get(v.RuntimeCredential)
		if err != nil {
			return nil, nil, nil, nil, output.New(3, "cannot read the attached Runtime credential")
		}
	}
	if key == "" {
		return nil, nil, nil, nil, output.New(3, "attach an explicit Runtime credential with context runtime-credential or set WOOBE_RUNTIME_KEY")
	}
	ctx, cancel := context.WithTimeout(cmd.Context(), a.Timeout)
	client, err := sdk.New(sdk.WithBaseURL(v.APIURL))
	if err != nil {
		cancel()
		return nil, nil, nil, nil, artifactCLIError(err)
	}
	artifacts, err := client.Artifacts(v.Project, key, sdk.ArtifactEnvironment(environment))
	if err != nil {
		client.CloseIdleConnections()
		cancel()
		return nil, nil, nil, nil, artifactCLIError(err)
	}
	return ctx, cancel, client, artifacts, nil
}

func newArtifactOperationID() (string, error) {
	var random [16]byte
	if _, err := rand.Read(random[:]); err != nil {
		return "", output.New(7, "could not create an Artifact operation ID")
	}
	return "artifact-" + hex.EncodeToString(random[:]), nil
}

func artifactCheckpointPath(configPath, operationID string) string {
	return filepath.Join(filepath.Dir(configPath), "artifact-uploads", operationID+".json")
}

func (a *App) artifactCommands() {
	root := &cobra.Command{Use: "artifacts", Short: "Operate scoped Artifact Workspaces and immutable document revisions"}
	var environment string
	root.PersistentFlags().StringVar(&environment, "environment", "production", "Artifact Environment: draft, staging or production")
	a.Root.AddCommand(root)

	workspace := &cobra.Command{Use: "workspace", Short: "Manage explicitly scoped Artifact Workspaces"}
	root.AddCommand(workspace)
	var limit int
	var cursor, namespace, externalKey, workspaceName string
	workspaceList := &cobra.Command{Use: "list", Args: cobra.NoArgs, Short: "List authorized Artifact Workspaces", RunE: func(cmd *cobra.Command, _ []string) error {
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		page, err := artifacts.ListWorkspaces(ctx, limit, cursor, namespace)
		if err != nil {
			return artifactCLIError(err)
		}
		return a.emit(page)
	}}
	workspaceList.Flags().IntVar(&limit, "limit", 50, "Maximum page size")
	workspaceList.Flags().StringVar(&cursor, "cursor", "", "Opaque next-page cursor")
	workspaceList.Flags().StringVar(&namespace, "external-namespace", "", "Filter by external namespace")
	workspace.AddCommand(workspaceList)
	workspaceCreate := &cobra.Command{Use: "create", Args: cobra.NoArgs, Short: "Provision an Artifact Workspace", RunE: func(cmd *cobra.Command, _ []string) error {
		if namespace == "" || externalKey == "" || workspaceName == "" {
			return output.New(2, "--external-namespace, --external-key and --name are required")
		}
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		result, err := artifacts.CreateWorkspace(ctx, sdk.CreateArtifactWorkspaceRequest{ExternalNamespace: namespace, ExternalKey: externalKey, Name: workspaceName})
		if err != nil {
			return artifactCLIError(err)
		}
		return a.emit(result)
	}}
	workspaceCreate.Flags().StringVar(&namespace, "external-namespace", "", "External owner namespace")
	workspaceCreate.Flags().StringVar(&externalKey, "external-key", "", "External Workspace identity")
	workspaceCreate.Flags().StringVar(&workspaceName, "name", "", "Display name")
	workspace.AddCommand(workspaceCreate)
	workspaceResolve := &cobra.Command{Use: "resolve NAMESPACE EXTERNAL_KEY", Args: cobra.ExactArgs(2), Short: "Resolve an externally keyed Artifact Workspace", RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		result, err := artifacts.ResolveWorkspace(ctx, args[0], args[1])
		if err != nil {
			return artifactCLIError(err)
		}
		return a.emit(result)
	}}
	workspace.AddCommand(workspaceResolve)
	workspaceGet := &cobra.Command{Use: "get WORKSPACE_ID", Args: cobra.ExactArgs(1), Short: "Inspect an Artifact Workspace", RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		result, err := artifacts.GetWorkspace(ctx, args[0])
		if err != nil {
			return artifactCLIError(err)
		}
		return a.emit(result)
	}}
	workspace.AddCommand(workspaceGet)
	var expectedVersion int64
	var workspaceStatus, updateName string
	workspaceUpdate := &cobra.Command{Use: "update WORKSPACE_ID", Args: cobra.ExactArgs(1), Short: "Update Workspace metadata using compare-and-swap", RunE: func(cmd *cobra.Command, args []string) error {
		if expectedVersion < 1 || updateName == "" && workspaceStatus == "" {
			return output.New(2, "--expected-version and at least one of --name or --status are required")
		}
		if !a.Yes && !a.DryRun {
			return output.New(2, "Workspace mutation requires --yes")
		}
		if a.DryRun {
			return a.emit(map[string]any{"workspace_id": args[0], "expected_version": expectedVersion, "executed": false})
		}
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		request := sdk.UpdateArtifactWorkspaceRequest{ExpectedVersion: expectedVersion}
		if cmd.Flags().Changed("name") {
			request.Name = &updateName
		}
		if cmd.Flags().Changed("status") {
			request.Status = &workspaceStatus
		}
		result, err := artifacts.UpdateWorkspace(ctx, args[0], request)
		if err != nil {
			return artifactCLIError(err)
		}
		return a.emit(result)
	}}
	workspaceUpdate.Flags().Int64Var(&expectedVersion, "expected-version", 0, "Expected Workspace version")
	workspaceUpdate.Flags().StringVar(&updateName, "name", "", "New display name")
	workspaceUpdate.Flags().StringVar(&workspaceStatus, "status", "", "New lifecycle status")
	workspace.AddCommand(workspaceUpdate)

	var directory string
	var artifactCursor string
	var artifactLimit int
	list := &cobra.Command{Use: "list WORKSPACE_ID", Args: cobra.ExactArgs(1), Short: "List a page of Artifacts", RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		page, err := artifacts.ListArtifacts(ctx, args[0], directory, artifactLimit, artifactCursor)
		if err != nil {
			return artifactCLIError(err)
		}
		return a.emit(page)
	}}
	list.Flags().StringVar(&directory, "directory", "", "Directory path to list")
	list.Flags().IntVar(&artifactLimit, "limit", 50, "Maximum page size")
	list.Flags().StringVar(&artifactCursor, "cursor", "", "Opaque next-page cursor")
	root.AddCommand(list)
	get := &cobra.Command{Use: "get WORKSPACE_ID ARTIFACT_ID", Args: cobra.ExactArgs(2), Short: "Inspect an Artifact and its current revision", RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		result, err := artifacts.GetArtifact(ctx, args[0], args[1])
		if err != nil {
			return artifactCLIError(err)
		}
		return a.emit(result)
	}}
	root.AddCommand(get)
	revision := &cobra.Command{Use: "revision WORKSPACE_ID ARTIFACT_ID REVISION_ID", Args: cobra.ExactArgs(3), Short: "Inspect immutable revision metadata", RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		result, err := artifacts.GetRevision(ctx, args[0], args[1], args[2])
		if err != nil {
			return artifactCLIError(err)
		}
		return a.emit(result)
	}}
	root.AddCommand(revision)
	var searchMode, searchCursor string
	var searchLimit int
	search := &cobra.Command{Use: "search WORKSPACE_ID QUERY", Args: cobra.ExactArgs(2), Short: "Search documents and return exact SourceRefs", RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		page, err := artifacts.Search(ctx, args[0], args[1], searchMode, searchCursor, searchLimit)
		if err != nil {
			return artifactCLIError(err)
		}
		return a.emit(page)
	}}
	search.Flags().StringVar(&searchMode, "mode", "text", "Search mode: text or hybrid")
	search.Flags().StringVar(&searchCursor, "cursor", "", "Opaque next-page cursor")
	search.Flags().IntVar(&searchLimit, "limit", 50, "Maximum page size")
	root.AddCommand(search)
	var operationID, profileID string
	var profileRevision *int64
	var profileRev int64
	process := &cobra.Command{Use: "process WORKSPACE_ID ARTIFACT_ID REVISION_ID", Args: cobra.ExactArgs(3), Short: "Request durable processing for an exact revision", RunE: func(cmd *cobra.Command, args []string) error {
		if !a.Yes && !a.DryRun {
			return output.New(2, "document processing requires --yes")
		}
		opID := operationID
		if opID == "" {
			var err error
			opID, err = newArtifactOperationID()
			if err != nil {
				return err
			}
		}
		if a.DryRun {
			return a.emit(map[string]any{"workspace_id": args[0], "artifact_id": args[1], "revision_id": args[2], "operation_id": opID, "executed": false})
		}
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		var profileIDValue *string
		if profileID != "" {
			profileIDValue = &profileID
		}
		result, err := artifacts.RequestProcessing(ctx, args[0], args[1], sdk.ArtifactProcessingRequest{OperationID: opID, RevisionID: args[2], ProfileID: profileIDValue, ProfileRevision: profileRevision})
		if err != nil {
			return artifactMutationError(err, opID)
		}
		return a.emit(result)
	}}
	process.Flags().StringVar(&operationID, "operation-id", "", "Stable operation ID for explicit reconciliation")
	process.Flags().StringVar(&profileID, "profile-id", "", "Pinned processing profile ID")
	process.Flags().Int64Var(&profileRev, "profile-revision", 0, "Pinned processing profile revision")
	process.Flags().Lookup("profile-revision").NoOptDefVal = "0"
	process.PreRunE = func(_ *cobra.Command, _ []string) error {
		if profileID != "" {
			profileRevision = &profileRev
		} else if profileRev != 0 {
			return output.New(2, "--profile-revision requires --profile-id")
		}
		return nil
	}
	root.AddCommand(process)
	var parentID, treeCursor string
	var treeLimit int
	tree := &cobra.Command{Use: "tree WORKSPACE_ID INDEX_ID", Args: cobra.ExactArgs(2), Short: "List a structural document-index page", RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		page, err := artifacts.ListDocumentNodes(ctx, args[0], args[1], parentID, treeCursor, treeLimit)
		if err != nil {
			return artifactCLIError(err)
		}
		return a.emit(page)
	}}
	tree.Flags().StringVar(&parentID, "parent", "", "Parent node ID (omit for roots)")
	tree.Flags().StringVar(&treeCursor, "cursor", "", "Opaque next-page cursor")
	tree.Flags().IntVar(&treeLimit, "limit", 50, "Maximum page size")
	root.AddCommand(tree)
	var readOffset int64
	var readMaxChars int
	readNode := &cobra.Command{Use: "read-node WORKSPACE_ID INDEX_ID NODE_ID", Args: cobra.ExactArgs(3), Short: "Read bounded text owned by a structural node", RunE: func(cmd *cobra.Command, args []string) error {
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		result, err := artifacts.ReadDocumentNode(ctx, args[0], args[1], args[2], readOffset, readMaxChars)
		if err != nil {
			return artifactCLIError(err)
		}
		return a.emit(result)
	}}
	readNode.Flags().Int64Var(&readOffset, "offset", 0, "Character offset")
	readNode.Flags().IntVar(&readMaxChars, "max-chars", 8192, "Maximum Unicode characters (1..65536)")
	root.AddCommand(readNode)
	var sourceFile string
	var sourceOffset int64
	var sourceMaxChars int
	readSource := &cobra.Command{Use: "read-source WORKSPACE_ID", Args: cobra.ExactArgs(1), Short: "Read bounded text using an exact immutable SourceRef", Long: "Reads a JSON SourceRef created by search or a Runtime output manifest. The source file is bounded, parsed strictly, and never sent to the Control Plane.", RunE: func(cmd *cobra.Command, args []string) error {
		if sourceFile == "" {
			return output.New(2, "--source-file is required")
		}
		file, err := os.Open(sourceFile)
		if err != nil {
			return output.New(2, "cannot open SourceRef JSON file")
		}
		defer file.Close()
		info, err := file.Stat()
		if err != nil || !info.Mode().IsRegular() || info.Size() > 64*1024 {
			return output.New(2, "SourceRef must be a regular file no larger than 64 KiB")
		}
		var source sdk.ArtifactSource
		decoder := json.NewDecoder(io.LimitReader(file, 64*1024+1))
		decoder.DisallowUnknownFields()
		if err = decoder.Decode(&source); err != nil || decoder.Decode(new(any)) != io.EOF {
			return output.New(2, "SourceRef file is not one valid JSON object")
		}
		if source.ArtifactID == "" || source.RevisionID == "" || len(source.SourceSHA256) != 64 || strings.ToLower(source.SourceSHA256) != source.SourceSHA256 {
			return output.New(2, "SourceRef must include exact Artifact and revision IDs with a lowercase SHA-256")
		}
		if _, err = hex.DecodeString(source.SourceSHA256); err != nil {
			return output.New(2, "SourceRef must include exact Artifact and revision IDs with a lowercase SHA-256")
		}
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		result, err := artifacts.ReadSource(ctx, args[0], sdk.ArtifactSourceReadRequest{Source: source, Offset: sourceOffset, MaxChars: sourceMaxChars})
		if err != nil {
			return artifactCLIError(err)
		}
		return a.emit(result)
	}}
	readSource.Flags().StringVar(&sourceFile, "source-file", "", "JSON file containing one exact SourceRef")
	readSource.Flags().Int64Var(&sourceOffset, "offset", 0, "Character offset within the cited source")
	readSource.Flags().IntVar(&sourceMaxChars, "max-chars", 8192, "Maximum Unicode characters (0..65536)")
	root.AddCommand(readSource)

	a.artifactUploadCommands(root, &environment)
	a.artifactDownloadCommand(root, &environment)
	var moveOperation string
	var artifactPath string
	var artifactVersion int64
	move := &cobra.Command{Use: "move WORKSPACE_ID ARTIFACT_ID", Args: cobra.ExactArgs(2), Short: "Move or rename an Artifact using compare-and-swap", RunE: func(cmd *cobra.Command, args []string) error {
		if !a.Yes && !a.DryRun {
			return output.New(2, "Artifact move requires --yes")
		}
		if artifactPath == "" || artifactVersion < 1 {
			return output.New(2, "--path and --expected-version are required")
		}
		opID := moveOperation
		if opID == "" {
			var err error
			opID, err = newArtifactOperationID()
			if err != nil {
				return err
			}
		}
		if a.DryRun {
			return a.emit(map[string]any{"workspace_id": args[0], "artifact_id": args[1], "path": artifactPath, "expected_version": artifactVersion, "operation_id": opID, "executed": false})
		}
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		result, err := artifacts.MoveArtifact(ctx, args[0], args[1], opID, artifactPath, artifactVersion)
		if err != nil {
			return artifactMutationError(err, opID)
		}
		return a.emit(result)
	}}
	move.Flags().StringVar(&moveOperation, "operation-id", "", "Stable operation ID")
	move.Flags().StringVar(&artifactPath, "path", "", "New relative Workspace path")
	move.Flags().Int64Var(&artifactVersion, "expected-version", 0, "Expected Artifact version")
	root.AddCommand(move)
	var deleteOperation string
	var deleteVersion int64
	remove := &cobra.Command{Use: "delete WORKSPACE_ID ARTIFACT_ID", Args: cobra.ExactArgs(2), Short: "Delete an Artifact from the current catalog", Long: "Delete requires --yes and an expected version. The mutation preserves immutable revision history and its operation ID is reconciled by the service.", RunE: func(cmd *cobra.Command, args []string) error {
		if !a.Yes && !a.DryRun {
			return output.New(2, "Artifact deletion requires --yes")
		}
		if deleteVersion < 1 {
			return output.New(2, "--expected-version is required")
		}
		opID := deleteOperation
		if opID == "" {
			var err error
			opID, err = newArtifactOperationID()
			if err != nil {
				return err
			}
		}
		if a.DryRun {
			return a.emit(map[string]any{"workspace_id": args[0], "artifact_id": args[1], "expected_version": deleteVersion, "operation_id": opID, "executed": false})
		}
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		result, err := artifacts.DeleteArtifact(ctx, args[0], args[1], opID, deleteVersion)
		if err != nil {
			return artifactMutationError(err, opID)
		}
		return a.emit(result)
	}}
	remove.Flags().StringVar(&deleteOperation, "operation-id", "", "Stable operation ID")
	remove.Flags().Int64Var(&deleteVersion, "expected-version", 0, "Expected Artifact version")
	root.AddCommand(remove)
}

func (a *App) artifactUploadCommands(root *cobra.Command, environment *string) {
	var destination, contentType, checkpointPath, operationID, artifactID, expectedRevision string
	upload := &cobra.Command{Use: "upload WORKSPACE_ID", Args: cobra.ExactArgs(1), Short: "Stream a file into a Workspace with a private resumable checkpoint", Long: "Reads a regular local file in bounded parts. The private checkpoint stores only scope, source identity, operation and acknowledged offset; it never stores Runtime credentials. If an acknowledgement is uncertain, resume reconciles the remote offset before continuing.", RunE: func(cmd *cobra.Command, args []string) error {
		if a.File == "" || a.File == "-" || destination == "" {
			return output.New(2, "upload requires a local --file and remote --path")
		}
		if (artifactID == "") != (expectedRevision == "") {
			return output.New(2, "updating an existing Artifact requires both --artifact-id and --expected-revision")
		}
		if artifactID != "" && !a.Yes && !a.DryRun {
			return output.New(2, "replacing an Artifact revision requires --yes")
		}
		sourcePath, err := filepath.Abs(a.File)
		if err != nil {
			return output.New(2, "invalid upload source path")
		}
		file, err := os.Open(sourcePath)
		if err != nil {
			return output.New(2, "cannot open upload source file")
		}
		defer file.Close()
		size, digest, err := artifactSourceDigest(file)
		if err != nil {
			return err
		}
		if contentType == "" {
			contentType = mime.TypeByExtension(filepath.Ext(sourcePath))
			if contentType == "" {
				contentType = "application/octet-stream"
			}
		}
		opID := operationID
		if opID == "" {
			opID, err = newArtifactOperationID()
			if err != nil {
				return err
			}
		}
		if a.DryRun {
			return a.emit(map[string]any{"workspace_id": args[0], "artifact_id": artifactID, "expected_revision": expectedRevision, "source_path": sourcePath, "path": destination, "size_bytes": size, "sha256": digest, "content_type": contentType, "operation_id": opID, "executed": false})
		}
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, *environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		capabilities, err := artifacts.Capabilities(ctx)
		if err != nil {
			return artifactCLIError(err)
		}
		if size > capabilities.MaxUploadBytes || capabilities.MaxUploadPartBytes <= 0 || capabilities.MaxUploadParts <= 0 {
			return output.New(2, "upload exceeds or lacks the advertised server limits")
		}
		parts := int64(0)
		if size > 0 {
			parts = 1 + (size-1)/capabilities.MaxUploadPartBytes
		}
		if parts > int64(capabilities.MaxUploadParts) {
			return output.New(2, "upload exceeds the advertised server part limit")
		}
		if checkpointPath == "" {
			checkpointPath = artifactCheckpointPath(a.ConfigPath, opID)
		}
		store, err := packagecheckpoint.Open(checkpointPath)
		if err != nil {
			return output.New(2, "cannot securely open private upload checkpoint")
		}
		defer store.Close()
		if _, readErr := store.ReadDocument(); readErr == nil {
			return output.New(2, "checkpoint already exists; use artifacts upload resume")
		} else if !os.IsNotExist(readErr) {
			return output.New(2, "checkpoint path is not a safe private file")
		}
		v, err := a.resolve()
		if err != nil {
			return err
		}
		cp := artifactUploadCheckpoint{Format: "woobe-artifact-upload-checkpoint", SchemaVersion: "1", APIOrigin: strings.TrimRight(v.APIURL, "/"), ProjectID: v.Project, Environment: *environment, WorkspaceID: args[0], ArtifactID: artifactID, ExpectedRevision: expectedRevision, OperationID: opID, SourcePath: sourcePath, ArtifactPath: destination, ContentType: contentType, SizeBytes: size, SHA256: digest, State: "begin_unknown", UpdatedAt: time.Now().UTC()}
		if err = saveArtifactUploadCheckpoint(store, &cp); err != nil {
			return err
		}
		request := sdk.BeginArtifactUploadRequest{OperationID: opID, Path: destination, SizeBytes: size, SHA256: digest, ContentType: contentType}
		if artifactID != "" {
			request.ArtifactID, request.ExpectedRevision = &artifactID, &expectedRevision
		}
		upload, err := artifacts.BeginUpload(ctx, args[0], request)
		if err != nil {
			return artifactBeginError(err, checkpointPath)
		}
		if upload == nil || upload.ID == "" || upload.WorkspaceID != args[0] || upload.OperationID != opID || upload.ExpectedSize != size || upload.Offset < 0 || upload.Offset > size {
			return output.New(8, "upload start response could not be reconciled; resume with --checkpoint "+checkpointPath)
		}
		cp.UploadID, cp.Offset, cp.State = upload.ID, upload.Offset, "uploading"
		if err = saveArtifactUploadCheckpoint(store, &cp); err != nil {
			return err
		}
		result, err := a.sendArtifactUpload(ctx, artifacts, store, &cp, file, capabilities.MaxUploadPartBytes, capabilities.MaxUploadParts)
		if err != nil {
			return output.New(8, "upload requires status reconciliation; resume with --checkpoint "+checkpointPath)
		}
		return a.emit(map[string]any{"upload": result, "checkpoint": checkpointPath, "source": map[string]any{"size_bytes": size, "sha256": digest}, "executed": true})
	}}
	upload.Flags().StringVar(&destination, "path", "", "Relative destination path in the Workspace")
	upload.Flags().StringVar(&artifactID, "artifact-id", "", "Existing Artifact to replace using exact revision compare-and-swap")
	upload.Flags().StringVar(&expectedRevision, "expected-revision", "", "Required immutable revision ID when replacing an Artifact")
	upload.Flags().StringVar(&contentType, "content-type", "", "Media type; inferred from extension when omitted")
	upload.Flags().StringVar(&checkpointPath, "checkpoint", "", "Private resumable checkpoint (default: CLI config state)")
	upload.Flags().StringVar(&operationID, "operation-id", "", "Stable operation ID for reconciliation")
	root.AddCommand(upload)
	var resumeCheckpoint string
	resume := &cobra.Command{Use: "resume", Args: cobra.NoArgs, Short: "Reconcile and resume one acknowledged Artifact upload", Long: "Reads a private checkpoint and the remote upload status. It seeks the original local source to the server's acknowledged offset; it never replays an uncertain part blindly.", RunE: func(cmd *cobra.Command, _ []string) error {
		if resumeCheckpoint == "" {
			return output.New(2, "--checkpoint is required")
		}
		store, cp, err := loadArtifactUploadCheckpoint(resumeCheckpoint)
		if err != nil {
			return err
		}
		defer store.Close()
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, cp.Environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		v, err := a.resolve()
		if err != nil {
			return err
		}
		if v.Project != cp.ProjectID || strings.TrimRight(v.APIURL, "/") != cp.APIOrigin {
			return output.New(3, "checkpoint belongs to a different Project or API origin")
		}
		if cp.State == "begin_unknown" {
			request := sdk.BeginArtifactUploadRequest{OperationID: cp.OperationID, Path: cp.ArtifactPath, SizeBytes: cp.SizeBytes, SHA256: cp.SHA256, ContentType: cp.ContentType}
			if cp.ArtifactID != "" {
				request.ArtifactID, request.ExpectedRevision = &cp.ArtifactID, &cp.ExpectedRevision
			}
			started, beginErr := artifacts.BeginUpload(ctx, cp.WorkspaceID, request)
			if beginErr != nil {
				return artifactBeginError(beginErr, resumeCheckpoint)
			}
			if started == nil || started.ID == "" || started.WorkspaceID != cp.WorkspaceID || started.OperationID != cp.OperationID || started.ExpectedSize != cp.SizeBytes || started.Offset < 0 || started.Offset > cp.SizeBytes {
				return output.New(8, "upload start response could not be reconciled; retry resume with --checkpoint "+resumeCheckpoint)
			}
			cp.UploadID, cp.Offset, cp.State = started.ID, started.Offset, "uploading"
			if err = saveArtifactUploadCheckpoint(store, &cp); err != nil {
				return err
			}
		}
		status, err := artifacts.UploadStatus(ctx, cp.WorkspaceID, cp.UploadID)
		if err != nil {
			return artifactCLIError(err)
		}
		if status.Receipt != nil || status.Status == "completed" {
			cp.State = "completed"
			_ = saveArtifactUploadCheckpoint(store, &cp)
			return a.emit(map[string]any{"upload": status, "checkpoint": resumeCheckpoint, "reconciled": true})
		}
		if status.Status != "uploading" || status.Offset < 0 || status.Offset > cp.SizeBytes {
			return output.New(6, "remote upload is not resumable; inspect its status before taking another action")
		}
		file, err := os.Open(cp.SourcePath)
		if err != nil {
			return output.New(2, "cannot reopen upload source file")
		}
		defer file.Close()
		size, digest, err := artifactSourceDigest(file)
		if err != nil {
			return err
		}
		if size != cp.SizeBytes || digest != cp.SHA256 {
			return output.New(2, "local upload source changed since checkpoint creation")
		}
		capabilities, err := artifacts.Capabilities(ctx)
		if err != nil {
			return artifactCLIError(err)
		}
		if _, err = file.Seek(status.Offset, io.SeekStart); err != nil {
			return output.New(2, "cannot seek to acknowledged upload offset")
		}
		cp.Offset, cp.State = status.Offset, "uploading"
		if err = saveArtifactUploadCheckpoint(store, &cp); err != nil {
			return err
		}
		result, err := a.sendArtifactUpload(ctx, artifacts, store, &cp, file, capabilities.MaxUploadPartBytes, capabilities.MaxUploadParts)
		if err != nil {
			return output.New(8, "upload remains uncertain; resume again with --checkpoint "+resumeCheckpoint)
		}
		return a.emit(map[string]any{"upload": result, "checkpoint": resumeCheckpoint, "reconciled": true})
	}}
	resume.Flags().StringVar(&resumeCheckpoint, "checkpoint", "", "Private upload checkpoint")
	upload.AddCommand(resume)
}

func (a *App) sendArtifactUpload(ctx context.Context, artifacts *sdk.ArtifactsClient, store *packagecheckpoint.Store, cp *artifactUploadCheckpoint, source io.Reader, partLimit int64, maxParts int) (*sdk.ArtifactUpload, error) {
	if partLimit <= 0 || partLimit > 8*1024*1024 || maxParts <= 0 {
		return nil, output.New(2, "invalid advertised upload part limits")
	}
	buffer := make([]byte, partLimit)
	parts := 0
	for cp.Offset < cp.SizeBytes {
		want := int64(len(buffer))
		if remaining := cp.SizeBytes - cp.Offset; remaining < want {
			want = remaining
		}
		n, err := io.ReadFull(source, buffer[:int(want)])
		if err != nil {
			return nil, output.New(2, "upload source ended before the declared size")
		}
		parts++
		if parts > maxParts {
			return nil, output.New(2, "upload source exceeds advertised part count")
		}
		expected := cp.Offset + int64(n)
		status, err := artifacts.UploadPart(ctx, cp.WorkspaceID, cp.UploadID, cp.Offset, bytes.NewReader(buffer[:n]), int64(n))
		if err != nil {
			cp.State = "outcome_unknown"
			_ = saveArtifactUploadCheckpoint(store, cp)
			return nil, err
		}
		if status.Offset != expected {
			cp.State = "outcome_unknown"
			_ = saveArtifactUploadCheckpoint(store, cp)
			return nil, output.New(6, "server upload offset differs from acknowledged part")
		}
		cp.Offset, cp.State = status.Offset, "uploading"
		if err = saveArtifactUploadCheckpoint(store, cp); err != nil {
			return nil, err
		}
	}
	if extra, ok := source.(interface{ Read([]byte) (int, error) }); ok && cp.Offset == cp.SizeBytes {
		var probe [1]byte
		if n, _ := extra.Read(probe[:]); n != 0 {
			return nil, output.New(2, "upload source exceeds the declared size")
		}
	}
	if file, ok := source.(*os.File); ok {
		size, digest, err := artifactSourceDigest(file)
		if err != nil {
			return nil, err
		}
		if size != cp.SizeBytes || digest != cp.SHA256 {
			return nil, output.New(2, "upload source changed while streaming; the staged upload was not finalized")
		}
	}
	cp.State = "outcome_unknown"
	if err := saveArtifactUploadCheckpoint(store, cp); err != nil {
		return nil, err
	}
	result, err := artifacts.FinalizeUpload(ctx, cp.WorkspaceID, cp.UploadID)
	if err != nil {
		_ = saveArtifactUploadCheckpoint(store, cp)
		return nil, err
	}
	cp.State = "completed"
	if err = saveArtifactUploadCheckpoint(store, cp); err != nil {
		return result, err
	}
	return result, nil
}

func (a *App) artifactDownloadCommand(root *cobra.Command, environment *string) {
	var destination string
	command := &cobra.Command{Use: "download WORKSPACE_ID ARTIFACT_ID REVISION_ID", Args: cobra.ExactArgs(3), Short: "Stream an exact Artifact revision to an atomically published local file", RunE: func(cmd *cobra.Command, args []string) error {
		if destination == "" {
			return output.New(2, "--output-file is required")
		}
		absolute, err := filepath.Abs(destination)
		if err != nil {
			return output.New(2, "invalid destination path")
		}
		if _, err = os.Stat(absolute); err == nil && !a.Yes {
			return output.New(2, "destination exists; use --yes to replace it")
		} else if err != nil && !os.IsNotExist(err) {
			return output.New(2, "destination is not writable")
		}
		if a.DryRun {
			return a.emit(map[string]any{"workspace_id": args[0], "artifact_id": args[1], "revision_id": args[2], "destination": absolute, "executed": false})
		}
		ctx, cancel, client, artifacts, err := a.artifactClients(cmd, *environment)
		if err != nil {
			return err
		}
		defer cancel()
		defer client.CloseIdleConnections()
		revision, err := artifacts.GetRevision(ctx, args[0], args[1], args[2])
		if err != nil {
			return artifactCLIError(err)
		}
		download, err := artifacts.Download(ctx, args[0], args[1], args[2], "")
		if err != nil {
			return artifactCLIError(err)
		}
		defer download.Body.Close()
		if download.StatusCode != http.StatusOK {
			return output.New(7, "Artifact download returned an unexpected status")
		}
		if revision.SizeBytes < 0 || revision.SizeBytes == 1<<63-1 {
			return output.New(7, "Artifact revision advertised an unsupported size")
		}
		temporary, err := os.CreateTemp(filepath.Dir(absolute), "."+filepath.Base(absolute)+"-*.partial")
		if err != nil {
			return output.New(2, "cannot create private temporary download")
		}
		temporaryPath := temporary.Name()
		defer os.Remove(temporaryPath)
		hash := sha256.New()
		written, copyErr := io.Copy(io.MultiWriter(temporary, hash), io.LimitReader(download.Body, revision.SizeBytes+1))
		syncErr := temporary.Sync()
		closeErr := temporary.Close()
		if copyErr != nil || syncErr != nil || closeErr != nil || written != revision.SizeBytes || hex.EncodeToString(hash.Sum(nil)) != revision.SHA256 {
			return output.New(7, "download was incomplete or failed revision integrity verification; no final file was published")
		}
		if a.Yes {
			err = os.Rename(temporaryPath, absolute)
		} else {
			err = os.Link(temporaryPath, absolute)
		}
		if err != nil {
			return output.New(2, "cannot atomically publish verified download; destination may already exist")
		}
		return a.emit(map[string]any{"destination": absolute, "artifact_id": args[1], "revision_id": args[2], "size_bytes": written, "sha256": revision.SHA256, "integrity": "verified", "executed": true})
	}}
	command.Flags().StringVar(&destination, "output-file", "", "Local destination file")
	root.AddCommand(command)
}
