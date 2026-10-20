package cli

import (
	"encoding/json"
	"net/url"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
)

func developmentResponseData(response any) (map[string]any, error) {
	envelope, ok := response.(map[string]any)
	if !ok {
		return nil, output.New(9, "Native operation omitted its response envelope")
	}
	data, ok := envelope["data"].(map[string]any)
	if !ok {
		return nil, output.New(9, "Native operation omitted its result evidence")
	}
	return data, nil
}

func (a *App) developmentNetworkLifecycleCommands() {
	for _, action := range []string{"stage", "publish", "activate", "rollback"} {
		var version, notes, revision, candidate, evaluation string
		command := &cobra.Command{Use: action + " REFERENCE", Short: action + " a saved Network composition", Args: cobra.ExactArgs(1), Long: "Publish --candidate UUID --evaluation UUID --notes REASON --yes creates the exact qualified Network Release without changing Production or standalone Agent environments. Partial preparations remain durable; inspect publication, explicitly reconcile or cancel, then use draft reconcile to recover original acceptance without repeating publication. Stage --revision REVISION_ID prepares the exact checkpointed isolated Draft as a detached Candidate; it reads the retained executable object, preserves native Draft/Staging/Production selections and does not publish. Inspect with candidate REFERENCE CANDIDATE_UUID. Reconcile lost acceptance using draft reconcile before another Stage. Without --revision, legacy native lifecycle behavior applies. stage previews the current Draft and freezes its constituent snapshots. publish previews current Staging, creates/reuses the immutable Network Release and activates it in Production, following Woobe's native publication behavior. activate/rollback select an explicit immutable Release with --version and record --notes. --yes approves only the preview's action IDs; concurrent changes fail. Local author YAML is never uploaded implicitly.", RunE: func(cmd *cobra.Command, args []string) error {
			if cmd.Flags().Changed("candidate") || cmd.Flags().Changed("evaluation") {
				if action != "publish" || version != "" || revision != "" {
					return output.New(2, "--candidate and --evaluation apply only to exact publication; omit --version and --revision")
				}
				return a.publishASaCCandidate(cmd, "network", args[0], candidate, evaluation, notes)
			}
			if cmd.Flags().Changed("revision") && strings.TrimSpace(revision) == "" {
				return output.New(2, "--revision requires the exact sealed revision ID; refusing legacy Stage fallback")
			}
			if revision != "" {
				if action != "stage" || version != "" || notes != "" {
					return output.New(2, "--revision applies only to Stage; it cannot select a published version or activation reason")
				}
				return a.stageASaCRevision(cmd, "network", args[0], revision)
			}
			if a.File != "" {
				return output.New(2, "Push author YAML before changing the saved Network lifecycle")
			}
			if !a.Yes && !a.DryRun {
				return output.New(2, "Network lifecycle mutation requires --yes")
			}
			if (action == "activate" || action == "rollback") && (version == "" || len(strings.TrimSpace(notes)) < 3) {
				return output.New(2, "Activation/rollback require --version and an audit reason in --notes")
			}
			if (action == "stage" || action == "publish") && (version != "" || notes != "") {
				return output.New(2, "Stage/publish use the current native snapshot; --version and --notes apply to activation/rollback")
			}
			id, err := a.nativeReference("network_id", args[0])
			if err != nil {
				return err
			}
			if err = resourceID(id); err != nil {
				return err
			}
			client, err := a.client()
			if err != nil {
				return err
			}
			path := "/network/" + url.PathEscape(id)
			body := map[string]any{"project_id": a.Project}
			if action == "stage" || action == "publish" {
				environment := "staging"
				if action == "publish" {
					environment = "production"
				}
				body["environment"] = environment
				encoded, _ := json.Marshal(body)
				response, _, err := client.Request(cmd.Context(), "POST", path+"/promotions/preview", nil, encoded)
				if err != nil {
					return err
				}
				preview, err := developmentResponseData(response)
				if err != nil {
					return err
				}
				if preview["ready"] != true {
					return output.New(6, "Network promotion is blocked; inspect network promotion preview")
				}
				if environment == "staging" {
					if preview["network_revision"] == nil {
						return output.New(9, "Promotion preview omitted Draft revision")
					}
					body["expected_revision"] = preview["network_revision"]
				} else {
					source, _ := preview["network_version_id"].(string)
					if source == "" {
						return output.New(9, "Promotion preview omitted Staging identity")
					}
					body["expected_network_version_id"] = source
				}
				approvals := []string{}
				actions, _ := preview["actions"].([]any)
				for _, raw := range actions {
					item, ok := raw.(map[string]any)
					if !ok {
						return output.New(9, "Promotion preview contained an invalid action")
					}
					identity, _ := item["id"].(string)
					if identity == "" {
						identity, _ = item["action_id"].(string)
					}
					if identity == "" {
						return output.New(9, "Promotion preview omitted action identity")
					}
					approvals = append(approvals, identity)
				}
				body["approved_action_ids"] = approvals
				path += "/promotions"
			} else {
				response, _, err := client.Request(cmd.Context(), "GET", path+"/management/versions", url.Values{"project_id": {a.Project}}, nil)
				if err != nil {
					return err
				}
				envelope, ok := response.(map[string]any)
				if !ok {
					return output.New(9, "Network versions omitted response envelope")
				}
				versions, ok := envelope["data"].([]any)
				if !ok {
					return output.New(9, "Network versions omitted immutable identity evidence")
				}
				selected := ""
				for _, raw := range versions {
					item, ok := raw.(map[string]any)
					if !ok {
						continue
					}
					if item["kind"] == "release" && item["version"] == version {
						if selected != "" {
							return output.New(6, "Release version is ambiguous")
						}
						selected, _ = item["id"].(string)
					}
				}
				if selected == "" {
					return output.New(6, "Immutable Network Release was not found")
				}
				response, _, err = client.Request(cmd.Context(), "GET", "/network/projects/"+url.PathEscape(a.Project)+"/networks/"+url.PathEscape(id), nil, nil)
				if err != nil {
					return err
				}
				current, err := developmentResponseData(response)
				if err != nil {
					return err
				}
				if current["production_version_id"] == selected {
					return output.New(6, "Selected Network Release is already in Production; choose a different immutable version")
				}
				body["source_version_id"], body["expected_current_production_version_id"], body["change_description"] = selected, current["production_version_id"], notes
				path += "/production/activations"
			}
			encoded, err := json.Marshal(body)
			if err != nil {
				return err
			}
			return a.call(cmd, "POST", path, encoded, false)
		}}
		command.Flags().StringVar(&candidate, "candidate", "", "Publish the exact qualified Candidate without changing Production")
		command.Flags().StringVar(&evaluation, "evaluation", "", "Passed Evaluation of the exact Candidate")
		command.Flags().StringVar(&revision, "revision", "", "Prepare the exact sealed revision from the selected isolated Draft; does not publish or select native Staging")
		command.Flags().StringVar(&version, "version", "", "Immutable Network Release version")
		command.Flags().StringVar(&notes, "notes", "", "Activation or rollback audit reason")
		a.group("develop network").AddCommand(command)
	}
}
