package cli

import (
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/spf13/cobra"
)

func validateDeploymentAcceptance(data map[string]any, project, id, operation, environment string, body map[string]any, plan bool) error {
	if err := devworkspace.ValidateDeploymentReceipt(data, plan); err != nil {
		return output.New(9, err.Error())
	}
	if data["project_id"] != project || data["resource_id"] != id || data["operation_id"] != operation || data["environment"] != environment {
		return output.New(9, "Deployment belongs to another original operation or destination")
	}
	keys := []string{"plan_id", "leases"}
	if plan {
		keys = []string{"release_id", "publication_id", "action", "reason", "expected_generation"}
	}
	for _, key := range keys {
		if body[key] != nil {
			left, _ := json.Marshal(body[key])
			right, _ := json.Marshal(data[key])
			if string(left) != string(right) {
				return output.New(9, "Deployment differs from the original request")
			}
		}
	}
	return nil
}

func (a *App) asacDeploymentCommands() {
	for _, kind := range []string{"agent", "network"} {
		var environment, operation, release, publication, planID, notes, workflow, lease, action string
		var generation, fence int64
		command := &cobra.Command{Use: "deployment REFERENCE ACTION [UUID]", Short: "Plan, apply, inspect or reconcile an exact Release selection", Args: cobra.RangeArgs(2, 3), Long: "Actions: plan, apply, show, plan-show, reconcile. Plan fixes an evaluated published Release and the expected environment generation; it does not activate. Apply requires --yes and the exact environment workflow lease. Registered aliases retain the original operation before submission and mirror committed receipts before clearing it. Reconcile reads the original operation only and never repeats a write. Native UUID commands work without .woobe-config and require explicit stable operation/workflow proof flags.", Example: "woobe agent '@support' deployment plan --release RELEASE_UUID --expected-generation 4 --notes 'Deploy qualified revision'\nwoobe agent '@support' lease acquire --scope production\nwoobe agent '@support' deployment apply PLAN_UUID --yes\nwoobe agent '@support' deployment reconcile", RunE: func(cmd *cobra.Command, args []string) error {
			verb := args[1]
			switch verb {
			case "plan", "apply", "show", "plan-show", "reconcile":
			default:
				return output.New(2, "Use deployment plan, apply, show, plan-show or reconcile")
			}
			if a.File != "" {
				return output.New(2, "Deployment uses explicit exact evidence; omit --file")
			}
			if environment != "staging" && environment != "production" {
				return output.New(2, "Deployment environment must be staging or production")
			}
			if verb == "plan" {
				if len(args) != 2 || !uuidReference(release) || !cmd.Flags().Changed("expected-generation") || generation < 0 || len(strings.TrimSpace(notes)) < 3 || (action != "activate" && action != "rollback") {
					return output.New(2, "Plan requires --release UUID, --expected-generation and meaningful --notes")
				}
				if publication != "" && !uuidReference(publication) {
					return output.New(2, "Publication must be a UUID")
				}
			}
			if verb == "apply" || verb == "show" || verb == "plan-show" {
				if len(args) != 3 || !uuidReference(args[2]) {
					return output.New(2, "Supply the exact returned Plan or Deployment UUID")
				}
				planID = args[2]
			}
			if verb == "apply" && !a.Yes && !a.DryRun {
				return output.New(2, "Applying a deployment requires --yes")
			}
			var c *devworkspace.Config
			var state *devworkspace.State
			var resource *devworkspace.Resource
			id := args[0]
			if !uuidReference(id) {
				var err error
				c, err = a.developmentConfig(true)
				if err != nil {
					return err
				}
				unlock, err := c.Lock()
				if err != nil {
					return err
				}
				defer unlock()
				if a.ContextName == "" && os.Getenv("WOOBE_CONTEXT") == "" {
					a.ContextName = c.Context
				}
				connection, err := a.resolve()
				if err != nil {
					return err
				}
				state, err = c.ReadState(strings.TrimRight(connection.APIURL, "/"), a.Workspace, a.Project)
				if err != nil {
					return err
				}
				resource, err = developmentReference(c, state, kind, id, "")
				if err != nil {
					return err
				}
				id, err = asacRegisteredResourceID(c, state, resource)
				if err != nil {
					return err
				}
			}
			if err := resourceID(id); err != nil {
				return err
			}
			if _, err := a.resolve(); err != nil {
				return err
			}
			base := fmt.Sprintf("/projects/%s/%ss/%s/asac", url.PathEscape(a.Project), kind, url.PathEscape(id))
			payload := map[string]any{"environment": environment}
			pendingPath := ""
			var pending asacPending
			if c != nil {
				pendingPath = asacPrivatePath(c, state, resource.UID, "pending")
			}
			if verb == "reconcile" && c != nil {
				raw, err := c.ReadOperationalFile(pendingPath, 16<<20)
				if err != nil || decodeASaCPending(raw, &pending) != nil || !uuidReference(pending.OperationID) || (pending.Path != base+"/deployment-plans" && pending.Path != base+"/deployments") {
					return output.New(9, "No original deployment operation is recorded")
				}
				if operation != "" && operation != pending.OperationID {
					return output.New(9, "Operation differs from the recorded deployment")
				}
				operation = pending.OperationID
				payload = pending.Body
				environment = packagefmt.Text(payload["environment"])
			}
			method, path := "GET", base+"/deployments/"+url.PathEscape(planID)
			isPlan := verb == "plan" || verb == "plan-show" || verb == "reconcile" && pending.Path == base+"/deployment-plans"
			if verb == "plan-show" {
				path = base + "/deployment-plans/" + url.PathEscape(planID)
			}
			if verb == "plan" || verb == "apply" {
				if c != nil {
					raw, err := c.ReadOperationalFile(pendingPath, 16<<20)
					if err == nil {
						if !clearedASaCPending(raw) {
							return output.New(9, "An ASaC write is unresolved; reconcile its original operation first")
						}
					} else if !os.IsNotExist(err) {
						return err
					}
				}
				if operation == "" && c != nil {
					var err error
					operation, err = devworkspace.NewID()
					if err != nil {
						return err
					}
				}
				if !uuidReference(operation) {
					return output.New(2, "Native writes require a stable --operation UUID")
				}
				payload["operation_id"] = operation
				if verb == "plan" {
					path = base + "/deployment-plans"
					payload["release_id"], payload["expected_generation"], payload["reason"], payload["action"] = release, generation, notes, action
					if publication != "" {
						payload["publication_id"] = publication
					}
				} else {
					path = base + "/deployments"
					payload["plan_id"] = planID
					if c != nil && lease == "" && workflow == "" && fence == 0 {
						observed, err := readLeaseObservations(c, state, resource.UID, id)
						if err != nil {
							return err
						}
						proof := observed.Leases[environment]
						lease = packagefmt.Text(proof["lease_id"])
						workflow = packagefmt.Text(proof["workflow_id"])
						fence, _ = asacCounter(proof["fencing_token"])
					}
					if !uuidReference(lease) || !uuidReference(workflow) || fence <= 0 {
						return output.New(2, "Acquire this environment lease first, or supply exact --lease, --workflow and --fencing-token")
					}
					payload["leases"] = []map[string]any{{"lease_id": lease, "workflow_id": workflow, "fencing_token": fence}}
				}
				method = "POST"
			}
			if verb == "reconcile" {
				if !uuidReference(operation) {
					return output.New(2, "Reconcile requires the original --operation UUID")
				}
				path = base + "/operations/" + url.PathEscape(operation)
			}
			if a.DryRun {
				return a.emit(map[string]any{"method": method, "path": path, "body": payload, "executed": false})
			}
			control, err := a.client()
			if err != nil {
				return err
			}
			if method == "POST" {
				raw, _, err := control.Request(cmd.Context(), "GET", fmt.Sprintf("/projects/%s/packages/capabilities", url.PathEscape(a.Project)), nil, nil)
				if err != nil {
					return err
				}
				cap, err := developmentResponseData(raw)
				if err != nil {
					return err
				}
				protocol := packagefmt.Object(cap["asac"])
				if protocol["schema_version"] != "1.0" || protocol["fenced_deployment"] != true || protocol["deployment_scope"] != "exact-release-owner-selection@1" {
					return output.New(9, "Backend does not advertise exact fenced Release deployments")
				}
			}
			var encoded []byte
			var query url.Values
			if method == "POST" {
				encoded, _ = json.Marshal(payload)
				if c != nil {
					pending = asacPending{OperationID: operation, Method: method, Path: path, Body: payload}
					raw, _ := json.Marshal(pending)
					if err = c.WriteOperationalFile(pendingPath, raw); err != nil {
						return output.New(10, "Cannot retain the deployment operation before submission")
					}
				}
			} else if verb != "reconcile" {
				query = url.Values{"environment": {environment}}
			}
			raw, _, err := control.Request(cmd.Context(), method, path, query, encoded)
			if err != nil {
				if c != nil && method == "POST" {
					normalized := output.Normalize(err)
					if normalized.Outcome == "rejected" || normalized.Outcome == "not_attempted" {
						if clearErr := c.WriteOperationalFile(pendingPath, []byte("{}")); clearErr != nil {
							return output.New(10, "Rejected deployment remains pending locally")
						}
					}
				}
				return err
			}
			data, err := developmentResponseData(raw)
			if err != nil {
				return err
			}
			if verb == "reconcile" {
				if data["operation_id"] != operation || data["state"] != "committed" {
					return output.New(9, "Original deployment acceptance is not proven committed; do not repeat it")
				}
				data = packagefmt.Object(data["result"])
				if c == nil {
					isPlan = data["state"] == "planned"
					environment = packagefmt.Text(data["environment"])
				}
			}
			if method == "POST" || verb == "reconcile" {
				if err = validateDeploymentAcceptance(data, a.Project, id, operation, environment, payload, isPlan); err != nil {
					return err
				}
				if data["kind"] != strings.Title(kind) {
					return output.New(9, "Deployment kind differs from the requested resource")
				}
				if c != nil {
					if err = c.StoreDeploymentReceipt(*resource, strings.TrimRight(control.Base, "/"), a.Workspace, a.Project, data, isPlan); err != nil {
						return output.New(10, "Deployment accepted; documentary receipt remains pending: "+err.Error())
					}
					if err = c.WriteOperationalFile(pendingPath, []byte("{}")); err != nil {
						return output.New(10, "Deployment accepted; original operation remains pending")
					}
				}
			} else {
				if err = devworkspace.ValidateDeploymentReceipt(data, isPlan); err != nil {
					return output.New(9, err.Error())
				}
				key := "deployment_id"
				if isPlan {
					key = "plan_id"
				}
				if data[key] != planID || data["project_id"] != a.Project || data["resource_id"] != id || data["environment"] != environment || data["kind"] != strings.Title(kind) {
					return output.New(9, "Deployment observation belongs to another destination")
				}
			}
			return a.emit(data)
		}}
		command.Flags().StringVar(&environment, "env", "production", "Exact selection environment: staging or production")
		command.Flags().StringVar(&operation, "operation", "", "Stable original operation UUID; generated for registered writes")
		command.Flags().StringVar(&release, "release", "", "Exact evaluated published Release UUID")
		command.Flags().StringVar(&publication, "publication", "", "Exact publication UUID; server fixes one if omitted")
		command.Flags().Int64Var(&generation, "expected-generation", 0, "Expected monotonic environment generation from current --env")
		command.Flags().StringVar(&notes, "notes", "", "Meaningful audit reason retained in the plan and receipt")
		command.Flags().StringVar(&action, "action", "activate", "Selection action: activate or rollback")
		command.Flags().StringVar(&lease, "lease", "", "Exact environment lease UUID outside registered workflows")
		command.Flags().StringVar(&workflow, "workflow", "", "Original workflow UUID for the environment lease")
		command.Flags().Int64Var(&fence, "fencing-token", 0, "Exact positive environment concurrency counter")
		a.group("develop " + kind).AddCommand(command)
	}
}
