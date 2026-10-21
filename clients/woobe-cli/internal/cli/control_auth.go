package cli

import (
	"bufio"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"runtime"
	"strconv"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"golang.org/x/term"
)

type controlProject struct {
	ID          string   `json:"id"`
	Name        string   `json:"name"`
	Slug        string   `json:"slug"`
	Status      string   `json:"status"`
	Eligible    bool     `json:"eligible"`
	Permissions []string `json:"permissions"`
}
type controlIdentity struct {
	Key            map[string]any `json:"key"`
	SchemaVersion  string         `json:"schema_version"`
	CredentialType string         `json:"credential_type"`
	Workspace      struct {
		ID     string `json:"id"`
		Name   string `json:"name"`
		Status string `json:"status"`
	} `json:"workspace"`
	Projects []controlProject `json:"projects"`
}

func inspectControl(cmd *cobra.Command, client *controlplane.Client) (controlIdentity, error) {
	var identity controlIdentity
	v, _, err := client.Request(cmd.Context(), "GET", "/identity/control-key/me", nil, nil)
	if err != nil {
		if output.Normalize(err).Status == 404 {
			return identity, output.New(9, "This Woobe API does not support CLI Key discovery. Upgrade the backend before logging in.")
		}
		return identity, err
	}
	b, err := json.Marshal(v)
	if err != nil {
		return identity, err
	}
	var envelope struct {
		Success bool            `json:"success"`
		Data    controlIdentity `json:"data"`
	}
	if err = json.Unmarshal(b, &envelope); err != nil {
		return identity, output.New(9, "Invalid CLI Key discovery response")
	}
	identity = envelope.Data
	if !envelope.Success || identity.SchemaVersion != "1" || identity.CredentialType != "control" || identity.Workspace.ID == "" || identity.Workspace.Status != "active" {
		return identity, output.New(9, "Invalid CLI Key identity or inactive Workspace")
	}
	return identity, nil
}
func isConnectionCredential(v config.Context) bool {
	return v.AuthAPIURL != "" && strings.HasPrefix(v.Credential, "connection-")
}

func (a *App) savedConnection() (config.Config, string, config.Context, error) {
	c, e := config.Load(a.ConfigPath)
	if e != nil {
		return c, "", config.Context{}, e
	}
	name := a.ContextName
	if name == "" {
		name = os.Getenv("WOOBE_CONTEXT")
	}
	if name == "" {
		name = c.Current
	}
	v, ok := c.Contexts[name]
	if !ok {
		return c, name, v, output.New(2, "Create and use a Woobe context before logging in")
	}
	if a.APIURL != "" && strings.TrimRight(a.APIURL, "/") != strings.TrimRight(v.APIURL, "/") || os.Getenv("WOOBE_API_URL") != "" && a.APIURL == "" && strings.TrimRight(os.Getenv("WOOBE_API_URL"), "/") != strings.TrimRight(v.APIURL, "/") {
		return c, name, v, output.New(2, "Update the saved context API URL before authenticating")
	}
	return c, name, v, nil
}
func (a *App) selectControlProject(identity controlIdentity, selection, previous string) (string, error) {
	projects := []controlProject{}
	for _, p := range identity.Projects {
		if p.Eligible && p.Status == "active" && len(p.Permissions) > 0 {
			projects = append(projects, p)
		}
	}
	if selection != "" {
		matches := []controlProject{}
		for _, p := range projects {
			if selection == p.ID || selection == p.Name || selection == p.Slug {
				matches = append(matches, p)
			}
		}
		if len(matches) != 1 {
			return "", output.New(2, "Project selection must match exactly one eligible name, slug or ID")
		}
		return matches[0].ID, nil
	}
	for _, p := range projects {
		if p.ID == previous {
			return previous, nil
		}
	}
	if len(projects) == 0 {
		return "", nil
	}
	if len(projects) == 1 {
		return projects[0].ID, nil
	}
	f, ok := a.In.(*os.File)
	if a.NoInput || !ok || !term.IsTerminal(int(f.Fd())) {
		return "", nil
	}
	for i, p := range projects {
		fmt.Fprintf(a.Err, "%d. %q (%q)\n", i+1, p.Name, p.Slug)
	}
	fmt.Fprint(a.Err, "Select project (number, name or slug): ")
	line, e := bufio.NewReader(io.LimitReader(a.In, 4096)).ReadString('\n')
	if e != nil {
		return "", output.New(2, "Project selection was cancelled")
	}
	return a.controlProjectChoice(identity, projects, strings.TrimSpace(line))
}
func (a *App) controlProjectChoice(identity controlIdentity, projects []controlProject, choice string) (string, error) {
	if choice == "" {
		return "", output.New(2, "Choose a project number, name or slug")
	}
	if n, e := strconv.Atoi(choice); e == nil && n >= 1 && n <= len(projects) {
		return projects[n-1].ID, nil
	}
	return a.selectControlProject(identity, choice, "")
}

