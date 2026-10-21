package cli

import (
	"encoding/json"
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/spf13/cobra"
)

// These observations are private workflow proofs, never portable author locks.
type asacLeaseObservations struct {
	ResourceID string                    `json:"resource_id"`
	ProjectID  string                    `json:"project_id"`
	Leases     map[string]map[string]any `json:"leases"`
}

func decodeASaCPending(raw []byte, pending *asacPending) error {
	if err := jsoninput.Validate(raw); err != nil {
		return err
	}
	decoder := json.NewDecoder(strings.NewReader(string(raw)))
	decoder.UseNumber()
	return decoder.Decode(pending)
}

func clearedASaCPending(raw []byte) bool {
	if jsoninput.Validate(raw) != nil {
		return false
	}
	var marker map[string]any
	return json.Unmarshal(raw, &marker) == nil && marker != nil && len(marker) == 0
}

func asacCounter(value any) (int64, bool) {
	raw, err := json.Marshal(value)
	if err != nil {
		return 0, false
	}
	n, err := strconv.ParseInt(string(raw), 10, 64)
	return n, err == nil && n > 0
}

func validateLeaseReceipt(data map[string]any, project, id, operation, scope string, body map[string]any) error {
	fail := func() error {
		return output.New(9, "Lease receipt differs from the original workflow; reconcile its original operation")
	}
	if data["schema_version"] != "1.0" || data["complete"] != true || data["clock_authority"] != "database" || data["project_id"] != project || data["resource_id"] != id || data["operation_id"] != operation || data["write_outcome"] != "committed" || data["scope"] != scope {
		return fail()
	}
	for _, key := range []string{"lease_id", "workflow_id"} {
		if !uuidReference(packagefmt.Text(data[key])) {
			return fail()
		}
		if body[key] != nil && body[key] != data[key] {
			return fail()
		}
	}
	counter, ok := asacCounter(data["fencing_token"])
	if !ok {
		return fail()
	}
	if body["fencing_token"] != nil {
		expected, valid := asacCounter(body["fencing_token"])
		if !valid || counter != expected {
			return fail()
		}
	}
	if packagefmt.Text(data["actor"]) == "" {
		return fail()
	}
	dates := make(map[string]time.Time)
	for _, key := range []string{"acquired_at", "expires_at", "maximum_expires_at", "server_time"} {
		value, err := time.Parse(time.RFC3339Nano, packagefmt.Text(data[key]))
		if err != nil {
			return fail()
		}
		dates[key] = value
	}
	if !dates["expires_at"].After(dates["acquired_at"]) || dates["expires_at"].After(dates["maximum_expires_at"]) || dates["server_time"].Before(dates["acquired_at"]) {
		return fail()
	}
	switch data["state"] {
	case "active", "released", "broken":
	default:
		return fail()
	}
	if data["state"] == "active" && !dates["expires_at"].After(dates["server_time"]) {
		return fail()
	}
	return nil
}

func validateLeaseAction(data map[string]any, action string) error {
	expected := map[string]string{"acquire": "active", "renew": "active", "release": "released", "break": "broken"}[action]
	if expected == "" || data["state"] != expected {
		return output.New(9, "Lease outcome differs from the original mutation; reconcile its original operation")
	}
	return nil
}

func readLeaseObservations(c *devworkspace.Config, state *devworkspace.State, uid, id string) (*asacLeaseObservations, error) {
	observed := &asacLeaseObservations{ResourceID: id, ProjectID: state.Project, Leases: map[string]map[string]any{}}
	raw, err := c.ReadOperationalFile(asacPrivatePath(c, state, uid, "leases"), 1<<20)
	if os.IsNotExist(err) {
		return observed, nil
	}
	if err != nil {
		return nil, err
	}
	decoder := json.NewDecoder(strings.NewReader(string(raw)))
	decoder.UseNumber()
	if decoder.Decode(observed) != nil || observed.ResourceID != id || observed.ProjectID != state.Project || observed.Leases == nil {
		return nil, output.New(9, "Lease observation belongs to another resource or Project")
	}
	return observed, nil
}

