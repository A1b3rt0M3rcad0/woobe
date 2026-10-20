package woobe

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"sync/atomic"
	"testing"
	"time"
)

func TestAgentStreamCapturesIdentityAndResult(t *testing.T) {
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/run/stream", func(w http.ResponseWriter, r *http.Request) {
		if got := r.Header.Get("Authorization"); got != "Bearer rk_test" {
			t.Fatalf("authorization=%q", got)
		}
		w.Header().Set("Content-Type", "text/event-stream")
		fmt.Fprint(w, "id: 0\ndata: {\"protocol_version\":2,\"event_id\":\"e0\",\"run_id\":\"run-1\",\"session_id\":\"sess-1\",\"run_kind\":\"AGENT\",\"sequence\":0,\"type\":\"run.state\",\"occurred_at\":\"2026-09-30T00:00:00Z\",\"payload\":{\"status\":\"running\"}}\n\n")
		fmt.Fprint(w, "id: 1\ndata: {\"protocol_version\":2,\"event_id\":\"e1\",\"run_id\":\"run-1\",\"session_id\":\"sess-1\",\"run_kind\":\"AGENT\",\"sequence\":1,\"type\":\"done\",\"occurred_at\":\"2026-09-30T00:00:01Z\",\"payload\":{\"answer\":\"ok\"}}\n\n")
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	client, err := New(WithBaseURL(srv.URL), WithReconnect(0, 0))
	if err != nil { t.Fatal(err) }
	agent, err := client.Connect.Agent("support", "rk_test")
	if err != nil { t.Fatal(err) }
	chat, err := agent.Chat("hello", nil)
	if err != nil { t.Fatal(err) }
	stream, err := chat.Stream(context.Background())
	if err != nil { t.Fatal(err) }

	var count int
	for range stream.Events { count++ }
	if err := stream.Err(); err != nil { t.Fatal(err) }
	if count != 2 { t.Fatalf("count=%d", count) }
	if stream.RunID() != "run-1" || stream.SessionID() != "sess-1" {
		t.Fatalf("identity=%s/%s", stream.RunID(), stream.SessionID())
	}
	if stream.Result() == nil || stream.Result().Answer != "ok" { t.Fatalf("result=%#v", stream.Result()) }
}

func TestReattachAfterSequenceGap(t *testing.T) {
	var posts atomic.Int32
	var gets atomic.Int32
	mux := http.NewServeMux()
	mux.HandleFunc("/v1/run/stream", func(w http.ResponseWriter, r *http.Request) {
		posts.Add(1)
		w.Header().Set("Content-Type", "text/event-stream")
		fmt.Fprint(w, "id: 0\ndata: {\"protocol_version\":2,\"event_id\":\"e0\",\"run_id\":\"run-1\",\"session_id\":\"sess-1\",\"run_kind\":\"AGENT\",\"sequence\":0,\"type\":\"run.state\",\"occurred_at\":\"2026-09-30T00:00:00Z\",\"payload\":{\"status\":\"running\"}}\n\n")
		fmt.Fprint(w, "id: 2\ndata: {\"protocol_version\":2,\"event_id\":\"e2\",\"run_id\":\"run-1\",\"session_id\":\"sess-1\",\"run_kind\":\"AGENT\",\"sequence\":2,\"type\":\"token\",\"occurred_at\":\"2026-09-30T00:00:01Z\",\"payload\":{\"content\":\"x\"}}\n\n")
	})
	mux.HandleFunc("/v1/runs/run-1/stream", func(w http.ResponseWriter, r *http.Request) {
		gets.Add(1)
		w.Header().Set("Content-Type", "text/event-stream")
		fmt.Fprint(w, "id: 2\ndata: {\"protocol_version\":2,\"event_id\":\"s2\",\"run_id\":\"run-1\",\"session_id\":\"sess-1\",\"run_kind\":\"AGENT\",\"sequence\":2,\"type\":\"run.state\",\"occurred_at\":\"2026-09-30T00:00:02Z\",\"payload\":{\"status\":\"running\"}}\n\n")
		fmt.Fprint(w, "id: 3\ndata: {\"protocol_version\":2,\"event_id\":\"e3\",\"run_id\":\"run-1\",\"session_id\":\"sess-1\",\"run_kind\":\"AGENT\",\"sequence\":3,\"type\":\"done\",\"occurred_at\":\"2026-09-30T00:00:03Z\",\"payload\":{\"answer\":\"recovered\"}}\n\n")
	})
	srv := httptest.NewServer(mux)
	defer srv.Close()

	client, _ := New(WithBaseURL(srv.URL), WithReconnect(2, time.Millisecond))
	agent, _ := client.Connect.Agent("a", "rk")
	chat, _ := agent.Chat("x", nil)
	stream, _ := chat.Stream(context.Background())
	for range stream.Events {}
	if err := stream.Err(); err != nil { t.Fatal(err) }
	if posts.Load() != 1 { t.Fatalf("duplicate POSTs=%d", posts.Load()) }
	if gets.Load() != 1 { t.Fatalf("reattach GETs=%d", gets.Load()) }
	if stream.Result() == nil || stream.Result().Answer != "recovered" { t.Fatalf("result=%#v", stream.Result()) }
}

func TestAuthenticationError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "invalid runtime key", http.StatusUnauthorized)
	}))
	defer srv.Close()
	client, _ := New(WithBaseURL(srv.URL))
	agent, _ := client.Connect.Agent("a", "bad")
	_, err := agent.Run(context.Background(), "hello", nil)
	if err == nil { t.Fatal("expected error") }
	if _, ok := err.(*AuthenticationError); !ok { t.Fatalf("type=%T", err) }
}
