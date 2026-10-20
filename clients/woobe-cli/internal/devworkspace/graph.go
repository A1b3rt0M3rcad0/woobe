package devworkspace

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/requestinput"
)

type Node struct {
	Resource     Resource
	Document     map[string]any
	Descriptor   string
	Dependencies []string
}
type Graph struct {
	Config *Config
	Nodes  map[string]*Node
}

func descriptor(resource Resource) string {
	if strings.HasSuffix(resource.Path, ".yaml") || strings.HasSuffix(resource.Path, ".yml") || strings.HasSuffix(resource.Path, ".json") {
		return resource.Path
	}
	return resource.Path + "/" + strings.ToLower(resource.Kind) + ".yaml"
}

func readConfined(root *os.Root, path string) ([]byte, error) {
	return packagebundle.ReadConfined(root, path, requestinput.MaxBytes)
}

func LoadGraph(config *Config) (*Graph, error) {
	if err := config.Validate(); err != nil {
		return nil, err
	}
	graph := &Graph{Config: config, Nodes: map[string]*Node{}}
	if len(config.Resources) == 0 {
		return graph, nil
	}
	info, err := os.Lstat(config.RootPath())
	if errors.Is(err, os.ErrNotExist) {
		return nil, fmt.Errorf("configured artifact root is missing; .woobe-config still registers %d resources; restore the directory or preview stale entries with woobe resources prune --dry-run", len(config.Resources))
	}
	if err != nil || !info.IsDir() || info.Mode()&os.ModeSymlink != 0 {
		return nil, fmt.Errorf("artifact root must be a real directory")
	}
	root, err := os.OpenRoot(config.RootPath())
	if err != nil {
		return nil, err
	}
	defer root.Close()
	for _, resource := range config.Resources {
		path := descriptor(resource)
		data, err := readConfined(root, path)
		if err != nil {
			return nil, descriptorReadError(resource, err)
		}
		node, err := decodeNode(resource, data)
		if err != nil {
			return nil, err
		}
		graph.Nodes[resource.Key] = node
	}
	if err := graph.Validate(); err != nil {
		return nil, err
	}
	return graph, nil
}

func descriptorReadError(resource Resource, err error) error {
	if errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("%s: registered descriptor %q is missing; .woobe-config still references it; restore the file or preview stale entries with woobe resources prune --dry-run", resource.Key, descriptor(resource))
	}
	return fmt.Errorf("%s: cannot safely read registered descriptor %q: %w", resource.Key, descriptor(resource), err)
}

