package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	sdk "github.com/A1b3rt0M3rcad0/woobe-sdk-go"
	"testing"
)

func TestRuntimeRevisionDeadlineAndUnsupportedCodes(t *testing.T) {
	for status, code := range map[int]int{412: 6, 408: 8, 504: 8, 405: 9, 501: 9} {
		e := runtimeError(&sdk.RequestError{StatusCode: status})
		if output.Normalize(e).Code != code {
			t.Fatal(status, e)
		}
	}
}
