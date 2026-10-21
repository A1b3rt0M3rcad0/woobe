package cli

import (
	"context"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/credentials"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/identity"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/requestinput"
	"github.com/spf13/cobra"
	"golang.org/x/term"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"time"
)

var Version = "dev"
var Commit = "unknown"

type App struct {
	asacResult                                                                               func(any) error
	asacOperation                                                                            string
	asacSourceExport, asacArtifactDigest                                                     string
	ProjectConfig                                                                            string
	NoProjectConfig                                                                          bool
	packageCheckpointPath                                                                    string
	packageOutputSequence                                                                    int64
	SchemaSHA                                                                                string
	Root                                                                                     *cobra.Command
	In                                                                                       io.Reader
	Out, Err                                                                                 io.Writer
	ConfigPath, ContextName, APIURL, Workspace, Project, Credential, RuntimeCredential, Mode string
	Timeout                                                                                  time.Duration
	ValidateBody                                                                             bool
	ValidateParameters                                                                       bool
	Yes, DryRun, NoInput                                                                     bool
	InputFormat                                                                              string
	File, IfMatch, IdempotencyKey, SecretFile                                                string
	Query                                                                                    []string
	Registry                                                                                 []Operation
	OutputFields                                                                             []string
	OutputWide                                                                               bool
	StrictFields                                                                             bool
	outputCommand                                                                            string
}

