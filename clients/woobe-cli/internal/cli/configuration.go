package cli

import (
	"encoding/json"
	"fmt"
	"net/url"
	"regexp"
	"strconv"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
)

var configurationKeyPattern = regexp.MustCompile(`^[A-Za-z_][A-Za-z0-9_]{0,127}$`)

type configurationReadinessFailure struct {
	Data  map[string]any
	Cause *output.Error
}

func (f *configurationReadinessFailure) Error() string { return f.Cause.Error() }
func (f *configurationReadinessFailure) Unwrap() error { return f.Cause }

func (a *App) configurationCommands() {
	group := a.group("project configuration")
	group.Short = "Declare remote configuration and inspect Environment metadata"
	group.Long = "Declare keys without values. An authorized operator configures values in Project → Environments. These commands never read a local secret store or display configured values. Configuration does not publish, deploy or execute an Agent. The explicit test command contacts the configured provider or MCP server."
	group.Example = "woobe project configuration declare PRIMARY_API_KEY --kind secret --format token\nwoobe project configuration list --env draft\nwoobe project configuration usage KEY_UUID"
	var kind, format, description string
	declare := &cobra.Command{Use: "declare KEY", Short: "Declare a key without supplying its value", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
		if !configurationKeyPattern.MatchString(args[0]) || (kind != "secret" && kind != "value") {
			return output.New(2, "Use an identifier key and --kind secret or value")
		}
		switch format {
		case "string", "token", "json", "pem", "url":
		default:
			return output.New(2, "Use --format string, token, json, pem or url")
		}
		if a.File != "" {
			return output.New(2, "Declaration does not accept --file or secret values")
		}
		return a.configurationCall(cmd, "POST", "/keys", nil, map[string]any{"key": args[0], "kind": kind, "value_format": format, "description": description})
	}}
	declare.Flags().StringVar(&kind, "kind", "secret", "secret or value")
	declare.Flags().StringVar(&format, "format", "token", "Declared material format (no material is sent)")
	declare.Flags().StringVar(&description, "description", "", "Purpose of this key; never include its value")
	group.AddCommand(declare)
	var environment, status, search string
	var offset, limit int
	list := &cobra.Command{Use: "list", Short: "List key status in one Environment without reading values", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		if environment != "draft" && environment != "staging" && environment != "production" {
			return output.New(2, "Use --env draft, staging or production")
		}
		switch status {
		case "all", "configured", "missing", "legacy", "attention":
		default:
			return output.New(2, "Unsupported configuration status filter")
		}
		if offset < 0 || limit < 1 || limit > 200 {
			return output.New(2, "Use --limit 1..200 and a nonnegative --offset")
		}
		return a.configurationCall(cmd, "GET", "/keys", url.Values{"environment": {environment}, "status": {status}, "search": {search}, "offset": {fmt.Sprint(offset)}, "limit": {fmt.Sprint(limit)}}, nil)
	}}
	list.Flags().StringVar(&environment, "env", "draft", "Environment to inspect")
	list.Flags().StringVar(&status, "status", "all", "all, configured, missing, legacy or attention")
	list.Flags().StringVar(&search, "search", "", "Filter key name or description")
	list.Flags().IntVar(&offset, "offset", 0, "Number of keys to skip")
	list.Flags().IntVar(&limit, "limit", 50, "Maximum keys in this page (1..200)")
	group.AddCommand(list)
	var usageOffset int
	usage := &cobra.Command{Use: "usage KEY_UUID", Short: "Inspect retained consumers of a configuration key", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
		if !uuidReference(args[0]) || usageOffset < 0 {
			return output.New(2, "Use a key UUID and a nonnegative --offset")
		}
		return a.configurationCall(cmd, "GET", "/keys/"+args[0]+"/usage", url.Values{"offset": {fmt.Sprint(usageOffset)}, "limit": {"50"}}, nil)
	}}
	usage.Flags().IntVar(&usageOffset, "offset", 0, "Number of consumers to skip")
	group.AddCommand(usage)
	var bindingKey, authType, bindingRoute string
	var bindingFields []string
	bind := &cobra.Command{Use: "bind provider|tool UUID", Short: "Bind an existing resource to declared remote keys without reading values", Args: cobra.ExactArgs(2), RunE: func(cmd *cobra.Command, args []string) error {
		kind := args[0]
		if kind == "provider" {
			kind = "provider_credential"
		}
		if (kind != "provider_credential" && kind != "tool") || !uuidReference(args[1]) {
			return output.New(2, "Use bind provider|tool UUID")
		}
		if bindingRoute != "" && (kind != "tool" || len(bindingRoute) > 128 || strings.ContainsAny(bindingRoute, "\r\n\x00")) {
			return output.New(2, "Use --route with a stable HTTP Tool route ID (1..128 characters)")
		}
		fields := map[string]any{}
		requestedFields := append([]string(nil), bindingFields...)
		if bindingKey != "" {
			if authType != "api_key" || len(bindingFields) != 0 {
				return output.New(2, "Use --key alone with --type api_key, or explicit --field FIELD=KEY entries")
			}
			requestedFields = []string{"api_key=" + bindingKey}
		}
		for _, raw := range requestedFields {
			field, key, ok := strings.Cut(raw, "=")
			if !ok || !regexp.MustCompile(`^[A-Za-z][A-Za-z0-9_-]{0,127}$`).MatchString(field) || !configurationKeyPattern.MatchString(key) {
				return output.New(2, "Use --field FIELD=DECLARED_KEY; never pass secret values")
			}
			if _, duplicate := fields[field]; duplicate {
				return output.New(2, "Each authentication field may be bound only once")
			}
			fields[field] = map[string]any{"source": "project_environment", "key": key}
		}
		valid := false
		switch authType {
		case "api_key":
			valid = len(fields) == 1 && fields["api_key"] != nil
		case "bearer":
			valid = kind == "tool" && len(fields) == 1 && fields["token"] != nil
		case "basic":
			valid = kind == "tool" && len(fields) == 2 && fields["username"] != nil && fields["password"] != nil
		case "headers":
			valid = kind == "tool" && len(fields) > 0 && len(fields) <= 16
		case "none":
			valid = kind == "tool" && len(fields) == 0
		}
		if !valid {
			return output.New(2, "Authentication type and declared field references are incompatible")
		}
		body := map[string]any{"authentication": map[string]any{"type": authType, "fields": fields}}
		if bindingRoute != "" {
			body["route_id"] = bindingRoute
		}
		return a.configurationCall(cmd, "PUT", "/bindings/"+kind+"/"+args[1], nil, body)
	}}
	bind.Flags().StringVar(&bindingKey, "key", "", "Declared key name for api_key authentication (not its value)")
	bind.Flags().StringVar(&authType, "type", "api_key", "api_key; Tools also support bearer, basic, headers or none")
	bind.Flags().StringArrayVar(&bindingFields, "field", nil, "Bind FIELD=DECLARED_KEY (repeatable; never values)")
	bind.Flags().StringVar(&bindingRoute, "route", "", "Bind only this stable HTTP group route ID")
	bind.Example = "woobe project configuration bind provider UUID --key PRIMARY_API_KEY\nwoobe project configuration bind tool UUID --type basic --field username=TOOL_USER --field password=TOOL_PASSWORD\nwoobe project configuration bind tool UUID --route orders --type bearer --field token=ORDERS_TOKEN"
	group.AddCommand(bind)
	var testEnvironment string
	test := &cobra.Command{Use: "test provider|tool UUID", Short: "Explicitly test a provider connection or prepare an MCP Tool",
		Long: "Contact the configured provider or MCP server with values resolved by Woobe for the selected Environment. MCP discovery is saved if the Tool revision and your permission still match. This may incur provider traffic; it never runs an Agent or deploys a resource. HTTP Tool operations are not executed by this command.", Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			kind := args[0]
			if kind == "provider" {
				kind = "provider_credential"
			}
			if (kind != "provider_credential" && kind != "tool") || !uuidReference(args[1]) {
				return output.New(2, "Use test provider|tool UUID (Tools must use MCP)")
			}
			if testEnvironment != "draft" && testEnvironment != "staging" && testEnvironment != "production" {
				return output.New(2, "Use --env draft, staging or production")
			}
			return a.configurationCall(cmd, "POST", "/tests/"+kind+"/"+args[1], url.Values{"environment": {testEnvironment}}, map[string]any{"environment": testEnvironment})
		}}
	test.Flags().StringVar(&testEnvironment, "env", "draft", "Environment whose values and use approvals authorize the external test")
	test.Example = "woobe project configuration test provider UUID --env staging\nwoobe project configuration test tool UUID --env draft"
	group.AddCommand(test)
	var summaryEnvironment, summaryCursor string
	var summaryLimit int
	summary := &cobra.Command{Use: "summary", Short: "Summarize current Agent and Network configuration in one Environment",
		Long: "Inspect current selections without reading values, running external tests or deploying. Each page inspects at most --limit Agents and --limit Networks. Follow next_cursor with --cursor. Page counts are not global totals, and the final page does not qualify earlier pages. Partial observations return exit 9; a complete blocked Project returns exit 6. Use check for authoritative evidence for an exact target or Candidate.", Args: cobra.NoArgs,
		RunE: func(cmd *cobra.Command, _ []string) error {
			if summaryEnvironment != "draft" && summaryEnvironment != "staging" && summaryEnvironment != "production" {
				return output.New(2, "Use --env draft, staging or production")
			}
			if summaryLimit < 1 || summaryLimit > 200 || len(summaryCursor) > 1024 {
				return output.New(2, "Use --limit 1..200 and the next_cursor returned by the same Project and Environment")
			}
			query := url.Values{"environment": {summaryEnvironment}}
			if cmd.Flags().Changed("limit") {
				query.Set("limit", strconv.Itoa(summaryLimit))
			}
			if summaryCursor != "" {
				query.Set("cursor", summaryCursor)
			}
			return a.configurationCall(cmd, "GET", "/summary", query, nil)
		}}
	summary.Flags().StringVar(&summaryEnvironment, "env", "draft", "Environment whose current selections are inspected")
	summary.Flags().IntVar(&summaryLimit, "limit", 50, "Maximum Agents and Networks to inspect per page (1..200)")
	summary.Flags().StringVar(&summaryCursor, "cursor", "", "Continue with next_cursor from this Project and Environment")
	summary.Example = "woobe project configuration summary --env draft\nwoobe project configuration summary --env staging --limit 25\nwoobe project configuration summary --env staging --cursor CURSOR"
	group.AddCommand(summary)
	var checkEnvironment, version string
	check := &cobra.Command{Use: "check agent|network|provider|tool UUID", Short: "Check remote configuration for the selected target and Environment",
		Long: "Inspect the backend-selected dependency closure without decrypting values or contacting providers. Missing, unauthorized or unresolved dependencies return a nonzero exit status. External credentials are not tested, and no Run or deployment is started.", Args: cobra.ExactArgs(2),
		RunE: func(cmd *cobra.Command, args []string) error {
			kind := args[0]
			if kind == "provider" {
				kind = "provider_credential"
			}
			if (kind != "agent" && kind != "network" && kind != "provider_credential" && kind != "tool") || !uuidReference(args[1]) {
				return output.New(2, "Use check agent|network|provider|tool UUID")
			}
			if checkEnvironment != "draft" && checkEnvironment != "staging" && checkEnvironment != "production" {
				return output.New(2, "Use --env draft, staging or production")
			}
			query := url.Values{"environment": {checkEnvironment}}
			if version != "" {
				if (kind != "agent" && kind != "network") || !uuidReference(version) {
					return output.New(2, "Use --version-id UUID only with an Agent or Network")
				}
				query.Set("version_id", version)
			}
			return a.configurationCall(cmd, "GET", "/readiness/"+kind+"/"+args[1], query, nil)
		}}
	check.Flags().StringVar(&checkEnvironment, "env", "draft", "Environment whose configured values and grants are checked")
	check.Flags().StringVar(&version, "version-id", "", "Inspect an exact retained Agent/Network snapshot instead of the current selection")
	check.Example = "woobe project configuration check agent UUID --env staging\nwoobe project configuration check network UUID --env production"
	group.AddCommand(check)
}

