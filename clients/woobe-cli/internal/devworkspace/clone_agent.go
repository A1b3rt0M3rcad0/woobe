package devworkspace

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"gopkg.in/yaml.v3"
)

// Clone Agent-owned artifacts in one journal transaction. Project dependencies
// keep their registered identities; no native bindings are inherited.
func (c *Config) cloneAgent(graph *Graph, source *Node, alias, destination string, state *State, dryRun bool) (Resource, error) {
	next := *c
	next.Resources = append([]Resource{}, c.Resources...)
	copyGraph := &Graph{Config: &next, Nodes: map[string]*Node{}}
	for key, node := range graph.Nodes {
		copyGraph.Nodes[key] = node
	}
	owned := map[string]bool{source.Resource.Key: true}
	for _, ref := range packagefmt.References(source.Document) {
		if ref.Kind == "Prompt" || ref.Kind == "Contract" {
			owned[ref.Key] = true
		}
		if ref.Kind == "Tool" && state != nil {
			tool := graph.Nodes[ref.Key]
			binding := state.Bindings[tool.Resource.UID]
			owner := state.Bindings[source.Resource.UID].ResourceID
			if owner != "" && binding.OwnerAgentID == owner {
				owned[ref.Key] = true
			}
		}
	}
	keys := map[string]string{source.Resource.Key: alias}
	for key := range owned {
		if key != source.Resource.Key {
			keys[key] = alias + "-" + key
		}
	}
	root, err := os.OpenRoot(c.RootPath())
	if err != nil {
		return Resource{}, err
	}
	defer root.Close()
	writes := map[string][]byte{}
	var result Resource
	for oldKey, key := range keys {
		node := graph.Nodes[oldKey]
		uid, err := NewID()
		if err != nil {
			return Resource{}, err
		}
		path := KindDirectory(node.Resource.Kind) + "/" + key
		if oldKey == source.Resource.Key && destination != "" {
			path = destination
		}
		resource := Resource{UID: uid, Kind: node.Resource.Kind, Key: key, Alias: key, Path: path}
		document := clone(node.Document)
		metadata := packagefmt.Object(document["metadata"])
		metadata["key"] = key
		if oldKey == source.Resource.Key {
			result = resource
		}
		rewriteCloneRefs(document, keys)
		data, err := EncodeFile(document, descriptor(resource))
		if err != nil {
			return Resource{}, err
		}
		copied, err := decodeNode(resource, data)
		if err != nil {
			return Resource{}, err
		}
		next.Resources = append(next.Resources, resource)
		copyGraph.Nodes[key] = copied
		writes[filepath.Join(c.RootPath(), descriptor(resource))] = data
		supports, err := authorSupportPaths(node.Document, node.Descriptor)
		if err != nil {
			return Resource{}, err
		}
		for _, support := range supports {
			rel, err := filepath.Rel(filepath.Dir(node.Descriptor), support)
			if err != nil {
				return Resource{}, err
			}
			content, err := packagebundle.ReadConfined(root, support, packagebundle.MaxFileBytes)
			if err != nil {
				return Resource{}, err
			}
			writes[filepath.Join(c.RootPath(), filepath.Dir(descriptor(resource)), rel)] = content
		}
	}
	if err := next.Validate(); err != nil {
		return Resource{}, err
	}
	if err := copyGraph.Validate(); err != nil {
		return Resource{}, err
	}
	for path := range writes {
		if err := c.validateAuthorWrite(path); err != nil {
			return Resource{}, err
		}
		if _, err := os.Lstat(path); !os.IsNotExist(err) {
			return Resource{}, fmt.Errorf("clone destination already exists or cannot be inspected")
		}
	}
	config, err := yaml.Marshal(&next)
	if err != nil {
		return Resource{}, err
	}
	writes[c.File] = config
	if !dryRun {
		if err = c.Commit(writes); err != nil {
			return Resource{}, err
		}
		*c = next
	}
	return result, nil
}

func rewriteCloneRefs(document map[string]any, keys map[string]string) {
	for _, reference := range packagefmt.References(document) {
		key, exists := keys[reference.Key]
		if !exists {
			continue
		}
		parts := strings.Split(strings.TrimPrefix(reference.Path, "/"), "/")
		// Agent-owned references use maps, except tool lists.
		if reference.Kind == "Tool" {
			for _, raw := range packagefmt.List(packagefmt.Object(document["spec"])["tools"]) {
				ref := packagefmt.Object(raw)
				if ref["ref"] == reference.Key {
					ref["ref"] = key
				}
			}
			continue
		}
		current := document
		for _, part := range parts[:len(parts)-1] {
			current = packagefmt.Object(current[part])
		}
		current[parts[len(parts)-1]] = key
	}
}