func New(in io.Reader, out, errOut io.Writer) *App {
	a := &App{In: in, Out: out, Err: errOut}
	r := &cobra.Command{Use: "woobe", Short: "Woobe public control plane and runtime", SilenceErrors: true, SilenceUsage: true}
	a.Root = r
	r.SetIn(in)
	r.SetOut(out)
	r.SetErr(errOut)
	f := r.PersistentFlags()
	f.StringVar(&a.ProjectConfig, "project-config", "", "Optional local development configuration (development commands only)")
	f.BoolVar(&a.NoProjectConfig, "no-project-config", false, "Ignore the local development registry")
	f.StringVar(&a.ConfigPath, "config", config.DefaultPath(), "Private config file")
	f.StringVar(&a.ContextName, "context", "", "Context name")
	f.StringVar(&a.APIURL, "api-url", "", "API origin")
	f.StringVar(&a.Workspace, "workspace", "", "Workspace ID")
	f.StringVar(&a.Project, "project", "", "Project ID")
	f.StringVar(&a.Credential, "credential", "", "Administrative credential reference")
	f.StringVar(&a.RuntimeCredential, "runtime-credential", "", "Runtime credential reference")
	defaultOutput := os.Getenv("WOOBE_OUTPUT")
	if defaultOutput == "" {
		defaultOutput = "auto"
	}
	f.StringVar(&a.Mode, "output", defaultOutput, "auto (text in terminals, JSON in pipes), text, table, compact, json or jsonl")
	f.StringSliceVar(&a.OutputFields, "fields", nil, "Response fields to display, comma-separated; dotted paths supported (text/table/compact)")
	f.BoolVar(&a.OutputWide, "wide", false, "Show all response fields in text/table/compact output")
	f.BoolVar(&a.StrictFields, "strict-fields", false, "Reject absent --fields paths (explicit null values remain valid)")
	f.DurationVar(&a.Timeout, "timeout", 30*time.Second, "HTTP deadline")
	f.BoolVar(&a.Yes, "yes", false, "Accept the specified destructive operation")
	f.BoolVar(&a.NoInput, "no-input", false, "Disable interactive authentication and project prompts")
	f.StringVar(&a.SchemaSHA, "schema-sha256", "", "Expected advertised OpenAPI snapshot SHA-256 when validating bodies")
	f.BoolVar(&a.ValidateParameters, "validate-parameters", false, "Validate advertised path and query schemas before a canonical HTTP operation")
	f.BoolVar(&a.ValidateBody, "validate-body", false, "Validate the advertised request-body schema before a canonical write")
	f.BoolVar(&a.DryRun, "dry-run", false, "Render the request without executing")
	f.StringVar(&a.File, "file", "", "YAML or JSON input file, or - for stdin")
	f.StringVar(&a.InputFormat, "input-format", "auto", "Input format: auto, json or yaml (including stdin)")
	f.StringArrayVar(&a.Query, "query", nil, "Query name=value (repeatable)")
	f.StringVar(&a.IfMatch, "if-match", "", "Expected server ETag")
	f.StringVar(&a.IdempotencyKey, "idempotency-key", "", "Key, only when supported by server")
	f.StringVar(&a.SecretFile, "secret-file", "", "Exclusive private issued-secret JSON destination; published after successful issuance")
	r.PersistentPreRunE = func(cmd *cobra.Command, args []string) error {
		path := strings.TrimPrefix(cmd.CommandPath(), "woobe ")
		a.outputCommand = path
		if !output.ValidMode(a.Mode) {
			return output.New(2, "invalid output mode")
		}
		a.selectOutput()
		if err := output.ValidateFields(a.OutputFields); err != nil {
			return err
		}
		if len(a.OutputFields) > 0 && (a.Mode == "json" || a.Mode == "jsonl") {
			return output.New(2, "--fields requires --output text, table or compact; full JSON output is unchanged")
		}
		if a.StrictFields && len(a.OutputFields) == 0 {
			return output.New(2, "--strict-fields requires --fields")
		}
		if a.StrictFields && !cmd.DisableFlagParsing && !a.strictFieldRead(path, args) {
			return output.New(2, "--strict-fields is for read-only inspections; inspect a write receipt separately to avoid confusing an accepted write with a presentation error")
		}
		if a.SchemaSHA != "" {
			if len(a.SchemaSHA) != 64 || strings.Trim(a.SchemaSHA, "0123456789abcdef") != "" {
				return output.New(2, "schema-sha256 must be 64 lowercase hexadecimal characters")
			}
			if !a.ValidateBody && !a.ValidateParameters && path != "manifest preflight" && path != "validate-input" {
				return output.New(2, "schema-sha256 requires body validation")
			}
		}
		if a.ValidateParameters {
			op, ok := a.operation(path)
			if !(packageHTTPCommand(path) || path == "validate-input" || path == "manifest apply" || path == "manifest preflight" || ok && op.Kind == "http") {
				return output.New(9, "--validate-parameters requires a canonical HTTP operation or manifest apply/preflight or validate-input")
			}
		}
		if a.ValidateBody {
			path := strings.TrimPrefix(cmd.CommandPath(), "woobe ")
			op, ok := a.operation(path)
			if !(packageHTTPCommand(path) || path == "manifest apply" || path == "manifest preflight" || path == "validate-input" || (ok && op.Kind == "http" && op.Method != "GET" && op.Method != "HEAD")) {
				return output.New(9, "--validate-body requires a canonical HTTP write or manifest apply/preflight")
			}
		}
		if a.Timeout <= 0 {
			return output.New(2, "timeout must be positive")
		}
		return nil
	}
	r.AddCommand(&cobra.Command{Use: "version", Args: cobra.NoArgs, RunE: func(*cobra.Command, []string) error {
		return a.emit(map[string]any{"version": Version, "commit": Commit, "go_version": runtime.Version(), "os": runtime.GOOS, "arch": runtime.GOARCH, "schema_version": "1"})
	}})
	a.assistantSkillCommands()
	a.developmentConfigCommands()
	a.developmentCommands()
	a.asacCommands()
	a.unifiedDeployCommands()
	a.asacReceiptCommands()
	a.asacGitCommands()
	a.developmentLifecycleCommands()
	a.developmentNetworkLifecycleCommands()
	a.developmentTestCommands()
	a.contextCommands()
	a.requestCommands()
	a.requestPagesCommand()
	a.workspaceCommands()
	a.projectCommands()
	a.configurationCommands()
	a.agentCommands()
	a.releaseCommands()
	a.networkCommands()
	a.toolCommands()
	a.knowledgeCommands()
	a.catalogCommands()
	a.surfaceCommands()
	a.keysCommands()
	a.permissionCommands()
	a.authCommands()
	a.controlAuthCommands()
	a.runtimeCommands()
	a.artifactCommands()
	a.manifestCommands()
	a.packageCommands()
	a.uploadCommands()
	a.exportCommands()
	a.projectionCommand()
	a.aliasCommands()
	a.remoteSchemaCommand()
	a.validateInputCommand()
	a.discoveryCommands()
	a.installCommandGuides()
	a.completeDiscovery()
	a.validateCommandGroups(r)
	return a
}

