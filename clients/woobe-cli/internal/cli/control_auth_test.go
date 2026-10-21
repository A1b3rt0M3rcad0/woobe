package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/credentials"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/schemacheck"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func authServer(t *testing.T, projects []controlProject) *httptest.Server {
	t.Helper()
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Header.Get("Authorization") != "Bearer test-control-key" {
			w.WriteHeader(401)
			return
		}
		if r.URL.Path != "/identity/control-key/me" {
			w.WriteHeader(404)
			return
		}
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"schema_version": "1", "credential_type": "control", "workspace": map[string]string{"id": "workspace", "name": "Workspace", "status": "active"}, "projects": projects}})
	}))
}
func authExecute(t *testing.T, path, input string, args ...string) (int, string) {
	t.Helper()
	var out bytes.Buffer
	app := New(strings.NewReader(input), &out, &bytes.Buffer{})
	code := app.Execute(context.Background(), append([]string{"--config", path}, args...))
	return code, out.String()
}
func authConfig(t *testing.T, url string) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "config.json")
	if e := config.Save(path, config.Config{Version: 1, Current: "first", Contexts: map[string]config.Context{"first": {APIURL: url}, "second": {APIURL: url}}}); e != nil {
		t.Fatal(e)
	}
	return path
}
func eligibleProject(id, name string) controlProject {
	return controlProject{ID: id, Name: name, Slug: strings.ToLower(name), Status: "active", Eligible: true, Permissions: []string{"agent:read"}}
}
func TestControlLoginPersistsScopeAndIsolatesLogout(t *testing.T) {
	srv := authServer(t, []controlProject{eligibleProject("project", "Production")})
	defer srv.Close()
	path := authConfig(t, srv.URL)
	for _, name := range []string{"first", "second"} {
		code, out := authExecute(t, path, "test-control-key", "--context", name, "auth", "login", "--cli-key", "--stdin")
		if code != 0 {
			t.Fatal(out)
		}
	}
	c, e := config.Load(path)
	if e != nil {
		t.Fatal(e)
	}
	v := c.Contexts["first"]
	if v.Workspace != "workspace" || v.Project != "project" || v.Credential == c.Contexts["second"].Credential {
		t.Fatal(c)
	}
	b, _ := os.ReadFile(path)
	if bytes.Contains(b, []byte("test-control-key")) {
		t.Fatal("secret leaked into config")
	}
	code, out := authExecute(t, path, "", "auth", "status")
	if code != 0 || !strings.Contains(out, "private-file") && !strings.Contains(out, "windows-credential-manager") {
		t.Fatal(out)
	}
	code, out = authExecute(t, path, "", "auth", "logout", "--cli-key")
	if code != 0 {
		t.Fatal(out)
	}
	c, _ = config.Load(path)
	if c.Contexts["first"].Workspace != "" || c.Contexts["first"].Credential != "" || c.Contexts["second"].Credential == "" {
		t.Fatal(c)
	}
	code, out = authExecute(t, path, "", "--context", "second", "auth", "status")
	if code != 0 {
		t.Fatal(out)
	}
	_, _ = authExecute(t, path, "", "--context", "second", "auth", "logout", "--cli-key")
	store := credentials.Store{Dir: filepath.Join(filepath.Dir(path), "credentials")}
	if _, e = store.Get(v.Credential); e == nil {
		t.Fatal("logout retained credential")
	}
}
func TestControlLoginFailurePreservesPreviousAuthentication(t *testing.T) {
	srv := authServer(t, nil)
	defer srv.Close()
	path := authConfig(t, srv.URL)
	code, out := authExecute(t, path, "test-control-key", "auth", "login", "--cli-key", "--stdin")
	if code != 0 {
		t.Fatal(out)
	}
	t.Cleanup(func() { _, _ = authExecute(t, path, "", "auth", "logout", "--cli-key") })
	before, _ := os.ReadFile(path)
	code, out = authExecute(t, path, "invalid-secret", "auth", "login", "--cli-key", "--stdin")
	if code == 0 || strings.Contains(out, "invalid-secret") {
		t.Fatal(out)
	}
	after, _ := os.ReadFile(path)
	if !bytes.Equal(before, after) {
		t.Fatal("failed login changed config")
	}
}
func TestControlMultiProjectSelectionAndNoArbitraryDefault(t *testing.T) {
	srv := authServer(t, []controlProject{eligibleProject("a", "Alpha"), eligibleProject("b", "Beta")})
	defer srv.Close()
	path := authConfig(t, srv.URL)
	code, out := authExecute(t, path, "test-control-key", "auth", "login", "--cli-key", "--stdin")
	if code != 0 || !strings.Contains(out, "project_selection_required") {
		t.Fatal(out)
	}
	t.Cleanup(func() { _, _ = authExecute(t, path, "", "auth", "logout", "--cli-key") })
	c, _ := config.Load(path)
	if c.Contexts["first"].Project != "" {
		t.Fatal("arbitrary project")
	}
	code, out = authExecute(t, path, "", "context", "project", "select", "Beta")
	if code != 0 {
		t.Fatal(out)
	}
	c, _ = config.Load(path)
	if c.Contexts["first"].Project != "b" {
		t.Fatal(c)
	}
	before, _ := os.ReadFile(path)
	code, out = authExecute(t, path, "", "context", "project", "select", "Missing")
	after, _ := os.ReadFile(path)
	if code == 0 || !bytes.Equal(before, after) {
		t.Fatal(out)
	}
}
func TestControlOriginOverrideNeverSendsKey(t *testing.T) {
	srv := authServer(t, nil)
	defer srv.Close()
	path := authConfig(t, srv.URL)
	code, out := authExecute(t, path, "test-control-key", "auth", "login", "--cli-key", "--stdin")
	if code != 0 {
		t.Fatal(out)
	}
	t.Cleanup(func() { _, _ = authExecute(t, path, "", "auth", "logout", "--cli-key") })
	calls := 0
	other := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { calls++; w.WriteHeader(500) }))
	defer other.Close()
	code, out = authExecute(t, path, "", "--api-url", other.URL, "auth", "status")
	if code == 0 || calls != 0 {
		t.Fatal("credential crossed API origin", out)
	}
	saved, _ := config.Load(path)
	owned := saved.Contexts["first"].Credential
	otherContext := saved.Contexts["second"]
	otherContext.APIURL = other.URL
	saved.Contexts["second"] = otherContext
	if e := config.Save(path, saved); e != nil {
		t.Fatal(e)
	}
	code, out = authExecute(t, path, "", "--context", "second", "--credential", owned, "auth", "status")
	if code == 0 || calls != 0 {
		t.Fatal("A reference override leaked a managed connection credential", out)
	}

	code, out = authExecute(t, path, "", "context", "update", "first", "--api-url", other.URL)
	if code != 0 {
		t.Fatal(out)
	}
	c, _ := config.Load(path)
	if c.Contexts["first"].Credential != "" || c.Contexts["first"].Workspace != "" {
		t.Fatal(c)
	}
}
func TestControlOldBackendPreservesConfig(t *testing.T) {
	srv := httptest.NewServer(http.NotFoundHandler())
	defer srv.Close()
	path := authConfig(t, srv.URL)
	before, _ := os.ReadFile(path)
	code, out := authExecute(t, path, "test-control-key", "auth", "login", "--cli-key", "--stdin")
	after, _ := os.ReadFile(path)
	if code != 9 || !strings.Contains(out, "Upgrade") || !bytes.Equal(before, after) {
		t.Fatal(code, out)
	}
}