func (a *App) configurationCall(cmd *cobra.Command, method, suffix string, query url.Values, body map[string]any) error {
	if a.File != "" {
		return output.New(2, "This configuration command does not accept --file")
	}
	if len(a.Query) != 0 {
		return output.New(2, "Use the explicit configuration flags instead of --query")
	}
	if _, err := a.resolve(); err != nil {
		return err
	}
	if err := resourceID(a.Project); err != nil {
		return err
	}
	path := "/core/projects/" + url.PathEscape(a.Project) + "/configuration"
	if a.DryRun {
		return a.emit(map[string]any{"method": method, "path": path + suffix, "query": query, "body": body, "executed": false})
	}
	control, err := a.client()
	if err != nil {
		return err
	}
	capQuery := url.Values{}
	if query.Get("environment") != "" {
		capQuery.Set("environment", query.Get("environment"))
	}
	raw, _, err := control.Request(cmd.Context(), "GET", path+"/capabilities", capQuery, nil)
	if err != nil {
		return output.New(9, "Server configuration capability is unavailable; upgrade Woobe or check project:environment:read. No local secrets were used")
	}
	capabilities, err := developmentResponseData(raw)
	if err != nil || capabilities["schema_version"] != "project_configuration.v1" || capabilities["declaration_without_value"] != true {
		return output.New(9, "Server does not support project_configuration.v1; no configuration mutation was sent")
	}
	if strings.HasPrefix(suffix, "/readiness/") && capabilities["target_readiness"] != true {
		return output.New(9, "Server does not advertise target configuration readiness; upgrade Woobe before checking this target")
	}
	if suffix == "/summary" && capabilities["project_summary"] != true {
		return output.New(9, "Server does not advertise Project configuration summaries; use check for an exact target")
	}
	if suffix == "/summary" && (query.Has("limit") || query.Has("cursor")) && capabilities["project_summary_pagination"] != true {
		return output.New(9, "Server does not advertise Project summary pagination; upgrade Woobe or check an exact target")
	}
	if strings.HasPrefix(suffix, "/tests/") && capabilities["external_validation"] != true {
		return output.New(9, "Server does not advertise external configuration validation; no external test was requested")
	}
	if strings.HasPrefix(suffix, "/bindings/") && method == "PUT" {
		if capabilities["binding_updates"] != true {
			return output.New(9, "Server does not support configuration binding updates; no mutation was sent")
		}
		var bindingQuery url.Values
		if route, _ := body["route_id"].(string); route != "" {
			if capabilities["route_authentication_bindings"] != true {
				return output.New(9, "Server does not advertise route authentication bindings; no mutation was sent")
			}
			bindingQuery = url.Values{"route_id": {route}}
		}
		current, _, readErr := control.Request(cmd.Context(), "GET", path+suffix, bindingQuery, nil)
		if readErr != nil {
			return readErr
		}
		metadata, parseErr := developmentResponseData(current)
		if parseErr != nil || configurationContainsMaterial(metadata) {
			return output.New(9, "Server returned invalid configuration binding metadata")
		}
		revision, ok := metadata["revision"].(string)
		if !ok || revision == "" {
			return output.New(9, "Server did not provide a binding revision; no mutation was sent")
		}
		body["expected_revision"] = revision
	}
	var encoded []byte
	if body != nil {
		encoded, err = json.Marshal(body)
		if err != nil {
			return err
		}
	}
	response, _, err := control.Request(cmd.Context(), method, path+suffix, query, encoded)
	if err != nil {
		return err
	}
	data, err := developmentResponseData(response)
	if err != nil {
		return err
	}
	// Configuration is a metadata-only contract. Refuse accidental material
	// fields before any renderer, including JSON and --wide, sees the response.
	if configurationContainsMaterial(data) {
		return output.New(9, "Server returned material in a metadata-only configuration response")
	}
	if suffix == "/summary" {
		if !validConfigurationSummary(data, query.Get("environment")) {
			return output.New(9, "Server returned incomplete Project configuration evidence")
		}
		if query.Has("cursor") && data["scope"] != "current_selections_page" {
			return output.New(9, "Server did not return the requested Project summary page")
		}
	}
	if strings.HasPrefix(suffix, "/readiness/") || suffix == "/summary" {
		switch data["state"] {
		case "ready", "ready_with_notices":
		case "blocked":
			return &configurationReadinessFailure{Data: data, Cause: output.New(6, "Configuration is blocked; review missing values and use approvals in Project → Environments")}
		case "unknown":
			return &configurationReadinessFailure{Data: data, Cause: output.New(9, "Configuration readiness is unknown; review unresolved dependencies before execution")}
		default:
			return output.New(9, "Server returned an unrecognized readiness state")
		}
	}
	if strings.HasPrefix(suffix, "/tests/") {
		switch data["state"] {
		case "valid", "ready":
		case "unknown":
			return &configurationReadinessFailure{Data: data, Cause: output.New(9, "External configuration validation is inconclusive")}
		default:
			return &configurationReadinessFailure{Data: data, Cause: output.New(6, "The connection is not ready; review configuration and discovery status")}
		}
	}
	return a.emit(data)
}

