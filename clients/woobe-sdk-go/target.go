package woobe

import (
	"context"
	"fmt"
	"strings"
)

type ChatOptions struct {
	SessionID       string
	TenantID        string
	UserID          string
	Metadata        map[string]any
	ExternalContext map[string]any
}
type RunOptions = ChatOptions

func (t runtimeTarget) Alias() string { return t.alias }

func (t runtimeTarget) Chat(input string, opts *ChatOptions) (*Chat, error) {
	if strings.TrimSpace(input) == "" { return nil, &ProtocolError{Message: "input must not be empty"} }
	var o ChatOptions
	if opts != nil { o = *opts }
	return newChat(t, input, o), nil
}
func (t runtimeTarget) Run(ctx context.Context, input string, opts *RunOptions) (*RunResult, error) {
	if strings.TrimSpace(input) == "" { return nil, &ProtocolError{Message: "input must not be empty"} }
	var o RunOptions
	if opts != nil { o = *opts }
	return t.client.run(ctx, t.key, input, o)
}
func (t runtimeTarget) ValidateContracts(ctx context.Context, req ContractValidationRequest) (*RuntimeContractsValidation, error) {
	return t.client.validateContracts(ctx, t.key, req)
}
func (t runtimeTarget) ActiveRun(ctx context.Context, sessionID string) (*ActiveRun, error) {
	if strings.TrimSpace(sessionID) == "" { return nil, &ProtocolError{Message: "sessionID must not be empty"} }
	return t.client.activeRun(ctx, t.key, sessionID)
}
func (t runtimeTarget) CancelRun(ctx context.Context, runID string) error {
	if strings.TrimSpace(runID) == "" { return &ProtocolError{Message: "runID must not be empty"} }
	return t.client.cancelRun(ctx, t.key, runID)
}
func (t runtimeTarget) ObserveRun(ctx context.Context, runID string) (*Stream, error) {
	if strings.TrimSpace(runID) == "" { return nil, &ProtocolError{Message: "runID must not be empty"} }
	chat := &Chat{client: t.client, targetKind: t.kind, targetAlias: t.alias, key: t.key, runID: runID, started: true}
	return chat.start(ctx, "reattach")
}

func (a *Agent) Alias() string { return a.runtimeTarget.Alias() }
func (n *Network) Alias() string { return n.runtimeTarget.Alias() }
func (a *Agent) String() string { return fmt.Sprintf("Agent(%s)", a.alias) }
func (n *Network) String() string { return fmt.Sprintf("Network(%s)", n.alias) }
