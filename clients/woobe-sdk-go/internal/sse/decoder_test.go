package sse

import "testing"

func TestDecoderMultilineData(t *testing.T) {
	d := NewDecoder()
	if d.Feed("event: token") != nil { t.Fatal("unexpected") }
	d.Feed("id: 7")
	d.Feed("data: {\"a\":")
	d.Feed("data: 1}")
	f := d.Feed("")
	if f == nil || f.Event != "token" || f.ID != "7" || string(f.Data) != "{\"a\":\n1}" {
		t.Fatalf("frame=%#v", f)
	}
}
