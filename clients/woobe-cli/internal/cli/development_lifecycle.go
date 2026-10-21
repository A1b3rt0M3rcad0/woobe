package cli

import (
	"encoding/json"
	"fmt"
	"net/url"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packageapi"
	"github.com/spf13/cobra"
)

func (a *App) developmentLifecycleCommands() {
	parent := a.group("develop agent")
	for _, action := range []string{"stage", "publish", "activate", "rollback", "archive", "delete"} {
		var version, notes, revision, candidate, evaluation string
		command := &cobra.Command{Use: action + " REFERENCE", Short: action + " an Agent through the native lifecycle", Args: cobra.ExactArgs(1), Long: "Publish --candidate CANDIDATE_UUID --evaluation EVALUATION_UUID --notes REASON --yes publishes the exact ready Candidate after its passed Evaluation; it never changes Production or reads current Staging. It persists original acceptance and an append-only local receipt. On uncertain acceptance or local receipt failure, use draft reconcile without repeating publication. Stage --revision REVISION_ID prepares the exact checkpointed isolated Draft as a detached Candidate; it reads the retained executable object, preserves native Draft/Staging/Production selections and does not publish. Inspect with candidate REFERENCE CANDIDATE_UUID. Reconcile lost acceptance using draft reconcile before another Stage. Without --revision, legacy native lifecycle behavior applies. Select the current native environment automatically. stage copies current Draft to Staging; publish creates an immutable Release from current Staging; activate and rollback require an explicit Release version. Local YAML is never silently pushed by lifecycle commands. Run push first. Publication requires --yes and an audit reason in --notes.", RunE: func(cmd *cobra.Command, args []string) error {
			if cmd.Flags().Changed("candidate") || cmd.Flags().Changed("evaluation") {
				if action != "publish" || version != "" || revision != "" {
					return output.New(2, "--candidate and --evaluation apply only to exact publication; omit --version and --revision")
				}
				return a.publishASaCCandidate(cmd, "agent", args[0], candidate, evaluation, notes)
			}
			if cmd.Flags().Changed("revision") && strings.TrimSpace(revision) == "" {
				return output.New(2, "--revision requires the exact sealed revision ID; refusing legacy Stage fallback")
			}
			if revision != "" {
				if action != "stage" || version != "" || notes != "" {
					return output.New(2, "--revision applies only to Stage; it cannot select a published version or activation reason")
				}
				return a.stageASaCRevision(cmd, "agent", args[0], revision)
			}
			if a.File != "" {
				return output.New(2, "Lifecycle commands use native saved snapshots; use push to synchronize author YAML")
			}
			if !a.Yes && !a.DryRun {
				return output.New(2, "Lifecycle mutation requires --yes")
			}
			if (action == "activate" || action == "rollback") && version == "" {
				return output.New(2, "Select the immutable Release with --version")
			}
			if action != "stage" && action != "archive" && action != "delete" && len(strings.TrimSpace(notes)) < 3 {
				return output.New(2, "Supply an audit reason with --notes (at least three characters)")
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
			path := "/ai/agents/" + url.PathEscape(id)
			body := map[string]any{}
			method := "POST"
			if action == "archive" || action == "delete" {
				method = "DELETE"
				response, _, readErr := control.Request(cmd.Context(), "GET", path, nil, nil)
				if readErr != nil {
					return readErr
				}
				current, readErr := developmentResponseData(response)
				if readErr != nil {
					return readErr
				}
				if current["revision"] == nil {
					return output.New(9, "Agent read omitted archive revision")
				}
				if a.IfMatch == "" {
					a.IfMatch = fmt.Sprintf("\"%v\"", current["revision"])
				}
			} else {
				client, err := packageapi.New(control, a.Project)
				if err != nil {
					return err
				}
				env, target := "draft", "staging"
				if action == "publish" {
					env, target = "staging", "released"
				}
				if action == "activate" || action == "rollback" {
					env, target = "release", "production"
				}
				receipt, err := client.Export(cmd.Context(), packageapi.ExportRequest{Kind: "Agent", TargetID: id, Source: &env, ReleaseVersion: version, Knowledge: "binding"})
				if err != nil {
					return err
				}
				snapshot, _ := receipt.Source["snapshot_id"].(string)
				if snapshot == "" {
					return output.New(9, "Native environment selection omitted snapshot identity")
				}
				path += "/releases/" + url.PathEscape(snapshot) + "/promote"
				body = map[string]any{"target_status": target, "copy_snapshot": action == "stage", "release_notes": notes, "change_description": notes}
				if action == "rollback" {
					path = strings.TrimSuffix(path, "promote") + "rollback"
					body = map[string]any{"change_description": notes}
				}
			}
			data, err := json.Marshal(body)
			if err != nil {
				return err
			}
			return a.call(cmd, method, path, data, false)
		}}
		command.Flags().StringVar(&candidate, "candidate", "", "Publish this exact ready Candidate UUID without changing Production")
		command.Flags().StringVar(&evaluation, "evaluation", "", "Passed Evaluation UUID for this exact Candidate")
		command.Flags().StringVar(&revision, "revision", "", "Prepare the exact sealed revision from the selected isolated Draft; does not publish or select native Staging")
		command.Flags().StringVar(&version, "version", "", "Immutable Release version for activation or rollback")
		command.Flags().StringVar(&notes, "notes", "", "Release description or activation/rollback reason")
		parent.AddCommand(command)
	}
}