func storeLeaseObservation(c *devworkspace.Config, state *devworkspace.State, uid, id string, data map[string]any) error {
	observed, err := readLeaseObservations(c, state, uid, id)
	if err != nil {
		return err
	}
	observed.Leases[packagefmt.Text(data["scope"])] = data
	raw, err := json.Marshal(observed)
	if err != nil {
		return err
	}
	return c.WriteOperationalFile(asacPrivatePath(c, state, uid, "leases"), raw)
}

// Never drop expired or superseded proofs based on a local clock or a GET. Only
// explicit owned release removes the requirement; the server decides validity.
func authoringLeaseProofs(c *devworkspace.Config, state *devworkspace.State, uid, id, draft string) ([]map[string]any, error) {
	observed, err := readLeaseObservations(c, state, uid, id)
	if err != nil {
		return nil, err
	}
	proofs := []map[string]any{}
	keys := []string{"resource"}
	if draft != "" {
		keys = append(keys, "draft:"+draft)
	}
	for _, scope := range keys {
		receipt := observed.Leases[scope]
		if receipt == nil || receipt["state"] == "released" {
			continue
		}
		if err := validateLeaseReceipt(receipt, state.Project, id, packagefmt.Text(receipt["operation_id"]), scope, map[string]any{}); err != nil {
			return nil, err
		}
		proofs = append(proofs, map[string]any{"lease_id": receipt["lease_id"], "workflow_id": receipt["workflow_id"], "fencing_token": receipt["fencing_token"]})
	}
	return proofs, nil
}

func asacLeaseScope(scope, draft string) (string, error) {
	switch scope {
	case "resource", "staging", "production":
		if draft != "" {
			return "", output.New(2, "--draft applies only to --scope draft")
		}
		return scope, nil
	case "draft":
		if draft != "" && !uuidReference(draft) {
			return "", output.New(2, "--draft requires an isolated Draft UUID")
		}
		if draft == "" {
			draft = "native"
		}
		return "draft:" + draft, nil
	default:
		return "", output.New(2, "Use --scope resource, draft, staging or production")
	}
}

