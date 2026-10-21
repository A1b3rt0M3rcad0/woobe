package woobe

import (
	"bytes"
	"context"
	"embed"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"os"
	"reflect"
	"strings"
	"testing"
)

//go:embed testdata/artifact_run.json
var artifactRuntimeTestdata embed.FS

type artifactRuntimeFixture struct {
	AgentRequest   map[string]any  `json:"agent_request"`
	NetworkRequest map[string]any  `json:"network_request"`
	ArtifactEvent  json.RawMessage `json:"artifact_available"`
	Completed      json.RawMessage `json:"completed"`
	ImageOnly      json.RawMessage `json:"image_only_completed"`
}

func loadArtifactRuntimeFixture(t *testing.T) artifactRuntimeFixture {
	t.Helper()
	content, err := artifactRuntimeTestdata.ReadFile("testdata/artifact_run.json")
	if err != nil {
		t.Fatal(err)
	}
	shared, sharedErr := os.ReadFile("../../specs/runtime/v2/artifact_run.json")
	if sharedErr == nil && !bytes.Equal(content, shared) {
		t.Fatal("embedded SDK fixture differs from the canonical monorepo runtime fixture")
	} else if sharedErr != nil && !os.IsNotExist(sharedErr) {
		t.Fatal(sharedErr)
	}
	var fixture artifactRuntimeFixture
	if err := json.Unmarshal(content, &fixture); err != nil {
		t.Fatal(err)
	}
	return fixture
}

func compactJSONFixture(t *testing.T, raw json.RawMessage) []byte {
	t.Helper()
	var value any
	if err := json.Unmarshal(raw, &value); err != nil {
		t.Fatal(err)
	}
	encoded, err := json.Marshal(value)
	if err != nil {
		t.Fatal(err)
	}
	return encoded
}

func TestAgentAndNetworkContentPartsMatchSharedRuntimeFixture(t *testing.T) {
	fixture := loadArtifactRuntimeFixture(t)
	parts := []ContentPart{
		TextPart("Resuma este material e cite a página."),
		ArtifactPart(ArtifactReference{ArtifactID: "artifact-source-1", RevisionID: "revision-source-2"}, "application/pdf"),
	}

	t.Run("agent stream", func(t *testing.T) {
		var requests int
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			requests++
			if r.Method != http.MethodPost || r.URL.Path != "/v1/run/stream" {
				t.Errorf("request = %s %s", r.Method, r.URL.Path)
			}
			var body map[string]any
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			if body["message"] != "" || !reflect.DeepEqual(body["content_parts"], fixture.AgentRequest["content_parts"]) || !reflect.DeepEqual(body["external_context"], fixture.AgentRequest["external_context"]) {
				t.Errorf("runtime request = %#v", body)
			}
			w.Header().Set("Content-Type", "text/event-stream")
			fmt.Fprintf(w, "id: 1\ndata: %s\n\n", compactJSONFixture(t, fixture.ArtifactEvent))
			fmt.Fprintf(w, "id: 2\ndata: %s\n\n", compactJSONFixture(t, fixture.Completed))
		}))
		defer server.Close()
		client, err := New(WithBaseURL(server.URL), WithHTTPClient(server.Client()), WithReconnect(0, 0))
		if err != nil {
			t.Fatal(err)
		}
		agent, err := client.Connect.Agent("tutor", "rk-agent")
		if err != nil {
			t.Fatal(err)
		}
		chat, err := agent.ChatParts(parts, &ChatOptions{ExternalContext: map[string]any{"course": "course-17", "turn": 9}})
		if err != nil {
			t.Fatal(err)
		}
		stream, err := chat.Stream(context.Background())
		if err != nil {
			t.Fatal(err)
		}
		var sawArtifact bool
		for event := range stream.Events {
			if artifact, ok, err := event.ArtifactAvailable(); err != nil {
				t.Fatal(err)
			} else if ok {
				sawArtifact = true
				if artifact.Ref.ArtifactID != "artifact-output-1" || artifact.Ref.RevisionID != "revision-output-1" || artifact.RunID == nil || *artifact.RunID != "run-17" {
					t.Fatalf("artifact event = %#v", artifact)
				}
			}
		}
		if err := stream.Err(); err != nil {
			t.Fatal(err)
		}
		result := stream.Result()
		if requests != 1 || !sawArtifact || result == nil || result.Answer != "O prazo é de um ano. [p. 3]" || len(result.OutputArtifacts) != 2 || len(result.SourceRefs) != 1 {
			t.Fatalf("requests=%d sawArtifact=%v result=%#v", requests, sawArtifact, result)
		}
		if result.OutputArtifacts[0].Ref.RevisionID != "revision-output-1" || result.SourceRefs[0].Locator == nil || result.SourceRefs[0].Locator.PageNumber == nil || *result.SourceRefs[0].Locator.PageNumber != 3 {
			t.Fatalf("artifact/source references = %#v / %#v", result.OutputArtifacts, result.SourceRefs)
		}
	})

	t.Run("network synchronous parts", func(t *testing.T) {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if r.Method != http.MethodPost || r.URL.Path != "/v1/run" {
				t.Errorf("request = %s %s", r.Method, r.URL.Path)
			}
			var body map[string]any
			if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
				t.Fatal(err)
			}
			if body["message"] != "" || !reflect.DeepEqual(body["content_parts"], fixture.NetworkRequest["content_parts"]) || !reflect.DeepEqual(body["external_context"], fixture.NetworkRequest["external_context"]) {
				t.Errorf("network request = %#v", body)
			}
			w.Header().Set("Content-Type", "application/json")
			fmt.Fprint(w, `{"success":true,"message":"ok","data":{"answer":"done"}}`)
		}))
		defer server.Close()
		client, err := New(WithBaseURL(server.URL), WithHTTPClient(server.Client()))
		if err != nil {
			t.Fatal(err)
		}
		network, err := client.Connect.Network("study-pipeline", "rk-network")
		if err != nil {
			t.Fatal(err)
		}
		result, err := network.RunParts(context.Background(), parts, &RunOptions{ExternalContext: map[string]any{"course": "course-17", "turn": 9}})
		if err != nil {
			t.Fatal(err)
		}
		if result.Data["answer"] != "done" {
			t.Fatalf("result = %#v", result)
		}
	})
}