func configurationContainsMaterial(value any) bool {
	switch node := value.(type) {
	case map[string]any:
		for key, child := range node {
			switch key {
			case "value", "stored_value", "ciphertext", "encrypted_secret", "secret_value":
				if child != nil {
					return true
				}
			}
			if configurationContainsMaterial(child) {
				return true
			}
		}
	case []any:
		for _, child := range node {
			if configurationContainsMaterial(child) {
				return true
			}
		}
	}
	return false
}

func validConfigurationSummary(data map[string]any, environment string) bool {
	complete, ok := data["complete"].(bool)
	scope := data["scope"]
	if !ok || data["environment"] != environment || (scope != "current_selections" && scope != "current_selections_page") || (!complete && data["state"] != "unknown") {
		return false
	}
	if scope == "current_selections_page" {
		pageComplete, pageOK := data["page_complete"].(bool)
		hasNext, nextOK := data["has_next"].(bool)
		cursor, cursorOK := data["next_cursor"].(string)
		if complete || data["state"] != "unknown" || !pageOK || !nextOK ||
			(hasNext && (!cursorOK || cursor == "" || len(cursor) > 1024)) ||
			(!hasNext && data["next_cursor"] != nil) {
			return false
		}
		pageState := data["page_state"]
		if (pageState != "ready" && pageState != "ready_with_notices" && pageState != "blocked" && pageState != "unknown") ||
			(!pageComplete && pageState != "unknown") {
			return false
		}
	}
	if scope == "current_selections" && data["has_next"] == true {
		return false
	}
	for _, name := range []string{"inspected_target_count", "unselected_target_count", "affected_target_count", "blocked_key_count", "missing_key_count", "required_key_count", "affected_consumer_count"} {
		raw, err := json.Marshal(data[name])
		if err != nil {
			return false
		}
		count, err := strconv.ParseUint(string(raw), 10, 64)
		if err != nil || count > 1<<53-1 {
			return false
		}
	}
	return true
}