func (a *App) asacLeaseCommands() {
	for _, kind := range []string{"agent", "network"} {
		var scope, draft, operation, workflow, lease, reason string
		var ttl int
		var fence int64
		command := &cobra.Command{Use: "lease REFERENCE ACTION", Short: "Reserve an authoring or environment workflow with bounded fencing", Args: cobra.ExactArgs(2), Long: "Actions: show, acquire, renew, release, break, reconcile. Resource scope reserves authoring across Draft lines; draft scope reserves one selected isolated Draft (or --draft UUID). Staging/Production leases reserve future selection operations, not Runs. Registered aliases keep workflow proofs privately and attach them to isolated Draft writes. Same credentials do not identify the same workflow. Expired proofs are never silently discarded. Native UUID operations stay independent of project config and require explicit operation/workflow/proof flags for writes. Reconcile only reads the original operation; it never repeats a mutation. Administrative break requires --yes, --reason and the exact current lease/fencing token.", Example: "woobe agent '@support' lease acquire --scope draft --ttl 60\nwoobe agent '@support' lease renew --scope draft --ttl 120\nwoobe agent '@support' lease release --scope draft", RunE: func(cmd *cobra.Command, args []string) error {
			action := args[1]
			switch action {
			case "show", "acquire", "renew", "release", "break", "reconcile":
			default:
				return output.New(2, "Use lease show, acquire, renew, release, break or reconcile")
			}
			if a.File != "" {
				return output.New(2, "Lease commands accept explicit flags, not --file")
			}
			if action != "acquire" && action != "renew" && cmd.Flags().Changed("ttl") {
				return output.New(2, "--ttl applies only to acquire/renew")
			}
			if action != "break" && reason != "" {
				return output.New(2, "--reason applies only to administrative break")
			}
			if action == "show" && (operation != "" || workflow != "" || lease != "" || fence != 0) || action == "reconcile" && (workflow != "" || lease != "" || fence != 0) {
				return output.New(2, "Read-only lease observation cannot adopt workflow proof flags")
			}
			if (action == "acquire" || action == "renew") && ttl <= 0 {
				return output.New(2, "Lease TTL must be positive")
			}
			if action == "break" && (len(strings.TrimSpace(reason)) < 3 || !a.Yes && !a.DryRun) {
				return output.New(2, "Administrative break requires --yes and a meaningful --reason")
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
					return output.New(2, err.Error())
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
				if !uuidReference(id) {
					return output.New(2, "Recover the native binding before acquiring a workflow lease")
				}
				if scope == "draft" && draft == "" {
					raw, err := c.ReadOperationalFile(asacPrivatePath(c, state, resource.UID, "draft"), 1<<20)
					var selected asacDraftObservation
					if err != nil || json.Unmarshal(raw, &selected) != nil || selected.ResourceID != id || selected.ResourceUID != resource.UID || !uuidReference(selected.DraftID) {
						return output.New(2, "Select an isolated Draft first, or use --draft UUID")
					}
					draft = selected.DraftID
				}
			}
			if err := resourceID(id); err != nil {
				return err
			}
			if _, err := a.resolve(); err != nil {
				return err
			}
			scopeKey, err := asacLeaseScope(scope, draft)
			if err != nil {
				return err
			}
			base := fmt.Sprintf("/projects/%s/%ss/%s/asac", url.PathEscape(a.Project), kind, url.PathEscape(id))
			payload := map[string]any{"scope": scope}
			if draft != "" {
				payload["draft_id"] = draft
			}
			var pending asacPending
			pendingPath := ""
			if c != nil {
				pendingPath = asacPrivatePath(c, state, resource.UID, "pending")
			}
			if action == "reconcile" && c != nil {
				raw, err := c.ReadOperationalFile(pendingPath, 16<<20)
				if err != nil || decodeASaCPending(raw, &pending) != nil || !uuidReference(pending.OperationID) || !strings.HasPrefix(pending.Path, base+"/leases/") {
					return output.New(9, "No original lease operation is recorded")
				}
				if operation != "" && operation != pending.OperationID {
					return output.New(9, "Operation differs from the original lease write")
				}
				operation = pending.OperationID
				payload = pending.Body
				scopeKey, err = asacLeaseScope(packagefmt.Text(payload["scope"]), packagefmt.Text(payload["draft_id"]))
				if err != nil {
					return err
				}
			}
			if action != "show" && action != "reconcile" {
				if c != nil {
					raw, readErr := c.ReadOperationalFile(pendingPath, 16<<20)
					if readErr == nil {
						if !clearedASaCPending(raw) {
							return output.New(9, "An ASaC write is unresolved; reconcile its original operation first")
						}
					} else if !os.IsNotExist(readErr) {
						return readErr
					}
				}
				if operation == "" && c != nil {
					operation, err = devworkspace.NewID()
					if err != nil {
						return err
					}
				}
				if !uuidReference(operation) {
					return output.New(2, "Native writes require an explicit --operation UUID")
				}
				payload["operation_id"] = operation
				if action == "acquire" {
					if lease != "" || fence != 0 {
						return output.New(2, "Acquire creates a new lease; omit --lease and --fencing-token")
					}
					if workflow == "" && c != nil {
						workflow, err = devworkspace.NewID()
						if err != nil {
							return err
						}
					}
					if !uuidReference(workflow) {
						return output.New(2, "Acquire requires --workflow UUID outside a registered alias")
					}
					payload["workflow_id"] = workflow
				}
				if action == "renew" || action == "release" {
					if c != nil && lease == "" && workflow == "" && fence == 0 {
						observed, err := readLeaseObservations(c, state, resource.UID, id)
						if err != nil {
							return err
						}
						receipt := observed.Leases[scopeKey]
						if receipt == nil {
							return output.New(2, "No owned workflow proof is recorded for this scope")
						}
						lease = packagefmt.Text(receipt["lease_id"])
						workflow = packagefmt.Text(receipt["workflow_id"])
						fence, _ = asacCounter(receipt["fencing_token"])
					}
					if !uuidReference(workflow) {
						return output.New(2, "Present the original --workflow UUID")
					}
					payload["workflow_id"] = workflow
				}
				if action != "acquire" {
					if !uuidReference(lease) || fence <= 0 {
						return output.New(2, "Present the exact --lease UUID and positive --fencing-token")
					}
					payload["lease_id"], payload["fencing_token"] = lease, fence
				}
				if action == "break" {
					payload["reason"] = reason
				}
				if action == "acquire" || action == "renew" {
					payload["ttl_seconds"] = ttl
				}
			}
			path, method := base+"/leases", "GET"
			if action == "reconcile" {
				if !uuidReference(operation) {
					return output.New(2, "Reconcile requires the original --operation UUID")
				}
				path = base + "/operations/" + url.PathEscape(operation)
			} else if action != "show" {
				method = "POST"
				path += "/" + action
			}
			if a.DryRun {
				return a.emit(map[string]any{"method": method, "path": path, "body": payload, "executed": false})
			}
			control, err := a.client()
			if err != nil {
				return err
			}
			if method == "POST" {
				response, _, capabilityErr := control.Request(cmd.Context(), "GET", fmt.Sprintf("/projects/%s/packages/capabilities", url.PathEscape(a.Project)), nil, nil)
				if capabilityErr != nil {
					return capabilityErr
				}
				capability, capabilityErr := developmentResponseData(response)
				if capabilityErr != nil {
					return capabilityErr
				}
				protocol := packagefmt.Object(capability["asac"])
				if protocol["schema_version"] != "1.0" || protocol["operation_leases"] != true || protocol["lease_clock"] != "database" || protocol["lease_fencing_scope"] != "owner-authoring-transaction@1" {
					return output.New(9, "Backend does not advertise compatible database-clock workflow leases")
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
						return output.New(10, "Cannot retain the lease operation before submission")
					}
				}
			} else if action == "show" {
				query = url.Values{"scope": {scope}}
				if draft != "" {
					query.Set("draft_id", draft)
				}
			}
			response, _, err := control.Request(cmd.Context(), method, path, query, encoded)
			if err != nil {
				if c != nil && method == "POST" {
					normalized := output.Normalize(err)
					if normalized.Outcome == "rejected" || normalized.Outcome == "not_attempted" {
						if clearErr := c.WriteOperationalFile(pendingPath, []byte("{}")); clearErr != nil {
							return output.New(10, "Rejected lease write remains locally pending")
						}
					}
				}
				return err
			}
			data, err := developmentResponseData(response)
			if err != nil {
				return err
			}
			if action == "show" {
				if data["project_id"] != a.Project || data["resource_id"] != id || data["scope"] != scopeKey || data["clock_authority"] != "database" {
					return output.New(9, "Lease observation differs from the requested destination")
				}
				return a.emit(data)
			}
			if action == "reconcile" {
				if data["operation_id"] != operation || data["state"] != "committed" {
					return output.New(9, "Original lease acceptance is not proven committed")
				}
				data = packagefmt.Object(data["result"])
				if c == nil {
					scopeKey = packagefmt.Text(data["scope"])
				}
			}
			if err = validateLeaseReceipt(data, a.Project, id, operation, scopeKey, payload); err != nil {
				return err
			}
			originalAction := action
			if action == "reconcile" {
				if c != nil {
					originalAction = strings.TrimPrefix(pending.Path, base+"/leases/")
				} else {
					originalAction = map[string]string{"active": "acquire", "released": "release", "broken": "break"}[packagefmt.Text(data["state"])]
				}
			}
			if err = validateLeaseAction(data, originalAction); err != nil {
				return err
			}
			if c != nil {
				if err = storeLeaseObservation(c, state, resource.UID, id, data); err != nil {
					return output.New(10, "Lease accepted; reconcile to repair its private workflow proof")
				}
				if err = c.WriteOperationalFile(pendingPath, []byte("{}")); err != nil {
					return output.New(10, "Lease accepted; original operation remains pending locally")
				}
			}
			return a.emit(data)
		}}
		command.Flags().StringVar(&scope, "scope", "resource", "Reservation scope: resource, draft, staging or production")
		command.Flags().StringVar(&draft, "draft", "", "Isolated Draft UUID; selected Draft used with registered --scope draft")
		command.Flags().StringVar(&operation, "operation", "", "Stable original operation UUID; generated before registered writes")
		command.Flags().StringVar(&workflow, "workflow", "", "Original workflow UUID; generated only for registered acquire")
		command.Flags().StringVar(&lease, "lease", "", "Exact lease UUID for expert renewal, release or administrative break")
		command.Flags().Int64Var(&fence, "fencing-token", 0, "Exact positive concurrency counter; not an authentication token")
		command.Flags().IntVar(&ttl, "ttl", 60, "Requested lease duration in seconds, bounded by server policy")
		command.Flags().StringVar(&reason, "reason", "", "Audit reason for administrative break")
		a.group("develop " + kind).AddCommand(command)
	}
}
