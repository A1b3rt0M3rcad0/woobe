package manifest

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"io"
	"regexp"
)

type Document struct {
	SchemaVersion string `json:"schema_version"`
	Workspace     string `json:"workspace_id"`
	Project       string `json:"project_id"`
	Steps         []Step `json:"steps"`
	SourceVersion string `json:"-"`
}
type Step struct {
	ID        string          `json:"id"`
	Command   string          `json:"command"`
	Args      []string        `json:"args,omitempty"`
	Body      json.RawMessage `json:"body,omitempty"`
	DependsOn []string        `json:"depends_on,omitempty"`
	IfMatch   string          `json:"if_match,omitempty"`
}

func Parse(b []byte) (Document, error) {
	var d Document
	if e := jsoninput.Validate(b); e != nil {
		return d, e
	}
	var header struct {
		SchemaVersion string `json:"schema_version"`
	}
	if e := json.Unmarshal(b, &header); e != nil {
		return d, e
	}
	if header.SchemaVersion == "2" {
		return parseResources(b)
	}
	dec := json.NewDecoder(bytes.NewReader(b))
	dec.DisallowUnknownFields()
	if e := dec.Decode(&d); e != nil {
		return d, e
	}
	var extra any
	if e := dec.Decode(&extra); e != io.EOF {
		return d, fmt.Errorf("expected one manifest document")
	}
	if d.SchemaVersion != "1" {
		return d, fmt.Errorf("schema_version must be 1")
	}
	if len(d.Steps) == 0 || len(d.Steps) > 1000 {
		return d, fmt.Errorf("manifest requires 1 to 1000 steps")
	}
	_, e := d.Order()
	return d, e
}
func (d Document) Hash() string {
	b, _ := json.Marshal(d)
	var v any
	dec := json.NewDecoder(bytes.NewReader(b))
	dec.UseNumber()
	if dec.Decode(&v) == nil {
		b, _ = json.Marshal(v)
	}
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

var stepID = regexp.MustCompile(`^[a-zA-Z0-9_-]{1,128}$`)

func (d Document) Order() ([]Step, error) {
	byID := map[string]Step{}
	for _, s := range d.Steps {
		if !stepID.MatchString(s.ID) || s.Command == "" {
			return nil, fmt.Errorf("step id and command required")
		}
		if _, ok := byID[s.ID]; ok {
			return nil, fmt.Errorf("duplicate step id %s", s.ID)
		}
		if e := validateBody(s.Body); e != nil {
			return nil, e
		}
		if e := ValidateReferences(s); e != nil {
			return nil, e
		}
		byID[s.ID] = s
	}
	state := map[string]int{}
	out := []Step{}
	var visit func(string) error
	visit = func(id string) error {
		if state[id] == 2 {
			return nil
		}
		if state[id] == 1 {
			return fmt.Errorf("dependency cycle at %s", id)
		}
		s, ok := byID[id]
		if !ok {
			return fmt.Errorf("missing dependency %s", id)
		}
		state[id] = 1
		for _, dep := range s.DependsOn {
			if e := visit(dep); e != nil {
				return e
			}
		}
		state[id] = 2
		out = append(out, s)
		return nil
	}
	for _, s := range d.Steps {
		if e := visit(s.ID); e != nil {
			return nil, e
		}
	}
	return out, nil
}

func (d Document) Version() string {
	if d.SourceVersion != "" {
		return d.SourceVersion
	}
	return d.SchemaVersion
}