func TestImageOnlyResultAndTransferReceiptsAreTypedWithoutFetchingBytes(t *testing.T) {
	fixture := loadArtifactRuntimeFixture(t)
	var event Event
	if err := json.Unmarshal(fixture.ImageOnly, &event); err != nil {
		t.Fatal(err)
	}
	result, err := chatResultFromEvent(event)
	if err != nil {
		t.Fatal(err)
	}
	if result.Answer != "" || len(result.OutputArtifacts) != 1 || result.OutputArtifacts[0].ContentType != "image/png" || result.OutputArtifacts[0].Ref.RevisionID != "revision-image-1" {
		t.Fatalf("image-only result = %#v", result)
	}
	var terminal map[string]any
	if err := json.Unmarshal(fixture.ImageOnly, &terminal); err != nil {
		t.Fatal(err)
	}
	runResponse, err := json.Marshal(map[string]any{"success": true, "message": "ok", "data": terminal["payload"]})
	if err != nil {
		t.Fatal(err)
	}
	var synchronous RunResult
	if err := json.Unmarshal(runResponse, &synchronous); err != nil {
		t.Fatal(err)
	}
	if len(synchronous.OutputArtifacts) != 1 || synchronous.OutputArtifacts[0].Ref.RevisionID != "revision-image-1" {
		t.Fatalf("synchronous Artifact result = %#v", synchronous)
	}

	transferEvent := Event{Type: "artifact.transfer.completed", Payload: map[string]any{
		"operation_id": "operation-1", "state": "completed", "mode": "mcp_base64",
		"destination_host": "tools.example", "input_refs": []any{map[string]any{"artifact_id": "artifact-source-1", "revision_id": "revision-source-2"}},
		"file_hashes": []any{map[string]any{"sha256": strings.Repeat("a", 64), "size_bytes": float64(12)}},
	}}
	transfer, ok, err := transferEvent.ArtifactTransferEvent()
	if err != nil {
		t.Fatal(err)
	}
	if !ok || transfer.OperationID != "operation-1" || transfer.InputRefs[0].RevisionID != "revision-source-2" {
		t.Fatalf("transfer event = %#v, present=%v", transfer, ok)
	}
	if _, _, err := (Event{Type: "artifact_transfer", Payload: map[string]any{"state": "completed"}}).ArtifactTransferEvent(); err == nil {
		t.Fatal("transfer event without an operation ID was accepted")
	}
	malformed := Event{RunID: "run-1", SessionID: "session-1", RunKind: RunKindAgent, Type: "done", Payload: map[string]any{
		"output_artifacts": []any{map[string]any{
			"schema_version": "1", "ref": map[string]any{"artifact_id": "artifact-1", "revision_id": "revision-1"},
			"path": "result.md", "content_type": "text/markdown", "size_bytes": 1, "sha256": "bad", "status": "available",
		}},
	}}
	if _, err := chatResultFromEvent(malformed); err == nil {
		t.Fatal("malformed Artifact SourceRef receipt was accepted")
	}
}

func TestContentPartsRejectAmbiguousAndUnboundedRequestsBeforeHTTP(t *testing.T) {
	var requests int
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) { requests++ }))
	defer server.Close()
	client, err := New(WithBaseURL(server.URL), WithHTTPClient(server.Client()))
	if err != nil {
		t.Fatal(err)
	}
	agent, err := client.Connect.Agent("tutor", "rk")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := agent.Chat("legacy text", &ChatOptions{ContentParts: []ContentPart{TextPart("another text")}}); err == nil {
		t.Fatal("ambiguous message and content parts were accepted")
	}
	tooMany := make([]ContentPart, 17)
	for index := range tooMany {
		tooMany[index] = ArtifactPart(
			ArtifactReference{ArtifactID: fmt.Sprintf("artifact-%d", index), RevisionID: fmt.Sprintf("revision-%d", index)},
			"",
		)
	}
	if _, err := agent.ChatParts(tooMany, nil); err == nil {
		t.Fatal("excess Artifact references were accepted")
	}
	if requests != 0 {
		t.Fatalf("invalid input caused %d HTTP requests", requests)
	}
}
