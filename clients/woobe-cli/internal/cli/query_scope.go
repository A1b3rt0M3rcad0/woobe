package cli

import "github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"

func (a *App) addScopeQuery(name, id string) error {
	if e := resourceID(id); e != nil {
		return e
	}
	q, e := a.query()
	if e != nil {
		return e
	}
	if values, ok := q[name]; ok {
		if len(values) != 1 || values[0] != id {
			return output.New(2, "query scope conflicts with selected context")
		}
		return nil
	}
	a.Query = append(a.Query, name+"="+id)
	return nil
}