func TestControlSelectedGrantRemovalRequiresSelectionWithoutRetargeting(t *testing.T) {
	projects := []controlProject{eligibleProject("a", "Alpha"), eligibleProject("b", "Beta")}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{"success": true, "data": map[string]any{"schema_version": "1", "credential_type": "control", "workspace": map[string]string{"id": "workspace", "status": "active"}, "projects": projects}})
	}))
	defer srv.Close()
	path := authConfig(t, srv.URL)
	code, out := authExecute(t, path, "test-control-key", "auth", "login", "--cli-key", "--stdin", "--select-project", "beta")
	if code != 0 {
		t.Fatal(out)
	}
	t.Cleanup(func() { _, _ = authExecute(t, path, "", "auth", "logout", "--cli-key") })
	projects = []controlProject{eligibleProject("a", "Alpha")}
	code, out = authExecute(t, path, "", "auth", "status")
	if code != 0 || !strings.Contains(out, "project_selection_required") {
		t.Fatal(out)
	}
	c, _ := config.Load(path)
	if c.Contexts["first"].Project != "b" {
		t.Fatal("status silently retargeted selected project")
	}
	code, out = authExecute(t, path, "test-control-key", "auth", "login", "--cli-key", "--stdin")
	if code != 0 {
		t.Fatal(out)
	}
	c, _ = config.Load(path)
	if c.Contexts["first"].Project != "a" {
		t.Fatal("explicit login did not refresh grants")
	}
}
func TestControlDryRunDoesNotReadOrPersistKey(t *testing.T) {
	path := authConfig(t, "https://example.invalid")
	before, _ := os.ReadFile(path)
	code, out := authExecute(t, path, "", "auth", "login", "--cli-key", "--dry-run")
	if code != 0 || !strings.Contains(out, "\"executed\":false") {
		t.Fatal(out)
	}
	after, _ := os.ReadFile(path)
	if !bytes.Equal(before, after) {
		t.Fatal("dry run changed config")
	}
}

