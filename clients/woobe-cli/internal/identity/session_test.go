package identity

import (
	"net/http"
	"net/url"
	"testing"
)

func TestSessionOriginAndCookiePaths(t *testing.T) {
	dir := t.TempDir()
	s, _, e := Load(dir, "https://api.example")
	if e != nil {
		t.Fatal(e)
	}
	h := http.Header{}
	h.Add("Set-Cookie", "access=fixture; Path=/; Secure; HttpOnly")
	h.Add("Set-Cookie", "refresh=fixture; Path=/identity/auth; Secure; HttpOnly")
	h.Set("X-CSRF-Token", "csrf-fixture")
	if e = s.Capture(&http.Response{Header: h}); e != nil {
		t.Fatal(e)
	}
	restored, jar, e := Load(dir, "https://api.example")
	if e != nil || restored.CSRF != "csrf-fixture" {
		t.Fatal(e)
	}
	u, _ := url.Parse("https://api.example/identity/auth/refresh")
	if len(jar.Cookies(u)) != 2 {
		t.Fatal("refresh path not restored")
	}
	other, jar, _ := Load(dir, "https://other.example")
	if other.CSRF != "" || len(jar.Cookies(u)) != 0 {
		t.Fatal("cross-origin session")
	}
}