func (a *App) strictFieldRead(path string, args []string) bool {
	if op, ok := a.operation(path); ok && op.Method != "" {
		return op.Method == "GET" || op.Method == "HEAD"
	}
	if path == "request" {
		return len(args) > 0 && (args[0] == "GET" || args[0] == "HEAD")
	}
	if strings.HasPrefix(path, "develop ") {
		if len(strings.Fields(path)) < 3 {
			return false
		}
		action := strings.Fields(path)[2]
		switch action {
		case "current", "status", "diff", "candidate", "heads":
			return true
		case "draft":
			return len(args) > 1 && (args[1] == "list" || args[1] == "show")
		case "history":
			return len(args) == 1 || len(args) > 1 && (args[1] == "list" || args[1] == "show" || args[1] == "verify")
		}
		return false
	}
	// Local reads with no remote/local mutation; unknown commands fail closed.
	switch path {
	case "version", "context list", "context show", "config show", "config check", "resources list", "resources used-by", "resources validate", "auth status", "auth key inspect", "doctor", "package doctor", "package status", "package validate", "server-schema", "schema", "help":
		return true
	}
	return false
}

// Cobra otherwise renders help successfully when an unresolved argument reaches
// a non-runnable group. Keep bare groups discoverable, but never accept a typo.
func (a *App) validateCommandGroups(cmd *cobra.Command) {
	if cmd != a.Root && cmd.Run == nil && cmd.RunE == nil {
		cmd.Args = cobra.NoArgs
		cmd.RunE = func(cmd *cobra.Command, _ []string) error { return cmd.Help() }
		if cmd.Annotations == nil {
			cmd.Annotations = map[string]string{}
		}
		cmd.Annotations["command_group"] = "true"
	}
	for _, child := range cmd.Commands() {
		a.validateCommandGroups(child)
	}
}
func (a *App) emit(v any) error {
	if a.asacResult != nil {
		return a.asacResult(v)
	}
	return a.writeOutput(a.Out, output.Redact(v), map[string]string{"workspace_id": a.Workspace, "project_id": a.Project}, nil, nil)
}

func (a *App) selectOutput() {
	if a.Mode != "auto" {
		return
	}
	a.Mode = "json"
	if f, ok := a.Out.(interface{ Fd() uintptr }); ok && term.IsTerminal(int(f.Fd())) {
		a.Mode = "text"
	}
}

