package cli

import (
	"bytes"
	"encoding/json"
	"net/url"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/spf13/cobra"
)

type releaseTestFailure struct {
	Data  any
	Cause *output.Error
}

func (f *releaseTestFailure) Error() string { return f.Cause.Error() }
func (f *releaseTestFailure) Unwrap() error { return f.Cause }

func (a *App) developmentTestCommands() {
	var environment, version, candidate string
	command := &cobra.Command{Use: "test REFERENCE", Short: "Execute a saved Agent snapshot and record its test result", Args: cobra.ExactArgs(1), Long: "Read a YAML/JSON testcase with message, optional expected_output and external_context. Select current Staging by default, Draft/Production with --env, or an immutable Release with --env release --version. Run the native Agent execution pipeline and store actual output, latency and validation errors. A failed assertion or execution exits with code 6; network uncertainty is never retried automatically. Default deadline: 2m unless --timeout is explicit. Preserve the private test UUID and use the reported recovery command after timeout." + candidateEvaluationHelp, Example: "woobe agent '@support' test --candidate CANDIDATE_UUID --file suite.yaml --yes\nwoobe agent '@support' evaluation EVALUATION_UUID", RunE: func(cmd *cobra.Command, args []string) error {
		if cmd.Flags().Changed("candidate") {
			if cmd.Flags().Changed("env") || cmd.Flags().Changed("version") {
				return output.New(2, "Candidate evaluation selects an exact frozen snapshot; omit --env and --version")
			}
			return a.evaluateASaCCandidate(cmd, "agent", args[0], candidate)
		}
		if !a.Yes && !a.DryRun {
			return output.New(2, "Test execution requires --yes")
		}
		if environment != "draft" && environment != "staging" && environment != "production" && environment != "release" {
			return output.New(2, "Invalid test environment")
		}
		if environment == "release" && version == "" {
			return output.New(2, "Release testing requires --version")
		}
		if environment != "release" && version != "" {
			return output.New(2, "--version requires --env release")
		}
		data, err := a.body(true)
		if err != nil {
			return err
		}
		decoder := json.NewDecoder(bytes.NewReader(data))
		decoder.UseNumber()
		var body map[string]any
		if decoder.Decode(&body) != nil {
			return output.New(2, "Testcase must be a YAML or JSON object")
		}
		message, _ := body["message"].(string)
		if message == "" {
			return output.New(2, "Testcase requires a message")
		}
		for field := range body {
			if field != "message" && field != "expected_output" && field != "external_context" {
				return output.New(2, "Testcase accepts only message, expected_output and external_context")
			}
		}
		id, err := a.nativeReference("agent_id", args[0])
		if err != nil {
			return err
		}
		if err = resourceID(id); err != nil {
			return err
		}
		control, err := a.client()
		if err != nil {
			return err
		}
		client, err := packageapi.New(control, a.Project)
		if err != nil {
			return err
		}
		receipt, err := client.Export(cmd.Context(), packageapi.ExportRequest{Kind: "Agent", TargetID: id, Source: &environment, ReleaseVersion: version, Knowledge: "binding"})
		if err != nil {
			return err
		}
		snapshot, _ := receipt.Source["snapshot_id"].(string)
		if snapshot == "" {
			return output.New(9, "Test selection omitted snapshot identity")
		}
		body["project_id"], body["agent_id"], body["release_id"], body["environment"] = a.Project, id, snapshot, environment
		data, err = json.Marshal(body)
		if err != nil {
			return err
		}
		path := "/ai/agents/" + url.PathEscape(id) + "/release-tests/run"
		if a.DryRun {
			return a.call(cmd, "POST", path, data, false)
		}
		result, err := a.requestReleaseTest(cmd, control, path, data)
		if err != nil {
			return err
		}
		envelope, ok := result.(map[string]any)
		if !ok {
			return output.New(9, "Test execution omitted result evidence")
		}
		outcome, ok := envelope["data"].(map[string]any)
		if !ok || (outcome["status"] != "passed" && outcome["status"] != "failed") {
			return output.New(9, "Test execution omitted a terminal test status")
		}
		if outcome["status"] == "failed" {
			return &releaseTestFailure{Data: outcome, Cause: output.New(6, "Agent test failed; inspect validation_errors and actual_output")}
		}
		return a.emit(outcome)
	}}
	command.Flags().StringVar(&environment, "env", "staging", "Saved native environment to test")
	command.Flags().StringVar(&version, "version", "", "Immutable Release version")
	command.Flags().StringVar(&candidate, "candidate", "", "Evaluate this ready Candidate UUID using a versioned YAML suite")
	a.group("develop agent").AddCommand(command)
}
