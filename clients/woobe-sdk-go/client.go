package woobe

import (
	"net"
	"net/http"
	"net/url"
	"os"
	"strings"
	"time"
)

const DefaultBaseURL = "https://api.woobe.com.br"

type Client struct {
	baseURL                string
	httpClient             *http.Client
	maxReconnectAttempts   int
	reconnectBaseDelay     time.Duration
	Connect                *Connector
}

type Option func(*clientConfig) error
type clientConfig struct {
	baseURL              string
	httpClient           *http.Client
	maxReconnectAttempts int
	reconnectBaseDelay   time.Duration
}

func WithBaseURL(v string) Option {
	return func(c *clientConfig) error { c.baseURL = v; return nil }
}
func WithHTTPClient(v *http.Client) Option {
	return func(c *clientConfig) error { if v != nil { c.httpClient = v }; return nil }
}
func WithReconnect(max int, baseDelay time.Duration) Option {
	return func(c *clientConfig) error {
		if max < 0 { max = 0 }
		if baseDelay < 0 { baseDelay = 0 }
		c.maxReconnectAttempts = max
		c.reconnectBaseDelay = baseDelay
		return nil
	}
}

func New(opts ...Option) (*Client, error) {
	base := os.Getenv("WOOBE_BASE_URL")
	if strings.TrimSpace(base) == "" { base = DefaultBaseURL }

	tr := &http.Transport{
		Proxy: http.ProxyFromEnvironment,
		DialContext: (&net.Dialer{Timeout: 30 * time.Second, KeepAlive: 30 * time.Second}).DialContext,
		TLSHandshakeTimeout: 10 * time.Second,
		ForceAttemptHTTP2: true,
		MaxIdleConns: 100,
		IdleConnTimeout: 90 * time.Second,
	}
	cfg := clientConfig{
		baseURL: base,
		httpClient: &http.Client{Transport: tr},
		maxReconnectAttempts: 4,
		reconnectBaseDelay: 250 * time.Millisecond,
	}
	for _, opt := range opts {
		if err := opt(&cfg); err != nil { return nil, err }
	}
	u, err := url.Parse(strings.TrimRight(strings.TrimSpace(cfg.baseURL), "/"))
	if err != nil || u.Scheme == "" || u.Host == "" {
		return nil, &ProtocolError{Message: "invalid Woobe base URL", Cause: err}
	}
	c := &Client{
		baseURL: u.String(),
		httpClient: cfg.httpClient,
		maxReconnectAttempts: cfg.maxReconnectAttempts,
		reconnectBaseDelay: cfg.reconnectBaseDelay,
	}
	c.Connect = &Connector{client: c}
	return c, nil
}

func (c *Client) CloseIdleConnections() { c.httpClient.CloseIdleConnections() }