func decodeNode(resource Resource, data []byte) (*Node, error) {
	data, err := requestinput.Decode(data, descriptor(resource), "auto")
	if err != nil {
		return nil, fmt.Errorf("%s: %w", resource.Key, err)
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	var document map[string]any
	if err := decoder.Decode(&document); err != nil {
		return nil, fmt.Errorf("resource descriptor must be an object")
	}
	metadata := packagefmt.Object(document["metadata"])
	if document["kind"] != resource.Kind || metadata["key"] != resource.Key {
		return nil, fmt.Errorf("resource descriptor identity differs from its registry entry")
	}
	if _, err := authorSupportPaths(document, descriptor(resource)); err != nil {
		return nil, err
	}
	node := &Node{Resource: resource, Document: document, Descriptor: descriptor(resource)}
	for _, ref := range packagefmt.References(document) {
		node.Dependencies = append(node.Dependencies, ref.Key)
	}
	spec := packagefmt.Object(document["spec"])
	if resource.Kind == "Provider" {
		if err := validateProvider(spec); err != nil {
			return nil, fmt.Errorf("%s: %w", resource.Key, err)
		}
	}
	if resource.Kind == "Model" {
		if ref := packagefmt.Text(spec["provider_ref"]); ref != "" {
			node.Dependencies = append(node.Dependencies, ref)
		}
	}
	if resource.Kind == "Skill" {
		for _, ref := range packagefmt.List(spec["tool_refs"]) {
			key := packagefmt.Text(packagefmt.Object(ref)["ref"])
			if key == "" {
				return nil, fmt.Errorf("Skill tool_refs require a resource ref")
			}
			node.Dependencies = append(node.Dependencies, key)
		}
	}
	if resource.Kind == "Surface" {
		if ref := packagefmt.Text(spec["target_ref"]); ref != "" {
			node.Dependencies = append(node.Dependencies, ref)
		}
	}
	sort.Strings(node.Dependencies)
	return node, nil
}

func (g *Graph) Validate() error {
	for key, node := range g.Nodes {
		for _, dependency := range node.Dependencies {
			if g.Nodes[dependency] == nil {
				return fmt.Errorf("%s references missing resource %s", key, dependency)
			}
		}
		for _, ref := range packagefmt.References(node.Document) {
			if g.Nodes[ref.Key].Resource.Kind != ref.Kind {
				return fmt.Errorf("resource reference has the wrong kind")
			}
		}
		if node.Resource.Kind == "Model" {
			if ref := packagefmt.Text(packagefmt.Object(node.Document["spec"])["provider_ref"]); ref != "" && g.Nodes[ref].Resource.Kind != "Provider" {
				return fmt.Errorf("Model provider_ref must reference a Provider")
			}
		}

		if node.Resource.Kind == "Skill" {
			for _, ref := range packagefmt.List(packagefmt.Object(node.Document["spec"])["tool_refs"]) {
				if g.Nodes[packagefmt.Text(packagefmt.Object(ref)["ref"])].Resource.Kind != "Tool" {
					return fmt.Errorf("Skill tool_refs must reference Tools")
				}
			}
		}
		if node.Resource.Kind == "Surface" {
			ref := packagefmt.Text(packagefmt.Object(node.Document["spec"])["target_ref"])
			if ref != "" && g.Nodes[ref].Resource.Kind != "Agent" && g.Nodes[ref].Resource.Kind != "Network" {
				return fmt.Errorf("Surface target_ref must reference an Agent or Network")
			}
		}
	}
	for key := range g.Nodes {
		if _, err := g.Closure(key); err != nil {
			return err
		}
	}
	return nil
}

func (g *Graph) Closure(key string) ([]*Node, error) {
	seen := map[string]bool{}
	visiting := map[string]bool{}
	var result []*Node
	var visit func(string) error
	visit = func(key string) error {
		if visiting[key] {
			return fmt.Errorf("resource dependency cycle")
		}
		if seen[key] {
			return nil
		}
		node := g.Nodes[key]
		if node == nil {
			return fmt.Errorf("resource is not registered")
		}
		visiting[key] = true
		for _, dependency := range node.Dependencies {
			if err := visit(dependency); err != nil {
				return err
			}
		}
		delete(visiting, key)
		seen[key] = true
		result = append(result, node)
		return nil
	}
	if err := visit(key); err != nil {
		return nil, err
	}
	return result, nil
}

func (g *Graph) UsedBy(key string) []Resource {
	var result []Resource
	for candidate, node := range g.Nodes {
		if candidate == key {
			continue
		}
		closure, err := g.Closure(candidate)
		if err != nil {
			continue
		}
		for _, dependency := range closure {
			if dependency.Resource.Key == key {
				result = append(result, node.Resource)
				break
			}
		}
	}
	sort.Slice(result, func(i, j int) bool { return result[i].Key < result[j].Key })
	return result
}

func (g *Graph) Path(node *Node) string {
	return filepath.Join(g.Config.RootPath(), filepath.FromSlash(node.Descriptor))
}

// A Provider is public connection intent, never credential material. Strict
// fields keep newly introduced authentication mechanisms out of author files.
func validateProvider(spec map[string]any) error {
	for key := range spec {
		if key == "authentication" {
			document := map[string]any{"format": "woobe-package", "schema_version": "2.0", "kind": "Package", "metadata": map[string]any{"name": "Provider", "version": "1"}, "spec": map[string]any{"entrypoint": map[string]any{"kind": "Agent", "ref": "agent"}, "resources": []any{"agent.yaml"}, "connections": map[string]any{"provider": map[string]any{"provider": spec["provider"], "name": "Provider", "authentication": spec[key]}}}}
			if err := packagefmt.Validate(&packagefmt.Document{Value: document}); err != nil {
				return fmt.Errorf("Provider authentication must contain remote configuration references only")
			}
			continue
		}
		switch key {
		case "provider", "credential_ref", "base_url", "compatibility", "provider_family":
		default:
			return fmt.Errorf("Provider contains unsupported fields; store credentials through auth/provider commands")
		}
		if _, ok := spec[key].(string); !ok {
			return fmt.Errorf("Provider fields must be strings")
		}
	}
	if packagefmt.Text(spec["provider"]) == "" {
		return fmt.Errorf("Provider requires provider; bind its native credential with resources bind")
	}
	if raw := packagefmt.Text(spec["base_url"]); raw != "" {
		parsed, err := url.Parse(raw)
		if err != nil || parsed.Host == "" || (parsed.Scheme != "http" && parsed.Scheme != "https") || parsed.User != nil || parsed.RawQuery != "" || parsed.Fragment != "" {
			return fmt.Errorf("Provider base_url must be an HTTP(S) endpoint without credentials, query or fragment")
		}
	}
	return nil
}
