package manifest

import (
	"bytes"
	"encoding/json"
	"fmt"
	"regexp"
	"strings"
)

type ResourceDocument struct {
	SchemaVersion string     `json:"schema_version"`
	Workspace     string     `json:"workspace_id,omitempty"`
	Project       string     `json:"project_id,omitempty"`
	Resources     []Resource `json:"resources"`
}
type Resource struct {
	Key        string            `json:"key"`
	Kind       string            `json:"kind"`
	Action     string            `json:"action"`
	ResourceID string            `json:"resource_id,omitempty"`
	Parents    map[string]string `json:"parents,omitempty"`
	Spec       json.RawMessage   `json:"spec"`
	DependsOn  []string          `json:"depends_on,omitempty"`
	IfMatch    string            `json:"if_match,omitempty"`
}
type Kind struct {
	Scope       string            `json:"scope"`
	ParentKinds map[string]string `json:"parent_kinds,omitempty"`
	Name        string            `json:"kind"`
	Create      string            `json:"create_command,omitempty"`
	Update      string            `json:"update_command,omitempty"`
	Parents     []string          `json:"parents"`
}

// Only verified configuration routes belong here. No inferred upsert, publication or secrets.
func Kinds() []Kind {
	kinds := []Kind{{Name: "Agent", Create: "project agent create", Update: "project agent update", Parents: []string{}}, {Name: "Network", Create: "project network create", Update: "project network update", Parents: []string{}}, {Name: "AgentPrompt", Create: "project agent prompt create", Parents: []string{"agent"}, ParentKinds: map[string]string{"agent": "Agent"}}, {Name: "AgentContract", Create: "project agent contract create", Update: "project agent contract update", Parents: []string{"agent"}, ParentKinds: map[string]string{"agent": "Agent"}}, {Name: "AgentModelConfig", Create: "project agent model-config create", Parents: []string{"agent"}, ParentKinds: map[string]string{"agent": "Agent"}}, {Name: "Project", Update: "project update", Parents: []string{}}, {Name: "Tool", Create: "project tool create", Update: "project tool update", Parents: []string{}}, {Name: "KnowledgeCollection", Create: "project knowledge collection create", Update: "project knowledge collection update", Parents: []string{}}, {Name: "KnowledgeDocument", Create: "project knowledge document create", Parents: []string{}}, {Name: "Skill", Create: "project skill create", Parents: []string{}}, {Name: "SkillVersion", Create: "project skill version create", Parents: []string{"skill"}, ParentKinds: map[string]string{"skill": "Skill"}}, {Name: "ChatSurface", Create: "project surface create", Update: "project surface update", Parents: []string{}}, {Name: "NetworkDraft", Update: "project network draft update", Parents: []string{}}}
	for i := range kinds {
		kinds[i].Scope = "project"
	}
	kinds = append(kinds, Kind{Name: "AuthorityCategory", Scope: "workspace", Create: "workspace authority category create", Update: "workspace authority category update", Parents: []string{}})
	return kinds
}

var resourceReference = regexp.MustCompile(`^\$\{resources\.([a-zA-Z0-9_-]+)\.([a-zA-Z0-9_.-]+)\}$`)

