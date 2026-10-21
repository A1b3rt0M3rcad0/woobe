package controlplane

import (
	"context"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"net/http"
	"net/http/httptest"
	"sync"
	"testing"
	"time"
)

func TestIdempotencyHeaderDoesNotEnableImplicitWriteReplay(t *testing.T) {
	var mu sync.Mutex
	reads, writes := 0, 0
	readAddr, writeAddr := "", ""
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		defer mu.Unlock()
		if r.Method == "GET" {
			reads++
			readAddr = r.RemoteAddr
			w.Write([]byte(`{}`))
			return
		}
		writes++
		writeAddr = r.RemoteAddr
		if writes == 1 {
			conn, _, e := w.(http.Hijacker).Hijack()
			if e != nil {
				t.Error(e)
				return
			}
			conn.Close()
			return
		}
		w.Write([]byte(`{"id":"duplicate"}`))
	}))
	defer s.Close()
	c, _ := New(s.URL, "", time.Second)
	defer c.HTTP.CloseIdleConnections()
	if _, _, e := c.Request(context.Background(), "GET", "/x", nil, nil); e != nil {
		t.Fatal(e)
	}
	c.Headers.Set("Idempotency-Key", "explicit-key")
	_, _, e := c.Request(context.Background(), "POST", "/x", nil, nil)
	mu.Lock()
	defer mu.Unlock()
	if e == nil || output.Normalize(e).Outcome != "unknown" || reads != 1 || writes != 1 || readAddr == writeAddr {
		t.Fatal(e, reads, writes, readAddr, writeAddr)
	}
}

func TestReadPoolStillReusesConnections(t *testing.T) {
	var mu sync.Mutex
	addresses := []string{}
	s := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		addresses = append(addresses, r.RemoteAddr)
		mu.Unlock()
		w.Write([]byte(`{}`))
	}))
	defer s.Close()
	c, _ := New(s.URL, "", time.Second)
	defer c.HTTP.CloseIdleConnections()
	for i := 0; i < 2; i++ {
		if _, _, e := c.Request(context.Background(), "GET", "/x", nil, nil); e != nil {
			t.Fatal(e)
		}
	}
	mu.Lock()
	defer mu.Unlock()
	if addresses[0] != addresses[1] {
		t.Fatal(addresses)
	}
}
