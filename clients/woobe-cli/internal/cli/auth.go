package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/identity"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"io"
	"path/filepath"
)

func (a *App) authCommands() {
	for _, op := range []Operation{{Command: "auth login", Method: "POST", Path: "/identity/auth/login", Body: true}, {Command: "auth register", Method: "POST", Path: "/identity/auth/register", Body: true}, {Command: "auth refresh", Method: "POST", Path: "/identity/auth/refresh"}, {Command: "auth status", Method: "GET", Path: "/identity/users/me"}, {Command: "auth invite list", Method: "GET", Path: "/identity/invites/pending"}, {Command: "auth invite accept", Method: "POST", Path: "/identity/invites/{invite_id}/accept"}, {Command: "instance status", Method: "GET", Path: "/identity/instance/status"}, {Command: "instance bootstrap", Method: "POST", Path: "/identity/instance/bootstrap", Body: true}} {
		a.register(op)
	}
	a.group("auth").AddCommand(&cobra.Command{Use: "logout", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		c, e := a.client()
		if e != nil {
			return e
		}
		_, _, e = c.Request(cmd.Context(), "POST", "/identity/auth/logout", nil, nil)
		if e != nil {
			return e
		}
		s, _, e := identity.Load(filepath.Join(filepath.Dir(a.ConfigPath), "sessions"), c.Base)
		if e != nil {
			return e
		}
		if e = s.Remove(); e != nil {
			return e
		}
		return a.emit(map[string]bool{"logged_out": true})
	}})
	g := a.group("auth credential")
	var name string
	var stdin bool
	c := &cobra.Command{Use: "import", Args: cobra.NoArgs, RunE: func(*cobra.Command, []string) error {
		if !stdin || name == "" {
			return output.New(2, "--stdin and --name required")
		}
		b, e := io.ReadAll(io.LimitReader(a.In, 65537))
		if e != nil {
			return e
		}
		if len(b) > 65536 {
			return output.New(2, "credential too large")
		}
		secret, e := credentialFromInput(b)
		if e != nil {
			return e
		}
		if e = a.store().Put(name, secret); e != nil {
			return e
		}
		return a.emit(map[string]string{"credential": name})
	}}
	c.Flags().StringVar(&name, "name", "", "Reference name")
	c.Flags().BoolVar(&stdin, "stdin", false, "Read credential from stdin")
	g.AddCommand(c)
	g.AddCommand(&cobra.Command{Use: "list", Args: cobra.NoArgs, RunE: func(*cobra.Command, []string) error {
		v, e := a.store().List()
		if e != nil {
			return e
		}
		return a.emit(v)
	}})
	g.AddCommand(&cobra.Command{Use: "remove <name>", Args: cobra.ExactArgs(1), RunE: func(_ *cobra.Command, args []string) error {
		if e := a.store().Remove(args[0]); e != nil {
			return e
		}
		return a.emit(map[string]string{"removed": args[0]})
	}})
}
