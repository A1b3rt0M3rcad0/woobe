package controlplane

import (
	"crypto/tls"
	"net/http"
)

// Read calls reuse a pool. Writes use fresh HTTP/1 connections so Transport
// cannot replay an Idempotency-Key request after a reused connection fails.
type noReplayTransport struct{ reads, writes *http.Transport }

func newNoReplayTransport() *noReplayTransport {
	base, ok := http.DefaultTransport.(*http.Transport)
	if !ok {
		base = &http.Transport{Proxy: http.ProxyFromEnvironment}
	}
	reads, writes := base.Clone(), base.Clone()
	writes.DisableKeepAlives = true
	writes.ForceAttemptHTTP2 = false
	if writes.TLSClientConfig == nil {
		writes.TLSClientConfig = &tls.Config{NextProtos: []string{"http/1.1"}}
	} else {
		writes.TLSClientConfig = writes.TLSClientConfig.Clone()
		writes.TLSClientConfig.NextProtos = []string{"http/1.1"}
	}
	writes.TLSNextProto = map[string]func(string, *tls.Conn) http.RoundTripper{}
	return &noReplayTransport{reads: reads, writes: writes}
}
func (t *noReplayTransport) RoundTrip(r *http.Request) (*http.Response, error) {
	if r.Method == http.MethodGet || r.Method == http.MethodHead {
		return t.reads.RoundTrip(r)
	}
	copy := r.Clone(r.Context())
	copy.GetBody = nil
	return t.writes.RoundTrip(copy)
}
func (t *noReplayTransport) CloseIdleConnections() {
	t.reads.CloseIdleConnections()
	t.writes.CloseIdleConnections()
}

var sharedNoReplayTransport = newNoReplayTransport()
