package cli

import (
	"bytes"
	"encoding/json"
	"io"
	"os"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/requestinput"
	"github.com/spf13/cobra"
)

func (a *App) developmentManageCommands() {
	group := a.group("resources")
	group.AddCommand(&cobra.Command{Use: "prune", Args: cobra.NoArgs, Short: "Unregister deleted local artifacts after validating remaining references", Long: "Remove only registry entries whose descriptor file or folder is absent. Preview with --dry-run; apply explicitly with --yes. Remaining references must be valid. Unsafe or unreadable files are rejected, not pruned. Author files, native bindings and remote resources are retained.", Example: "woobe resources prune --dry-run\nwoobe resources prune --yes", RunE: func(cmd *cobra.Command, _ []string) error {
		if !a.DryRun && !a.Yes {
			return output.New(2, "Preview deleted local artifacts with --dry-run, or explicitly unregister them with --yes")
		}
		if err := packageFlags(cmd, "yes"); err != nil {
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
		missing, err := c.PruneMissing(a.DryRun)
		if err != nil {
			return output.New(2, err.Error())
		}
		return a.emit(map[string]any{"resources": missing, "executed": !a.DryRun, "scope": "local", "files_retained": true, "bindings_retained": true, "remote_deleted": false})
	}})
	for _, action := range []string{"create", "register", "clone", "move", "alias", "unregister"} {
		var file, destination, alias string
		command := &cobra.Command{Use: action + " KIND REFERENCE", Args: cobra.ExactArgs(2), Short: action + " an explicitly registered local artifact", Long: "Local registry operation; never deletes remote resources. create copies an author YAML and its declared support files with a new UID; register links an existing descriptor under the configured root; clone gives an existing artifact a new identity and shares its referenced dependencies. unregister retains author files and private native bindings. All writes are journaled and references validated.", Example: "woobe resources clone agent '@support' --alias support-v2\nwoobe resources create provider openai --file provider.yaml\nwoobe agent '@support-v2' create", RunE: func(cmd *cobra.Command, args []string) error {
			kind := devworkspace.CanonicalKind(args[0])
			if kind == "" {
				return output.New(2, "Unknown resource kind")
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
			var resource devworkspace.Resource
			switch action {
			case "create":
				if file == "" || alias != "" {
					return output.New(2, "create requires --file; REFERENCE is the new local alias")
				}
				source, readErr := os.Open(file)
				if readErr != nil {
					return output.New(2, "Cannot read author file")
				}
				data, readErr := io.ReadAll(io.LimitReader(source, requestinput.MaxBytes+1))
				source.Close()
				if readErr != nil || len(data) > requestinput.MaxBytes {
					return output.New(2, "Author file exceeds input limit or cannot be read")
				}
				data, err = requestinput.Decode(data, file, "auto")
				if err != nil {
					return output.New(2, err.Error())
				}
				decoder := json.NewDecoder(bytes.NewReader(data))
				decoder.UseNumber()
				var document map[string]any
				if err = decoder.Decode(&document); err == nil {
					var supports map[string][]byte
					supports, err = devworkspace.ReadAuthorSupports(document, file)
					if err == nil {
						resource, err = c.Add(kind, args[1], destination, document, supports, a.DryRun)
					}
				}
			case "register":
				if destination == "" || file != "" || alias != "" {
					return output.New(2, "register requires --path relative to the configured root; REFERENCE is the local alias")
				}
				resource, err = c.Register(kind, args[1], destination, a.DryRun)
			case "clone":
				if alias == "" || file != "" {
					return output.New(2, "clone requires --alias for its new identity")
				}
				var state *devworkspace.State
				if a.ContextName == "" && os.Getenv("WOOBE_CONTEXT") == "" {
					a.ContextName = c.Context
				}
				if connection, resolveErr := a.resolve(); resolveErr == nil {
					state, err = c.ReadState(strings.TrimRight(connection.APIURL, "/"), connection.Workspace, connection.Project)
					if err != nil {
						return output.New(2, err.Error())
					}
				}
				resource, err = c.CloneWithState(kind, args[1], alias, destination, state, a.DryRun)
			case "move":
				if destination == "" || alias != "" || file != "" {
					return output.New(2, "move requires --path relative to the configured root")
				}
				err = c.Move(kind, args[1], destination, a.DryRun)
			case "alias":
				if alias == "" || destination != "" || file != "" {
					return output.New(2, "alias requires --alias; native identity and logical references remain stable")
				}
				err = c.Alias(kind, args[1], alias, a.DryRun)
			case "unregister":
				if destination != "" || alias != "" || file != "" {
					return output.New(2, "unregister accepts only its resource reference")
				}
				err = c.Unregister(kind, args[1], a.DryRun)
			}
			if err != nil {
				return output.New(2, err.Error())
			}
			return a.emit(map[string]any{"action": action, "resource": resource, "executed": !a.DryRun, "scope": "local", "files_retained": action == "unregister", "remote_deleted": false})
		}}
		command.Flags().StringVar(&file, "file", "", "Author JSON/YAML descriptor to copy")
		command.Flags().StringVar(&destination, "path", "", "Artifact path relative to the configured root")
		command.Flags().StringVar(&alias, "alias", "", "New local identity for clone")
		group.AddCommand(command)
	}
}