func (a *App) writeOutput(w io.Writer, data any, scope map[string]string, err error, meta map[string]any) error {
	a.selectOutput()
	mode := a.Mode
	if !output.ValidMode(mode) {
		mode = "json"
	}
	return output.WriteView(w, output.Options{Mode: mode, Command: a.outputCommand, Fields: a.OutputFields, Wide: a.OutputWide, StrictFields: a.StrictFields}, data, scope, err, meta)
}
func (a *App) store() credentials.Store {
	return credentials.Store{Dir: filepath.Join(filepath.Dir(a.ConfigPath), "credentials")}
}
func (a *App) resolve() (config.Context, error) {
	c, e := config.Load(a.ConfigPath)
	if e != nil {
		return config.Context{}, output.New(2, "cannot load config")
	}
	name := a.ContextName
	if name == "" {
		name = os.Getenv("WOOBE_CONTEXT")
	}
	if name == "" {
		name = c.Current
	}
	v := config.Context{}
	if name != "" {
		var ok bool
		v, ok = c.Contexts[name]
		if !ok {
			return v, output.New(2, "unknown context")
		}
	}
	originalWorkspace := v.Workspace
	vals := []struct {
		dst             *string
		flag, env, name string
	}{{&v.APIURL, a.APIURL, "WOOBE_API_URL", "api-url"}, {&v.Workspace, a.Workspace, "WOOBE_WORKSPACE_ID", "workspace"}, {&v.Project, a.Project, "WOOBE_PROJECT_ID", "project"}, {&v.Credential, a.Credential, "WOOBE_CREDENTIAL", "credential"}, {&v.RuntimeCredential, a.RuntimeCredential, "WOOBE_RUNTIME_CREDENTIAL", "runtime-credential"}}
	for _, x := range vals {
		if x.flag != "" || a.Root.PersistentFlags().Changed(x.name) {
			*x.dst = x.flag
		} else if s := os.Getenv(x.env); s != "" {
			*x.dst = s
		}
	}
	if v.Workspace != originalWorkspace && a.Project == "" && !a.Root.PersistentFlags().Changed("project") && os.Getenv("WOOBE_PROJECT_ID") == "" {
		v.Project = ""
	}
	if v.APIURL == "" {
		v.APIURL = "http://localhost:8000"
	}
	// A managed reference must retain its owner even when a legacy reference
	// flag/environment override is supplied. Validate before any secret is read.
	for owner, connection := range c.Contexts {
		if v.Credential != "" && connection.Credential == v.Credential && isConnectionCredential(connection) {
			if owner != name || strings.TrimRight(v.APIURL, "/") != connection.AuthAPIURL {
				return v, output.New(3, "CLI Key reference belongs to another connection or API URL; use its context or log in to this connection")
			}
		}
	}
	a.Workspace = v.Workspace
	a.Project = v.Project
	return v, nil
}
func (a *App) client() (*controlplane.Client, error) {
	v, e := a.resolve()
	if e != nil {
		return nil, e
	}
	if v.AuthAPIURL != "" && strings.TrimRight(v.APIURL, "/") != v.AuthAPIURL {
		return nil, output.New(3, "CLI Key belongs to a different API URL; update the context and log in again")
	}
	key := os.Getenv("WOOBE_CONTROL_KEY")
	if v.Credential != "" {
		key, e = a.store().Get(v.Credential)
		if e != nil {
			return nil, e
		}
	}
	c, e := controlplane.New(v.APIURL, key, a.Timeout)
	if e == nil {
		c.Headers.Set("User-Agent", "woobe-cli/"+Version)
		if key == "" {
			session, jar, err := identity.Load(filepath.Join(filepath.Dir(a.ConfigPath), "sessions"), v.APIURL)
			if err != nil {
				return nil, output.New(3, "cannot restore session")
			}
			c.HTTP.Jar = jar
			c.ResponseHook = session.Capture
			c.Headers.Set("X-CSRF-Token", session.CSRF)
		}
		if a.IfMatch != "" {
			c.Headers.Set("If-Match", a.IfMatch)
		}
		if a.IdempotencyKey != "" {
			c.Headers.Set("Idempotency-Key", a.IdempotencyKey)
		}
	}
	return c, e
}
func (a *App) body(required bool) ([]byte, error) {
	if a.File == "" {
		if required {
			return nil, output.New(2, "--file is required (use - for stdin)")
		}
		return nil, nil
	}
	var b []byte
	var e error
	if a.File == "-" {
		b, e = io.ReadAll(io.LimitReader(a.In, 8<<20+1))
	} else {
		f, err := os.Open(a.File)
		if err != nil {
			return nil, output.New(2, "cannot read input")
		}
		defer f.Close()
		b, e = io.ReadAll(io.LimitReader(f, 8<<20+1))
	}
	if e != nil {
		return nil, output.New(2, "cannot read input")
	}
	converted, err := requestinput.Decode(b, a.File, a.InputFormat)
	if err != nil {
		return nil, output.New(2, err.Error())
	}
	return converted, nil
}
func (a *App) query() (url.Values, error) {
	q := url.Values{}
	for _, s := range a.Query {
		k, v, ok := strings.Cut(s, "=")
		if !ok || k == "" {
			return nil, output.New(2, "query must be name=value")
		}
		q.Add(k, v)
	}
	return q, nil
}
func (a *App) Execute(ctx context.Context, args []string) int {
	a.Root.SetArgs(args)
	command, e := a.Root.ExecuteContextC(ctx)
	if e == nil {
		return 0
	}
	if failure, ok := e.(*deployFailure); ok {
		_ = a.writeOutput(a.Out, failure.Data, map[string]string{"workspace_id": a.Workspace, "project_id": a.Project}, failure.Cause, map[string]any{"complete": false})
		return failure.Cause.Code
	}
	if failure, ok := e.(*releaseTestFailure); ok {
		_ = a.writeOutput(a.Out, failure.Data, nil, failure.Cause, map[string]any{"complete": true, "executed": true})
		return failure.Cause.Code
	}
	if failure, ok := e.(*configurationReadinessFailure); ok {
		_ = a.writeOutput(a.Out, failure.Data, map[string]string{"workspace_id": a.Workspace, "project_id": a.Project}, failure.Cause, map[string]any{"complete": true, "executed": false})
		return failure.Cause.Code
	}
	if failure, ok := e.(*developmentBatchFailure); ok {
		_ = a.writeOutput(a.Out, failure.Data, nil, failure.Cause, map[string]any{"complete": false})
		return failure.Cause.Code
	}
	if failure, ok := e.(*packageOperationFailure); ok {
		_ = a.writeOutput(a.Out, failure.Operation, map[string]string{"project_id": failure.Operation.ProjectID}, failure.Cause, a.packageFinalMeta(failure.Operation))
		return failure.Cause.Code
	}
	if failure, ok := e.(*packageFailure); ok {
		code := 2
		if failure.Diagnostic.Code == "PACKAGE_UNSUPPORTED" {
			code = 9
		}
		_ = a.writeOutput(a.Out, map[string]any{"package_schema_version": "1.0", "valid": false, "diagnostics": []*packagefmt.Diagnostic{failure.Diagnostic}, "executed": false}, nil, output.New(code, failure.Diagnostic.Message), nil)
		return code
	}
	if p, ok := e.(*preflightFailure); ok {
		_ = a.emitPreflight(p.Data, p.Cause)
		return p.Cause.Code
	}
	if partial, ok := e.(*manifestPartial); ok {
		return a.emitManifestPartial(partial)
	}
	if partial, ok := e.(*partialPages); ok {
		cause := partial.Cause
		failure := &output.Error{Code: partial.Code, Message: partial.Message}
		if cause != nil {
			failure.Status = cause.Status
			failure.RequestID = cause.RequestID
		}
		_ = a.writeOutput(a.Out, output.Redact(partial.Data), nil, failure, partial.Meta)
		return partial.Code
	}
	if partial, ok := e.(*diagnosticPartial); ok {
		_ = a.writeOutput(a.Out, output.Redact(partial.Data), nil, &output.Error{Code: 10, Message: partial.Error()}, nil)
		return 10
	}
	if _, ok := e.(*output.Error); !ok {
		if output.Normalize(e).Code == 1 {
			e = output.New(2, e.Error())
		}
	}
	e = output.Normalize(e)
	if failure := output.Normalize(e); failure.Code == 2 && failure.Status == 0 && command != nil {
		failure.Message += "; see " + command.CommandPath() + " --help"
	}
	meta := map[string]any{}
	if a.packageCheckpointPath != "" {
		meta["checkpoint"] = a.packageCheckpointPath
		meta["recovery_command"] = "woobe package status --checkpoint " + strconv.Quote(a.packageCheckpointPath) + " --wait"
	}
	w := a.Out
	if a.Mode == "jsonl" {
		w = a.Err
	}
	_ = a.writeOutput(w, nil, map[string]string{"workspace_id": a.Workspace, "project_id": a.Project}, e, meta)
	return output.Normalize(e).Code
}
