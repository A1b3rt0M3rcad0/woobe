package cli

import (
	"encoding/json"
	"net/url"
	"os"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
)

// Provider bindings are private destination identities, never author credentials.
func (a *App) developmentBindCommand() {
	command := &cobra.Command{Use: "bind provider REFERENCE UUID", Args: cobra.ExactArgs(3), Short: "Bind a local Provider to a verified native credential", Long: "Read the current Project credential catalog and bind an active matching Provider in private .state. This does not create or rotate credentials. It rejects reassignment and duplicate identities; API keys never enter author YAML.", Example: "woobe provider list\nwoobe resources bind provider @openai UUID", RunE: func(cmd *cobra.Command, args []string) error {
		if devworkspace.CanonicalKind(args[0]) != "Provider" {
			return output.New(2, "bind currently accepts provider; Agent and Network use pull to capture complete native evidence")
		}
		if err := resourceID(args[2]); err != nil {
			return err
		}
		c, err := a.developmentConfig(true)
		if err != nil {
			return err
		}
		unlock, err := c.Lock()
		if err != nil {
			return output.New(2, err.Error())
		}
		defer unlock()
		c, err = devworkspace.Load(c.File)
		if err != nil {
			return output.New(2, err.Error())
		}
		resource, err := c.Resolve("Provider", args[1])
		if err != nil {
			return output.New(2, err.Error())
		}
		graph, err := devworkspace.LoadGraph(c)
		if err != nil {
			return output.New(2, err.Error())
		}
		if a.ContextName == "" && os.Getenv("WOOBE_CONTEXT") == "" {
			a.ContextName = c.Context
		}
		connection, err := a.resolve()
		if err != nil {
			return err
		}
		state, err := c.ReadState(strings.TrimRight(connection.APIURL, "/"), connection.Workspace, connection.Project)
		if err != nil {
			return output.New(2, err.Error())
		}
		if existing := state.Credentials[resource.Key]; existing != "" && existing != args[2] {
			return output.New(6, "Provider is already bound to another identity in this destination; create a distinct Provider instead")
		}
		for key, id := range state.Credentials {
			if key != resource.Key && id == args[2] {
				return output.New(6, "Native credential is already registered as "+key+"; reuse that Provider")
			}
		}
		client, err := a.client()
		if err != nil {
			return err
		}
		response, _, err := client.Request(cmd.Context(), "GET", "/ai/credentials", url.Values{"project_id": {connection.Project}}, nil)
		if err != nil {
			return err
		}
		var envelope struct {
			Data []struct {
				ID       string `json:"id"`
				Project  string `json:"project_id"`
				Provider string `json:"provider"`
				Status   string `json:"status"`
			} `json:"data"`
		}
		encoded, encodeErr := json.Marshal(response)
		if encodeErr != nil {
			return output.New(9, "Invalid native credential catalog")
		}
		if err = json.Unmarshal(encoded, &envelope); err != nil {
			return output.New(9, "Invalid native credential catalog")
		}
		spec, _ := graph.Nodes[resource.Key].Document["spec"].(map[string]any)
		found := false
		for _, entry := range envelope.Data {
			if entry.ID == args[2] {
				if entry.Project != connection.Project || entry.Status != "active" || entry.Provider != spec["provider"] {
					return output.New(6, "Credential must be active in this Project and match the author Provider")
				}
				found = true
			}
		}
		if !found {
			return output.New(6, "Credential not found in this Project")
		}
		if !a.DryRun {
			state.Credentials[resource.Key] = args[2]
			if state.Bindings[resource.UID].ResourceID == "" {
				state.Bindings[resource.UID] = devworkspace.Binding{ResourceID: args[2], Base: graph.Nodes[resource.Key].Document}
			}
			if err = c.WriteState(state); err != nil {
				return output.New(2, err.Error())
			}
		}
		return a.emit(map[string]any{"action": "bind", "kind": "Provider", "alias": resource.Alias, "resource_id": args[2], "executed": !a.DryRun, "scope": "destination"})
	}}
	a.group("resources").AddCommand(command)
}
