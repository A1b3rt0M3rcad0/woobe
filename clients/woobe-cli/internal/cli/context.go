package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"strings"
)

func (a *App) contextCommands() {
	g := &cobra.Command{Use: "context", Short: "Local context profiles"}
	a.Root.AddCommand(g)
	for _, action := range []string{"list", "show", "create", "update", "use", "delete", "set"} {
		action := action
		cmd := &cobra.Command{Use: action, RunE: func(_ *cobra.Command, args []string) error {
			c, e := config.Load(a.ConfigPath)
			if e != nil {
				return output.New(2, "cannot load config")
			}
			name := c.Current
			if a.ContextName != "" {
				name = a.ContextName
			}
			if len(args) > 1 {
				return output.New(2, "expected at most one context name")
			}
			if len(args) == 1 {
				name = args[0]
			}
			oldCredential := c.Contexts[name].Credential
			oldManaged := isConnectionCredential(c.Contexts[name])
			switch action {
			case "list":
				return a.emit(c)
			case "show":
				if len(args) == 1 {
					a.ContextName = name
				}
				v, e := a.resolve()
				if e != nil {
					return e
				}
				return a.emit(v)
			case "create":
				if len(args) != 1 {
					return output.New(2, "context name required")
				}
				if _, ok := c.Contexts[name]; ok {
					return output.New(6, "context exists")
				}
				if a.APIURL == "" {
					return output.New(2, "--api-url required")
				}
				c.Contexts[name] = config.Context{APIURL: a.APIURL, Workspace: a.Workspace, Project: a.Project}
			default:
				v, ok := c.Contexts[name]
				if !ok {
					return output.New(2, "unknown context")
				}
				switch action {
				case "use":
					c.Current = name
				case "delete":
					delete(c.Contexts, name)
					if c.Current == name {
						c.Current = ""
					}
				case "update", "set":
					if a.APIURL != "" {
						if strings.TrimRight(v.APIURL, "/") != strings.TrimRight(a.APIURL, "/") {
							v.Credential = ""
							v.RuntimeCredential = ""
							v.AuthAPIURL = ""
							v.Workspace = ""
							v.Project = ""
						}
						v.APIURL = a.APIURL
					}
					if a.Workspace != "" && a.Workspace != v.Workspace {
						v.Workspace = a.Workspace
						v.Project = ""
					}
					if a.Project != "" {
						v.Project = a.Project
					}
					c.Contexts[name] = v
				}
			}
			if e = config.Save(a.ConfigPath, c); e != nil {
				return e
			}
			if oldManaged && c.Contexts[name].Credential != oldCredential {
				if e = a.store().Remove(oldCredential); e != nil {
					return output.New(3, "Context saved, but previous credential cleanup failed")
				}
			}
			return a.emit(map[string]string{"context": name, "action": action})
		}}
		g.AddCommand(cmd)
	}
	g.AddCommand(&cobra.Command{Use: "unset <context> <field>...", Args: cobra.MinimumNArgs(2), RunE: func(_ *cobra.Command, args []string) error {
		c, e := config.Load(a.ConfigPath)
		if e != nil {
			return e
		}
		v, ok := c.Contexts[args[0]]
		if !ok {
			return output.New(2, "unknown context")
		}
		for _, field := range args[1:] {
			switch field {
			case "workspace":
				v.Workspace = ""
				v.Project = ""
			case "project":
				v.Project = ""
			case "credential":
				v.Credential = ""
				v.AuthAPIURL = ""
			case "runtime-credential":
				v.RuntimeCredential = ""
			default:
				return output.New(2, "unsupported context field")
			}
		}
		c.Contexts[args[0]] = v
		if e = config.Save(a.ConfigPath, c); e != nil {
			return e
		}
		return a.emit(map[string]any{"context": args[0], "unset": strings.Join(args[1:], ",")})
	}})
	for _, runtimeCredential := range []bool{false, true} {
		label := "credential"
		if runtimeCredential {
			label = "runtime-credential"
		}
		cr := &cobra.Command{Use: label}
		g.AddCommand(cr)
		for _, action := range []string{"attach", "detach"} {
			action := action
			cr.AddCommand(&cobra.Command{Use: action + " <context>", Args: cobra.ExactArgs(1), RunE: func(_ *cobra.Command, args []string) error {
				c, e := config.Load(a.ConfigPath)
				if e != nil {
					return e
				}
				v, ok := c.Contexts[args[0]]
				if !ok {
					return output.New(2, "unknown context")
				}
				ref := a.Credential
				if runtimeCredential {
					ref = a.RuntimeCredential
				}
				if action == "attach" {
					for _, connection := range c.Contexts {
						if connection.Credential == ref && isConnectionCredential(connection) {
							return output.New(2, "Connection credentials are private to their context; use auth login --cli-key")
						}
					}
					if ref == "" {
						return output.New(2, "credential reference flag required")
					}
					if _, e = a.store().Get(ref); e != nil {
						return e
					}
					if runtimeCredential {
						v.RuntimeCredential = ref
					} else {
						v.Credential = ref
						v.AuthAPIURL = ""
					}
				} else {
					if runtimeCredential {
						v.RuntimeCredential = ""
					} else {
						v.Credential = ""
						v.AuthAPIURL = ""
					}
				}
				c.Contexts[args[0]] = v
				if e = config.Save(a.ConfigPath, c); e != nil {
					return e
				}
				return a.emit(map[string]string{"context": args[0], "action": action})
			}})
		}
	}
}