func resourceRefs(v any) (any, error) {
	switch x := v.(type) {
	case string:
		if m := resourceReference.FindStringSubmatch(x); m != nil {
			return "${steps." + m[1] + "." + m[2] + "}", nil
		}
		if strings.Contains(x, "${resources.") || strings.Contains(x, "${steps.") {
			return nil, fmt.Errorf("resource references must be exact whole values using resources namespace")
		}
		return x, nil
	case map[string]any:
		out := map[string]any{}
		for k, v := range x {
			r, e := resourceRefs(v)
			if e != nil {
				return nil, e
			}
			out[k] = r
		}
		return out, nil
	case []any:
		out := make([]any, len(x))
		for i, v := range x {
			r, e := resourceRefs(v)
			if e != nil {
				return nil, e
			}
			out[i] = r
		}
		return out, nil
	}
	return v, nil
}
func parseResources(b []byte) (Document, error) {
	var source ResourceDocument
	dec := json.NewDecoder(bytes.NewReader(b))
	dec.DisallowUnknownFields()
	if e := dec.Decode(&source); e != nil {
		return Document{}, e
	}
	return source.Compile()
}
func (d ResourceDocument) Compile() (Document, error) {
	out := Document{SchemaVersion: "1", Workspace: d.Workspace, Project: d.Project, SourceVersion: "2"}
	if d.SchemaVersion != "2" || len(d.Resources) == 0 || len(d.Resources) > 1000 {
		return out, fmt.Errorf("resource manifest requires schema_version 2 and 1 to 1000 resources")
	}
	declared := map[string]string{}
	for _, r := range d.Resources {
		if _, ok := declared[r.Key]; ok {
			return out, fmt.Errorf("duplicate resource key")
		}
		declared[r.Key] = r.Kind
	}
	catalog := map[string]Kind{}
	for _, k := range Kinds() {
		catalog[k.Name] = k
	}
	for _, r := range d.Resources {
		k, ok := catalog[r.Kind]
		if !ok {
			return out, fmt.Errorf("unsupported resource kind %s", r.Kind)
		}
		if k.Scope == "workspace" && d.Workspace == "" {
			return out, fmt.Errorf("workspace_id required for %s", r.Kind)
		}
		if k.Scope == "project" && d.Project == "" {
			return out, fmt.Errorf("project_id required for %s", r.Kind)
		}
		if r.Kind == "Project" && r.ResourceID != d.Project {
			return out, fmt.Errorf("Project resource_id must equal document project_id")
		}
		s := Step{ID: r.Key, DependsOn: r.DependsOn, IfMatch: r.IfMatch}
		switch r.Action {
		case "create":
			s.Command = k.Create
			if r.ResourceID != "" || r.IfMatch != "" {
				return out, fmt.Errorf("create does not accept resource_id or if_match")
			}
		case "update":
			s.Command = k.Update
			if r.ResourceID == "" {
				return out, fmt.Errorf("update requires explicit resource_id")
			}
		default:
			return out, fmt.Errorf("resource action must be create or update")
		}
		if s.Command == "" {
			return out, fmt.Errorf("action unsupported for resource kind %s", r.Kind)
		}
		if len(r.Parents) != len(k.Parents) {
			return out, fmt.Errorf("incorrect parent identifiers for %s", r.Kind)
		}
		for _, p := range k.Parents {
			id := r.Parents[p]
			if id == "" {
				return out, fmt.Errorf("parent %s required", p)
			}
			s.Args = append(s.Args, id)
		}
		if r.Action == "update" {
			s.Args = append(s.Args, r.ResourceID)
		}
		for i, arg := range s.Args {
			expected := r.Kind
			if i < len(k.Parents) {
				expected = k.ParentKinds[k.Parents[i]]
			} else if r.Kind == "NetworkDraft" {
				expected = "Network"
			}
			if m := resourceReference.FindStringSubmatch(arg); m != nil {
				if declared[m[1]] != expected || m[2] != "id" {
					return out, fmt.Errorf("resource ID reference has incompatible kind or field")
				}
			}
			v, e := resourceRefs(arg)
			if e != nil {
				return out, e
			}
			s.Args[i] = v.(string)
			if arg == "." || arg == ".." {
				return out, fmt.Errorf("invalid resource identifier")
			}
		}
		var spec map[string]any
		dec := json.NewDecoder(bytes.NewReader(r.Spec))
		dec.UseNumber()
		if e := dec.Decode(&spec); e != nil || spec == nil {
			return out, fmt.Errorf("resource spec must be an object")
		}
		if r.Kind == "AuthorityCategory" {
			if e := ValidateCategorySpec(spec, r.Action == "create"); e != nil {
				return out, e
			}
			if r.Action == "update" && r.IfMatch == "" {
				return out, fmt.Errorf("category update requires explicit if_match")
			}
		}

		if scope, ok := spec["project_id"]; ok && scope != d.Project {
			return out, fmt.Errorf("resource project_id differs from document scope")
		}
		if r.Kind == "Agent" && r.Action == "create" {
			spec["project_id"] = d.Project
		}
		v, e := resourceRefs(spec)
		if e != nil {
			return out, e
		}
		s.Body, e = json.Marshal(v)
		if e != nil {
			return out, e
		}
		out.Steps = append(out.Steps, s)
	}
	_, e := out.Order()
	return out, e
}

// ValidateCategorySpec excludes assignment, identity and lifecycle fields from imports.
func ValidateCategorySpec(spec map[string]any, create bool) error {
	allowed := map[string]bool{"name": true, "description": true, "permissions": true, "conditions": true, "catalog_revision": true}
	if create {
		allowed["scope"] = true
	}
	for field := range spec {
		if !allowed[field] {
			return fmt.Errorf("category spec field %s is not configuration", field)
		}
	}
	return nil
}
