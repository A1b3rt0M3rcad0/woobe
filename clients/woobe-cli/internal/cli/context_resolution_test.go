package cli

import (
	"bytes"
	"context"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"path/filepath"
	"testing"
)

func contextApp(t *testing.T) *App {
	t.Helper()
	a := New(&bytes.Buffer{}, &bytes.Buffer{}, &bytes.Buffer{})
	a.ConfigPath = filepath.Join(t.TempDir(), "config.json")
	if e := config.Save(a.ConfigPath, config.Config{Version: 1, Current: "dev", Contexts: map[string]config.Context{"dev": {APIURL: "http://localhost", Workspace: "w1", Project: "p1"}}}); e != nil {
		t.Fatal(e)
	}
	return a
}
func TestWorkspaceOverrideClearsInheritedProject(t *testing.T) {
	for _, env := range []bool{false, true} {
		a := contextApp(t)
		if env {
			t.Setenv("WOOBE_WORKSPACE_ID", "w2")
		} else {
			a.Workspace = "w2"
		}
		v, e := a.resolve()
		if e != nil || v.Project != "" || v.Workspace != "w2" {
			t.Fatal(v, e)
		}
	}
	a := contextApp(t)
	a.Workspace = "w2"
	a.Project = "p2"
	v, e := a.resolve()
	if e != nil || v.Project != "p2" {
		t.Fatal(v, e)
	}
}

func TestExplicitEmptyFlagsOverrideEnvironment(t *testing.T) {
	a := contextApp(t)
	t.Setenv("WOOBE_PROJECT_ID", "env-project")
	if e := a.Root.PersistentFlags().Set("project", ""); e != nil {
		t.Fatal(e)
	}
	v, e := a.resolve()
	if e != nil || v.Project != "" {
		t.Fatal(v, e)
	}
}

func TestShowNamedContext(t *testing.T) {
	a := contextApp(t)
	c, _ := config.Load(a.ConfigPath)
	c.Contexts["other"] = config.Context{APIURL: "http://other", Project: "p2"}
	if e := config.Save(a.ConfigPath, c); e != nil {
		t.Fatal(e)
	}
	if code := a.Execute(context.Background(), []string{"context", "show", "other"}); code != 0 {
		t.Fatal(code)
	}
	if a.Project != "p2" {
		t.Fatal(a.Project)
	}
}

func TestUnsetWorkspaceClearsProject(t *testing.T) {
	a := contextApp(t)
	if code := a.Execute(context.Background(), []string{"context", "unset", "dev", "workspace"}); code != 0 {
		t.Fatal(code)
	}
	c, e := config.Load(a.ConfigPath)
	if e != nil || c.Contexts["dev"].Workspace != "" || c.Contexts["dev"].Project != "" {
		t.Fatal(c, e)
	}
}

func TestRuntimeCredentialAttachment(t *testing.T) {
	a := contextApp(t)
	if e := a.store().Put("runtime", "secret-value"); e != nil {
		t.Fatal(e)
	}
	if code := a.Execute(context.Background(), []string{"context", "runtime-credential", "attach", "dev", "--runtime-credential", "runtime"}); code != 0 {
		t.Fatal(code)
	}
	c, e := config.Load(a.ConfigPath)
	v := c.Contexts["dev"]
	if e != nil || v.RuntimeCredential != "runtime" || v.Credential != "" {
		t.Fatal(v, e)
	}
}

func TestControlContextURLChangeDetachesRuntimeCredential(t *testing.T) {
	a := contextApp(t)
	c, err := config.Load(a.ConfigPath)
	if err != nil {
		t.Fatal(err)
	}
	v := c.Contexts["dev"]
	v.RuntimeCredential = "runtime"
	c.Contexts["dev"] = v
	if err := config.Save(a.ConfigPath, c); err != nil {
		t.Fatal(err)
	}
	if err := a.store().Put("runtime", "test-runtime-key"); err != nil {
		t.Fatal(err)
	}
	if code := a.Execute(context.Background(), []string{"context", "update", "dev", "--api-url", "http://other"}); code != 0 {
		t.Fatal(code)
	}
	c, err = config.Load(a.ConfigPath)
	if err != nil || c.Contexts["dev"].RuntimeCredential != "" {
		t.Fatal("old runtime credential retained for new API", c, err)
	}
	if _, err := a.store().Get("runtime"); err != nil {
		t.Fatal("detachment deleted a reusable credential", err)
	}
}