func TestControlLoginInvocationSchemaDistinguishesHumanAndKeyModes(t *testing.T) {
	app := New(strings.NewReader(""), &bytes.Buffer{}, &bytes.Buffer{})
	op, ok := app.operation("auth login")
	if !ok {
		t.Fatal("Login not discoverable")
	}
	for _, flag := range op.Flags {
		if flag.Name == "file" && flag.Required {
			t.Fatal("CLI Key login incorrectly requires file")
		}
	}
	schema := commandSchema(op, "input")["properties"].(map[string]any)["flags"]
	raw, _ := json.Marshal(schema)
	var decoded any
	_ = json.Unmarshal(raw, &decoded)
	for _, test := range []struct {
		flags map[string]any
		valid bool
	}{
		{map[string]any{"cli-key": true}, true},
		{map[string]any{"cli-key": true, "stdin": true, "select-project": "production"}, true},
		{map[string]any{"file": "login.json"}, true},
		{map[string]any{"cli-key": false, "file": "login.json"}, true},
		{map[string]any{}, false},
		{map[string]any{"cli-key": true, "file": "secret.json"}, false},
		{map[string]any{"file": "login.json", "stdin": true}, false},
		{map[string]any{"cli-key": true, "validate-parameters": true}, false},
	} {
		if err := schemacheck.Check(decoded, test.flags, decoded); (err == nil) != test.valid {
			t.Fatalf("schema validity=%v, expected=%v: %v", err == nil, test.valid, err)
		}
	}
}

func TestControlInteractiveProjectChoiceByNumberNameAndSlug(t *testing.T) {
	app := New(strings.NewReader(""), &bytes.Buffer{}, &bytes.Buffer{})
	projects := []controlProject{eligibleProject("a", "Alpha"), eligibleProject("b", "Production Team")}
	projects[1].Slug = "production"
	identity := controlIdentity{Projects: projects}
	for _, choice := range []string{"2", "Production Team", "production"} {
		id, err := app.controlProjectChoice(identity, projects, choice)
		if err != nil || id != "b" {
			t.Fatalf("Choice %q did not select production: %v", choice, err)
		}
	}
	for _, choice := range []string{"", "3", "Missing"} {
		if _, err := app.controlProjectChoice(identity, projects, choice); err == nil {
			t.Fatal("Invalid choice selected a project")
		}
	}
}

func TestControlLegacyReferencesAreNotDeletedOrReservedByPrefix(t *testing.T) {
	srv := authServer(t, nil)
	defer srv.Close()
	path := authConfig(t, srv.URL)
	store := credentials.Store{Dir: filepath.Join(filepath.Dir(path), "credentials")}
	const alias = "connection-legacy"
	if e := store.Put(alias, "test-control-key"); e != nil {
		t.Fatal(e)
	}
	t.Cleanup(func() { _ = store.Remove(alias); _, _ = authExecute(t, path, "", "auth", "logout", "--cli-key") })
	for _, name := range []string{"first", "second"} {
		code, out := authExecute(t, path, "", "context", "credential", "attach", name, "--credential", alias)
		if code != 0 {
			t.Fatal(out)
		}
	}
	code, out := authExecute(t, path, "", "auth", "logout", "--cli-key")
	if code != 0 {
		t.Fatal(out)
	}
	if _, e := store.Get(alias); e != nil {
		t.Fatal("Logout deleted a shared legacy reference", e)
	}
	code, out = authExecute(t, path, "test-control-key", "auth", "login", "--cli-key", "--stdin")
	if code != 0 {
		t.Fatal(out)
	}
	if _, e := store.Get(alias); e != nil {
		t.Fatal("Login deleted a shared legacy reference", e)
	}
	code, out = authExecute(t, path, "", "--context", "second", "auth", "status")
	if code != 0 {
		t.Fatal(out)
	}
	c, _ := config.Load(path)
	owned := c.Contexts["first"].Credential
	code, out = authExecute(t, path, "", "context", "credential", "attach", "second", "--credential", owned)
	if code == 0 {
		t.Fatal("Managed connection credential was shared across contexts")
	}
	c, _ = config.Load(path)
	if c.Contexts["second"].Credential != alias {
		t.Fatal("Failed attach changed second context")
	}
}
