package cli

import "github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"

func notAttempted(err error) error {
	if err == nil {
		return nil
	}
	e := *output.Normalize(err)
	e.Outcome = "not_attempted"
	if e.Code == 1 {
		e.Code = 2
	}
	return &e
}
