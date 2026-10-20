package manifest

import "testing"

func TestProtectedSecretReferences(t *testing.T) {
	for _, body := range []string{`{"api_key":{"$secret_ref":"provider-prod"}}`, `{"config":{"headers":{"Authorization":{"$secret_ref":"http-auth"}}}}`} {
		if e := validateBody([]byte(body)); e != nil {
			t.Fatal(e)
		}
	}
	for _, body := range []string{`{"api_key":"literal"}`, `{"api_key":{"$secret_ref":"../escape"}}`, `{"api_key":{"$secret_ref":"good","prefix":"Bearer"}}`, `{"name":{"$secret_ref":"good"}}`, `{"api_key":"${secrets.good}"}`} {
		if validateBody([]byte(body)) == nil {
			t.Fatal(body)
		}
	}
}
