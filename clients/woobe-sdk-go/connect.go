package woobe

import "strings"

type Connector struct{ client *Client }

func (c *Connector) Agent(alias, key string) (*Agent, error) {
	t, err := newRuntimeTarget(c.client, alias, key, RunKindAgent)
	if err != nil { return nil, err }
	return &Agent{runtimeTarget: t}, nil
}
func (c *Connector) Network(alias, key string) (*Network, error) {
	t, err := newRuntimeTarget(c.client, alias, key, RunKindNetwork)
	if err != nil { return nil, err }
	return &Network{runtimeTarget: t}, nil
}

type runtimeTarget struct {
	client *Client
	alias  string
	key    string
	kind   RunKind
}

func newRuntimeTarget(c *Client, alias, key string, kind RunKind) (runtimeTarget, error) {
	alias = strings.TrimSpace(alias)
	key = strings.TrimSpace(key)
	if alias == "" { return runtimeTarget{}, &ProtocolError{Message: "alias must not be empty"} }
	if key == "" { return runtimeTarget{}, &ProtocolError{Message: "key must not be empty"} }
	return runtimeTarget{client: c, alias: alias, key: key, kind: kind}, nil
}

type Agent struct{ runtimeTarget }
type Network struct{ runtimeTarget }
