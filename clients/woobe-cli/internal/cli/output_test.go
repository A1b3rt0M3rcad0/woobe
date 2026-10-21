package cli

import (
	"bytes"
	"context"
	"encoding/json"
	"github.com/spf13/pflag"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"sync/atomic"
	"testing"
)

func outputInvoke(t *testing.T, args []string) (int, string) {
	t.Helper()
	var out, stderr bytes.Buffer
	a := New(strings.NewReader(""), &out, &stderr)
	args = append(args, "--config", filepath.Join(t.TempDir(), "config.json"))
	code := a.Execute(context.Background(), args)
	if out.Len() == 0 {
		return code, stderr.String()
	}
	return code, out.String()
}

func TestOutputHumanCompactAndFullAgentReads(t *testing.T) {
	t.Setenv("WOOBE_OUTPUT", "auto")
	var calls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls.Add(1)
		if r.URL.Path != "/ai/agents" || r.URL.Query().Get("project_id") != "project" || r.Method != "GET" {
			t.Error(r.Method, r.URL)
		}
		json.NewEncoder(w).Encode(map[string]any{"success": true, "data": []any{map[string]any{"id": "agent-full-id", "name": "Suporte", "status": "draft", "model": "gpt-4.1", "system_prompt": "long instructions", "api_key": "never-output"}}})
	}))
	defer server.Close()
	base := []string{"project", "agent", "list", "--api-url", server.URL, "--project", "project"}
	for _, mode := range []string{"text", "table", "compact", "json", "auto"} {
		code, text := outputInvoke(t, append(append([]string{}, base...), "--output", mode))
		if code != 0 || strings.Contains(text, "never-output") || !strings.Contains(text, "agent-full-id") {
			t.Fatal(mode, code, text)
		}
		if mode == "json" || mode == "auto" {
			var envelope map[string]any
			if json.Unmarshal([]byte(text), &envelope) != nil || envelope["schema_version"] != "1" || !strings.Contains(text, "long instructions") {
				t.Fatal(mode, text)
			}
		} else if strings.Contains(text, "long instructions") {
			t.Fatal("verbose default", mode, text)
		}
	}
	if calls.Load() != 5 {
		t.Fatal("presentation issued additional requests", calls.Load())
	}
}

func TestOutputAliasForwardsFlagsBeforeAndAfterCommand(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Write([]byte(`{"data":[{"id":"a","name":"Agent","description":"useful","model":{"name":"Model"}}]}`))
	}))
	defer server.Close()
	for _, flagsFirst := range []bool{false, true} {
		flags := []string{"--output", "compact", "--fields", "name,model.name,description", "--project", "project", "--api-url", server.URL}
		args := append([]string{"agent", "list"}, flags...)
		if flagsFirst {
			args = append(flags, "agent", "list")
		}
		code, text := outputInvoke(t, args)
		var result map[string]any
		if code != 0 || json.Unmarshal([]byte(text), &result) != nil {
			t.Fatal(code, text)
		}
		row := result["data"].([]any)[0].(map[string]any)
		if len(row) != 3 || row["model.name"] != "Model" || row["description"] != "useful" {
			t.Fatal(result)
		}
	}
}

func TestOutputInvalidPresentationFlagsNeverSendMutation(t *testing.T) {
	var calls atomic.Int32
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		calls.Add(1)
		w.Write([]byte(`{"data":{"id":"created"}}`))
	}))
	defer server.Close()
	for _, flags := range [][]string{
		{"--output", "compact", "--fields", "name..id"},
		{"--output", "json", "--fields", "id"},
		{"--output", "jsonl", "--fields", "id"},
		{"--output", "invalid"},
		{"--output", "compact", "--fields", "id", "--strict-fields"},
	} {
		args := append([]string{"agent", "create", "--api-url", server.URL, "--project", "project"}, flags...)
		code, text := outputInvoke(t, args)
		if code != 2 || !strings.Contains(text, "error") && !strings.Contains(text, "ERROR") {
			t.Fatal(code, text)
		}
	}
	if calls.Load() != 0 {
		t.Fatal("invalid presentation sent a mutation", calls.Load())
	}
}

func TestOutputEnvironmentDefaultAndExplicitOverride(t *testing.T) {
	t.Setenv("WOOBE_OUTPUT", "compact")
	code, text := outputInvoke(t, []string{"version"})
	if code != 0 || strings.Contains(text, "schema_version") || strings.Contains(text, "meta") {
		t.Fatal(code, text)
	}
	code, text = outputInvoke(t, []string{"version", "--output", "json"})
	if code != 0 || !strings.Contains(text, "schema_version") || !strings.Contains(text, "meta") {
		t.Fatal(code, text)
	}
}

func TestOutputJSONLStreamFormatAndUsageErrorsStayMachineReadable(t *testing.T) {
	code, text := outputInvoke(t, []string{"runtime", "target", "stream", "agent", "--output", "text"})
	if code != 2 || !strings.Contains(text, "--output jsonl") {
		t.Fatal(code, text)
	}
	for _, mode := range []string{"text", "compact", "json"} {
		code, text := outputInvoke(t, []string{"unknown-command", "--output", mode})
		if code != 2 || !strings.Contains(text, "unknown command") {
			t.Fatal(code, text)
		}
	}
}

func TestOutputAuditResourceFlagsNeverShadowGlobalFlags(t *testing.T) {
	app := New(strings.NewReader(""), &bytes.Buffer{}, &bytes.Buffer{})
	for _, op := range app.Registry {
		if op.Kind != "http" {
			continue
		}
		cmd, _, err := app.Root.Find(strings.Fields(op.Command))
		if err != nil {
			t.Fatal(err)
		}
		app.Root.PersistentFlags().VisitAll(func(global *pflag.Flag) {
			if local := cmd.Flags().Lookup(global.Name); local != nil && local != global {
				t.Errorf("%s shadows --%s", op.Command, global.Name)
			}
		})
	}
	code, result := invoke(t, []string{"project", "agent", "model-config", "get", "agent", "model-config", "--dry-run"}, "")
	if code != 0 || result["data"].(map[string]any)["path"] != "/ai/agents/agent/model-configs/model-config" {
		t.Fatal(code, result)
	}
}
