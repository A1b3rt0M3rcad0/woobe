package cli

import (
	"context"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/manifest"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"strings"
)

func (a *App) observeUnchanged(ctx context.Context, s manifest.Step) (any, bool, error) {
	op, ok := a.operation(s.Command)
	if !ok {
		return nil, false, output.New(2, "unknown configuration operation")
	}
	if op.Method == "POST" {
		return nil, false, nil
	}
	getter, ok := a.operation(strings.TrimSuffix(s.Command, " update") + " get")
	if !ok || getter.Method != "GET" || getter.Path != op.Path {
		return nil, false, output.New(9, "skip-unchanged requires a compatible canonical getter")
	}
	current, meta, e := a.readResource(ctx, getter, s.Args)
	if e != nil {
		return nil, false, e
	}
	if s.Command == "workspace authority category update" {
		if e := verifyCategoryObservation(current, meta, a.Workspace, s.Args[0]); e != nil {
			return nil, false, e
		}
	}
	if s.IfMatch != "" && meta["etag"] == "" {
		return nil, false, output.New(9, "skip-unchanged cannot verify if_match without an observed ETag")
	}
	if s.IfMatch != "" && meta["etag"] != "" && s.IfMatch != meta["etag"] {
		return nil, false, output.New(6, "observed resource revision differs from if_match")
	}
	desired, e := desiredFields(s.Body)
	if e != nil {
		return nil, false, e
	}
	changes, e := configurationChanges(s.Command, current, desired)
	if e != nil {
		return nil, false, e
	}
	return current, len(changes) == 0, nil
}
