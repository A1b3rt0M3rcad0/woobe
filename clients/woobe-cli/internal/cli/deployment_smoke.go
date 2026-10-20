package cli

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"reflect"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	sdk "github.com/A1b3rt0M3rcad0/woobe-sdk-go"
)

func (w *deployWorkflow) smokeInput() (map[string]any, error) {
	data, digest, err := readDeployDocument(w.intent.Request.Smoke)
	if err != nil {
		return nil, err
	}
	if data["schema_version"] != "1.0" || packagefmt.Text(data["target_alias"]) == "" || data["request"] == nil {
		return nil, output.New(2, "Smoke requires schema_version: '1.0', target_alias, request and expected_output")
	}
	if _, ok := data["expected_output"]; !ok {
		return nil, output.New(2, "Smoke requires an explicit expected_output assertion")
	}
	for key := range data {
		if key != "schema_version" && key != "target_alias" && key != "request" && key != "expected_output" {
			return nil, output.New(2, "Unknown environment smoke field")
		}
	}
	raw, _ := json.Marshal(data["request"])
	input, err := decodeRuntimeInput(raw)
	if err != nil {
		return nil, output.New(2, err.Error())
	}
	if input.Options.SessionID != "" {
		return nil, output.New(2, "Staging smoke requires a new Session to resolve the current exact Release")
	}
	if old := w.intent.Local["smoke_digest"]; old != "" && old != digest {
		return nil, output.New(6, "Environment smoke changed after deployment intent creation")
	}
	w.intent.Local["smoke_digest"] = digest
	v, err := w.app.resolve()
	if err != nil {
		return nil, err
	}
	if v.RuntimeCredential == "" && os.Getenv("WOOBE_RUNTIME_KEY") == "" {
		return nil, output.New(3, "--via-staging requires a separate Runtime Key; the CLI Key is never reused")
	}
	return data, nil
}

func (w *deployWorkflow) runStagingSmoke() error {
	data, err := w.smokeInput()
	if err != nil {
		return err
	}
	if state := w.intent.Local["smoke_status"]; state != "" {
		if state == "passed" {
			return nil
		}
		if state == "failed" {
			return output.New(11, "Staging smoke failed; Production remains unchanged")
		}
		return &output.Error{Code: 9, Message: "Staging smoke outcome unknown; inspect original Run evidence before a new intent. No Runtime execution repeated", Outcome: "unknown"}
	}
	selected, err := w.current("staging")
	if err != nil {
		return err
	}
	if selected["snapshot_id"] != w.intent.Source["release_id"] || selected["selection_authority"] != "asac" {
		return output.New(6, "Staging changed before its smoke; no Production deployment attempted")
	}
	v, err := w.app.resolve()
	if err != nil {
		return err
	}
	key := os.Getenv("WOOBE_RUNTIME_KEY")
	if v.RuntimeCredential != "" {
		key, err = w.app.store().Get(v.RuntimeCredential)
		if err != nil {
			return err
		}
	}
	cp, err := controlplane.New(v.APIURL, "", w.app.Timeout)
	if err != nil {
		return err
	}
	capture := &runtimeResponseCapture{base: cp.HTTP.Transport}
	cp.HTTP.Transport = capture
	client, err := sdk.New(sdk.WithBaseURL(v.APIURL), sdk.WithHTTPClient(cp.HTTP), sdk.WithReconnect(0, 0))
	if err != nil {
		return runtimeError(err)
	}
	defer client.CloseIdleConnections()
	var target runtimeTarget
	alias := packagefmt.Text(data["target_alias"])
	if w.intent.Kind == "Agent" {
		target, err = client.Connect.Agent(alias, key)
	} else {
		target, err = client.Connect.Network(alias, key)
	}
	if err != nil {
		return runtimeError(err)
	}
	raw, _ := json.Marshal(data["request"])
	input, err := decodeRuntimeInput(raw)
	if err != nil {
		return output.New(2, err.Error())
	}
	w.intent.Local["smoke_status"] = "submitted"
	if err = w.save(); err != nil {
		return err
	}
	ctx, cancel := context.WithTimeout(w.cmd.Context(), w.app.Timeout)
	defer cancel()
	result, err := target.Run(ctx, input.Input, &input.Options)
	if err != nil {
		w.intent.Status = "staging_smoke_unknown"
		_ = w.save()
		return &output.Error{Code: 9, Message: "Staging Runtime response lost; observe the original Run before another intention. No execution repeated", Outcome: "unknown"}
	}
	result, err = capture.preciseResult(result)
	if err != nil {
		return runtimeError(err)
	}
	body := result.Data
	if nested, ok := body["data"].(map[string]any); ok {
		body = nested
	}
	identity := packagefmt.Object(body["runtime_identity"])
	w.intent.Local["smoke_run_id"] = packagefmt.Text(body["run_id"])
	if identity["snapshot_id"] != w.intent.Source["release_id"] || identity["target_id"] != w.intent.Resource || identity["project_id"] != w.intent.Project || identity["environment"] != "staging" {
		w.intent.Local["smoke_status"] = "failed"
		_ = w.save()
		return output.New(9, "Smoke did not prove execution of the intended Staging Release; Production unchanged")
	}
	actual := body["output"]
	if actual == nil {
		actual = body["answer"]
	}
	equal := func(left, right any) bool {
		a, _ := json.Marshal(left)
		b, _ := json.Marshal(right)
		return reflect.DeepEqual(a, b)
	}
	if !result.Success || body["status"] == "failed" || body["status"] == "cancelled" || !equal(actual, data["expected_output"]) {
		w.intent.Local["smoke_status"] = "failed"
		w.intent.Status = "staging_verification_failed"
		_ = w.save()
		return output.New(11, "Staging smoke failed; Staging selection retained and Production unchanged")
	}
	after, err := w.current("staging")
	if err != nil {
		return err
	}
	if after["snapshot_id"] != selected["snapshot_id"] || fmt.Sprint(after["environment_generation"]) != fmt.Sprint(selected["environment_generation"]) {
		return output.New(6, "Staging changed during smoke; inspect before Production deployment")
	}
	w.intent.Local["smoke_status"] = "passed"
	return w.save()
}
