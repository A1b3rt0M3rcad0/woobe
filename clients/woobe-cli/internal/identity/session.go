package identity

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/config"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"os"
	"path/filepath"
	"time"
)

type Session struct {
	Cookies []*http.Cookie `json:"cookies"`
	CSRF    string         `json:"csrf"`
	path    string
	origin  *url.URL
}

func Load(dir, origin string) (*Session, http.CookieJar, error) {
	u, e := url.Parse(origin)
	if e != nil {
		return nil, nil, e
	}
	h := sha256.Sum256([]byte(origin))
	s := &Session{path: filepath.Join(dir, hex.EncodeToString(h[:])+".session"), origin: u}
	b, e := os.ReadFile(s.path)
	if e != nil && !os.IsNotExist(e) {
		return nil, nil, e
	}
	if len(b) > 0 {
		if e = json.Unmarshal(b, s); e != nil {
			return nil, nil, e
		}
	}
	j, _ := cookiejar.New(nil)
	for _, c := range s.Cookies {
		if c.Expires.IsZero() || c.Expires.After(time.Now()) {
			v := *u
			v.Path = c.Path
			j.SetCookies(&v, []*http.Cookie{c})
		}
	}
	return s, j, nil
}
func (s *Session) Capture(resp *http.Response) error {
	for _, c := range resp.Cookies() {
		if c.Path == "" {
			c.Path = "/"
		}
		out := s.Cookies[:0]
		for _, old := range s.Cookies {
			if old.Name != c.Name || old.Path != c.Path {
				out = append(out, old)
			}
		}
		s.Cookies = out
		if c.MaxAge >= 0 {
			s.Cookies = append(s.Cookies, c)
		}
	}
	if v := resp.Header.Get("X-CSRF-Token"); v != "" {
		s.CSRF = v
	}
	b, e := json.Marshal(s)
	if e != nil {
		return e
	}
	return config.AtomicWrite(s.path, b, 0600)
}
func (s *Session) Remove() error {
	e := os.Remove(s.path)
	if os.IsNotExist(e) {
		return nil
	}
	return e
}
