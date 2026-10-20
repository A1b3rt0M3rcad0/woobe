package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"net/url"
	"regexp"
	"strings"
)

type Operation struct {
	Summary          string                          `json:"summary,omitempty"`
	Examples         []string                        `json:"examples,omitempty"`
	Details          string                          `json:"details,omitempty"`
	Pagination       controlplane.PaginationContract `json:"pagination,omitempty"`
	Kind             string                          `json:"kind"`
	Usage            string                          `json:"usage"`
	Flags            []FlagDescriptor                `json:"flags"`
	Command          string                          `json:"command"`
	ID               string                          `json:"operation_id"`
	Method           string                          `json:"method"`
	Path             string                          `json:"path"`
	Scope            string                          `json:"scope"`
	PermissionSource string                          `json:"permission_source"`
	Permission       string                          `json:"permission,omitempty"`
	Effect           string                          `json:"effect"`
	Status           string                          `json:"availability"`
	Body             bool                            `json:"body_required"`
	Secret           bool                            `json:"secret_emission"`
	Params           []string                        `json:"path_parameters"`
	QueryScope       string                          `json:"query_scope,omitempty"`
}

var placeholders = regexp.MustCompile(`\{([^}]+)\}`)

func (a *App) group(path string) *cobra.Command {
	cur := a.Root
	for _, part := range strings.Fields(path) {
		var found *cobra.Command
		for _, c := range cur.Commands() {
			if c.Name() == part {
				found = c
				break
			}
		}
		if found == nil {
			found = &cobra.Command{Use: part, Short: part + " operations"}
			cur.AddCommand(found)
		}
		cur = found
	}
	return cur
}
func (a *App) register(op Operation) {
	if op.Method == "GET" {
		op.Pagination = paginationForPath(op.Path)
	}
	op.PermissionSource = "historical_catalog_hint_not_effective_authority"
	if op.Permission == "" {
		op.Permission = permissionHint(op)
	}
	if op.ID == "" {
		op.ID = strings.ReplaceAll(op.Command, " ", ".")
	}
	if op.Status == "" {
		op.Status = "observed"
	}
	if op.Effect == "" {
		op.Effect = "read"
		if op.Method != "GET" {
			op.Effect = "mutation"
		}
	}
	for _, m := range placeholders.FindAllStringSubmatch(op.Path, -1) {
		if m[1] != "workspace_id" && m[1] != "project_id" {
			op.Params = append(op.Params, m[1])
		}
	}
	a.Registry = append(a.Registry, op)
	parts := strings.Fields(op.Command)
	g := a.group(strings.Join(parts[:len(parts)-1], " "))
	use := parts[len(parts)-1]
	for _, p := range op.Params {
		use += " <" + p + ">"
	}
	paramValues := map[string]*string{}
	pageOptions := paginationOptions{}
	cmd := &cobra.Command{Use: use, Short: op.Method + " " + op.Path, Args: func(_ *cobra.Command, args []string) error {
		count := 0
		for _, p := range op.Params {
			if paramValues[p] == nil || *paramValues[p] == "" {
				count++
			}
		}
		if len(args) != count {
			return output.New(2, "required resource IDs must be supplied positionally or by their named flags")
		}
		return nil
	}, RunE: func(cmd *cobra.Command, args []string) (err error) {
		defer func() {
			if err != nil && op.Method != "GET" && op.Method != "HEAD" && output.Normalize(err).Outcome == "" {
				err = notAttempted(err)
			}
		}()
		if op.Pagination != "" {
			if a.File != "" {
				return output.New(2, "paginated reads do not accept --file")
			}
			if e := pageOptions.validate(cmd, op.Pagination); e != nil {
				return e
			}
			q, e := a.query()
			if e != nil {
				return e
			}
			if e = pageOptions.query(q, op.Pagination); e != nil {
				return e
			}
		}
		_, e := a.resolve()
		if e != nil {
			return e
		}
		path := op.Path
		pathValues := map[string]string{}
		for _, p := range []struct{ name, value string }{{"workspace_id", a.Workspace}, {"project_id", a.Project}} {
			if strings.Contains(path, "{"+p.name+"}") {
				if e := resourceID(p.value); e != nil {
					return e
				}
				pathValues[p.name] = p.value
				path = strings.ReplaceAll(path, "{"+p.name+"}", url.PathEscape(p.value))
			}
		}
		argIndex := 0
		for _, p := range op.Params {
			value := ""
			if paramValues[p] != nil {
				value = *paramValues[p]
			}
			if value == "" {
				value = args[argIndex]
				argIndex++
			}
			referenceParameter := p
			if p == "version_id" && op.Command == "project agent prompt get" {
				referenceParameter = "prompt_id"
			}
			value, e = a.nativeReference(referenceParameter, value)
			if e != nil {
				return e
			}
			if e := resourceID(value); e != nil {
				return e
			}
			pathValues[p] = value
			path = strings.ReplaceAll(path, "{"+p+"}", url.PathEscape(value))
		}
		if op.Status == "proposed" && !a.DryRun {
			if e := a.requireAdvertised(cmd.Context(), op); e != nil {
				return e
			}
		}
		b, e := a.body(op.Body)
		if e != nil {
			return e
		}
		if e = validateMCPPermissions(op.Command, b); e != nil {
			return e
		}
		if op.QueryScope != "" {
			id := a.Project
			if op.QueryScope == "workspace_id" {
				id = a.Workspace
			}
			if id == "" {
				return output.New(2, op.QueryScope+" required")
			}
			if e := a.addScopeQuery(op.QueryScope, id); e != nil {
				return e
			}
		}
		if (op.Effect == "publication" || op.Effect == "execution" || strings.HasSuffix(op.Command, " revoke") || strings.HasSuffix(op.Command, " cancel")) && !a.Yes && !a.DryRun {
			return output.New(2, "operation requires --yes")
		}
		if (a.ValidateBody || a.ValidateParameters) && !a.DryRun {
			_, doc, _, def, e := a.serverOperation(cmd.Context(), op.Command)
			if e != nil {
				return notAttempted(e)
			}
			if a.ValidateBody {
				if e = validateBodySchema(doc, def, b); e != nil {
					return notAttempted(e)
				}
			}
			if a.ValidateParameters {
				q, e := a.query()
				if e != nil {
					return e
				}
				if op.Pagination != "" {
					if e = pageOptions.query(q, op.Pagination); e != nil {
						return e
					}
				}
				if e = validateOperationParameters(doc, op, pathValues, q); e != nil {
					return e
				}
			}
		}
		if op.Pagination != "" {
			return a.paginatedCall(cmd, path, pageOptions, op.Pagination)
		}
		return a.call(cmd, op.Method, path, b, op.Secret)
	}}
	if op.Pagination != "" {
		pageOptions.flags(cmd, op.Pagination)
	}
	for _, p := range op.Params {
		flag := strings.ReplaceAll(strings.TrimSuffix(p, "_id"), "_", "-")
		if a.Root.PersistentFlags().Lookup(flag) != nil {
			// Resource parameters must not shadow connection/configuration flags.
			flag = strings.ReplaceAll(p, "_", "-")
		}
		if cmd.Flags().Lookup(flag) == nil {
			value := new(string)
			paramValues[p] = value
			cmd.Flags().StringVar(value, flag, "", "Explicit "+p)
		}
	}
	g.AddCommand(cmd)
}
func (a *App) discoveryCommands() {
	help := &cobra.Command{Use: "help [command-path]", Short: "Discover command metadata", RunE: func(cmd *cobra.Command, args []string) error {
		if len(args) == 0 {
			return a.emit(a.Registry)
		}
		path := strings.Join(args, " ")
		if len(args) >= 2 && (args[0] == "agent" || args[0] == "network") {
			actions := map[string]string{"pull": "pull", "sync": "pull", "push": "push", "diff": "diff", "status": "status", "validate": "validate"}
			action := args[1]
			if len(args) >= 3 {
				action = args[2]
				if action == "update" {
					action = "push"
				}
			}
			if mapped := actions[action]; mapped != "" {
				path = "develop " + args[0] + " " + mapped
			}
		}
		for alias, canonical := range map[string]string{"agent": "project agent", "network": "project network", "control-key": "workspace control-key"} {
			if path == alias || strings.HasPrefix(path, alias+" ") {
				path = canonical + strings.TrimPrefix(path, alias)
				break
			}
		}
		for _, op := range a.Registry {
			if op.Command == path {
				return a.emit(op)
			}
		}
		command, remaining, err := a.Root.Find(strings.Fields(path))
		if err == nil && len(remaining) == 0 && command != a.Root && command.HasAvailableSubCommands() {
			commands := []map[string]string{}
			for _, child := range command.Commands() {
				if !child.Hidden {
					commands = append(commands, map[string]string{"name": child.Name(), "summary": child.Short, "usage": child.UseLine()})
				}
			}
			examples := []string{}
			if command.Example != "" {
				examples = strings.Split(command.Example, "\n")
			}
			return a.emit(map[string]any{"command": path, "usage": command.UseLine(), "summary": command.Short, "examples": examples, "commands": commands})
		}
		return output.New(2, "unknown operation; use woobe help or COMMAND --help")
	}}
	a.Root.SetHelpCommand(help)
	a.Root.AddCommand(help)
	var command, kind, manifestVersion string
	c := &cobra.Command{Use: "schema", RunE: func(*cobra.Command, []string) error {
		for _, op := range a.Registry {
			if op.Command == command {
				schema := commandSchema(op, kind)
				if kind != "input" && kind != "output" && kind != "document" {
					return output.New(2, "kind must be input, output or document")
				}
				if kind == "document" {
					if !strings.HasPrefix(command, "manifest ") {
						return output.New(2, "document schema is available for manifest commands")
					}
					switch manifestVersion {
					case "1":
						schema = manifest.Schema()
					case "2":
						schema = manifest.ResourceSchema()
					default:
						return output.New(2, "manifest-version must be 1 or 2")
					}
				}
				return a.writeOutput(a.Out, schema, nil, nil, nil)
			}
		}
		return output.New(2, "unknown operation")
	}}
	c.Flags().StringVar(&command, "command", "", "Canonical command path")
	c.Flags().StringVar(&manifestVersion, "manifest-version", "1", "Document format: 1 steps or 2 resources")
	c.Flags().StringVar(&kind, "kind", "input", "input, output or document")
	a.Root.AddCommand(c)
	a.doctorCommand()
}