func (a *App) loginControl(cmd *cobra.Command, stdin bool, selection string) error {
	c, name, v, e := a.savedConnection()
	if e != nil {
		return e
	}
	if a.DryRun {
		return a.emit(map[string]any{"executed": false, "context": name, "api_url": v.APIURL, "method": "GET", "path": "/identity/control-key/me", "auth_mode": "cli-key"})
	}
	if a.File != "" || a.ValidateBody || a.ValidateParameters || a.SchemaSHA != "" {
		return output.New(2, "CLI Key login reads a masked prompt or --stdin; it does not accept JSON body files or canonical HTTP schema-validation flags")
	}
	var key []byte
	if stdin {
		key, e = io.ReadAll(io.LimitReader(a.In, 65537))
	} else {
		f, ok := a.In.(*os.File)
		if a.NoInput || !ok || !term.IsTerminal(int(f.Fd())) {
			return output.New(2, "Use --cli-key --stdin for noninteractive login")
		}
		fmt.Fprint(a.Err, "CLI Key: ")
		key, e = term.ReadPassword(int(f.Fd()))
		fmt.Fprintln(a.Err)
	}
	if e != nil {
		return output.New(2, "Cannot read CLI Key")
	}
	if len(key) > 65536 || strings.TrimSpace(string(key)) == "" {
		return output.New(2, "CLI Key must contain 1 to 65536 bytes")
	}
	token, e := credentialFromInput(key)
	if e != nil {
		return e
	}
	client, e := controlplane.New(v.APIURL, token, a.Timeout)
	if e != nil {
		return e
	}
	identity, e := inspectControl(cmd, client)
	if e != nil {
		return e
	}
	previous := v.Project
	if v.Workspace != identity.Workspace.ID {
		previous = ""
	}
	project, e := a.selectControlProject(identity, selection, previous)
	if e != nil {
		return e
	}
	nonce := make([]byte, 16)
	if _, e = rand.Read(nonce); e != nil {
		return e
	}
	ref := "connection-" + hex.EncodeToString(nonce)
	if e = a.store().Put(ref, token); e != nil {
		return e
	}
	oldManaged := isConnectionCredential(v)
	old := v.Credential
	v.Credential = ref
	v.AuthAPIURL = strings.TrimRight(v.APIURL, "/")
	v.Workspace = identity.Workspace.ID
	v.Project = project
	c.Contexts[name] = v
	if e = config.Save(a.ConfigPath, c); e != nil {
		_ = a.store().Remove(ref)
		return e
	}
	if oldManaged {
		if e = a.store().Remove(old); e != nil && !os.IsNotExist(e) {
			return output.New(3, "Login saved, but previous credential cleanup failed")
		}
	}
	a.Workspace = v.Workspace
	a.Project = v.Project
	state := "authenticated"
	eligible := 0
	for _, p := range identity.Projects {
		if p.Eligible {
			eligible++
		}
	}
	if project == "" && eligible > 1 {
		state = "project_selection_required"
	}
	return a.emit(map[string]any{"authenticated": true, "context": name, "state": state, "workspace": identity.Workspace, "project_id": project, "projects": identity.Projects})
}
func (a *App) controlAuthCommands() {
	login, _, _ := a.Root.Find([]string{"auth", "login"})
	original := login.RunE
	var key, stdin bool
	var selection string
	login.Flags().BoolVar(&key, "cli-key", false, "Authenticate this connection with a masked CLI Key")
	login.Flags().BoolVar(&stdin, "stdin", false, "Read CLI Key from stdin")
	login.Flags().StringVar(&selection, "select-project", "", "Eligible project name, slug or ID")
	login.RunE = func(cmd *cobra.Command, args []string) error {
		if key {
			return a.loginControl(cmd, stdin, selection)
		}
		if stdin || selection != "" {
			return output.New(2, "--stdin and --select-project require --cli-key")
		}
		return original(cmd, args)
	}
	status, _, _ := a.Root.Find([]string{"auth", "status"})
	humanStatus := status.RunE
	status.RunE = func(cmd *cobra.Command, args []string) error {
		client, e := a.client()
		if e != nil {
			return e
		}
		if client.Token == "" {
			return humanStatus(cmd, args)
		}
		identity, e := inspectControl(cmd, client)
		if e != nil {
			return e
		}
		v, e := a.resolve()
		if e != nil {
			return e
		}
		state := "authenticated"
		found := false
		for _, p := range identity.Projects {
			if p.ID == v.Project && p.Eligible {
				found = true
			}
		}
		eligibleCount := 0
		for _, p := range identity.Projects {
			if p.Eligible && p.Status == "active" && len(p.Permissions) > 0 {
				eligibleCount++
			}
		}
		if v.Project == "" && eligibleCount > 1 || v.Project != "" && (!found || v.Workspace != identity.Workspace.ID) {
			state = "project_selection_required"
		}
		method := "environment"
		if v.Credential != "" {
			method = "private-file"
			if runtime.GOOS == "windows" {
				method = "windows-credential-manager"
			}
		}
		connectionName := a.ContextName
		if connectionName == "" {
			connectionName = os.Getenv("WOOBE_CONTEXT")
		}
		if connectionName == "" {
			saved, _ := config.Load(a.ConfigPath)
			connectionName = saved.Current
		}
		return a.emit(map[string]any{"context": connectionName, "authenticated": true, "identity": map[string]any{"schema_version": identity.SchemaVersion, "credential_type": identity.CredentialType, "key_metadata": identity.Key, "workspace": identity.Workspace, "projects": identity.Projects}, "api_url": v.APIURL, "project_id": v.Project, "state": state, "credential_source": method})
	}
	logout, _, _ := a.Root.Find([]string{"auth", "logout"})
	humanLogout := logout.RunE
	var local bool
	logout.Flags().BoolVar(&local, "cli-key", false, "Remove local CLI Key authentication without revoking the key")
	logout.RunE = func(cmd *cobra.Command, args []string) error {
		if !local {
			return humanLogout(cmd, args)
		}
		c, name, v, e := a.savedConnection()
		if e != nil {
			return e
		}
		if a.DryRun {
			return a.emit(map[string]any{"executed": false, "context": name, "local_logout": true, "revoked": false})
		}
		managed := isConnectionCredential(v)
		ref := v.Credential
		v.Credential = ""
		v.AuthAPIURL = ""
		v.Workspace = ""
		v.Project = ""
		c.Contexts[name] = v
		if e = config.Save(a.ConfigPath, c); e != nil {
			return e
		}
		if managed {
			if e = a.store().Remove(ref); e != nil && !os.IsNotExist(e) {
				return e
			}
		}
		a.Workspace = ""
		a.Project = ""
		return a.emit(map[string]any{"logged_out": true, "context": name, "revoked": false})
	}
	a.register(Operation{Command: "auth key inspect", Method: "GET", Path: "/identity/control-key/me"})
	var projectName string
	selectCmd := &cobra.Command{Use: "select [name-or-slug]", Args: cobra.MaximumNArgs(1), Short: "Choose a project granted to this connection's CLI Key", RunE: func(cmd *cobra.Command, args []string) error {
		c, name, v, e := a.savedConnection()
		if e != nil {
			return e
		}
		if a.DryRun {
			return a.emit(map[string]any{"executed": false, "context": name, "method": "GET", "path": "/identity/control-key/me"})
		}
		client, e := a.client()
		if e != nil {
			return e
		}
		if client.Token == "" {
			return output.New(3, "Authenticate with a CLI Key first")
		}
		identity, e := inspectControl(cmd, client)
		if e != nil {
			return e
		}
		selection := projectName
		if len(args) > 0 {
			selection = args[0]
		}
		project, e := a.selectControlProject(identity, selection, "")
		if e != nil {
			return e
		}
		if project == "" {
			return a.emit(map[string]any{"state": "project_selection_required", "projects": identity.Projects})
		}
		v.Workspace = identity.Workspace.ID
		v.Project = project
		c.Contexts[name] = v
		if e = config.Save(a.ConfigPath, c); e != nil {
			return e
		}
		a.Workspace = v.Workspace
		a.Project = project
		return a.emit(map[string]string{"context": name, "project_id": project})
	}}
	selectCmd.Flags().StringVar(&projectName, "name", "", "Eligible project name, slug or ID")
	a.group("context project").AddCommand(selectCmd)
}
