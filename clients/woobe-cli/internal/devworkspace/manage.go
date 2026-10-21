package devworkspace

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"gopkg.in/yaml.v3"
)

// Add creates an explicitly new local identity. It never infers a remote
// binding from display names, and validates references before committing.
func (c *Config) Add(kind, alias, destination string, document map[string]any, supports map[string][]byte, dryRun bool) (Resource, error) {
	uid, err := NewID()
	if err != nil {
		return Resource{}, err
	}
	if destination == "" {
		destination = KindDirectory(kind) + "/" + alias
	}
	resource := Resource{UID: uid, Kind: kind, Key: alias, Alias: alias, Path: destination}
	next := *c
	next.Resources = append(append([]Resource{}, c.Resources...), resource)
	if err := next.Validate(); err != nil {
		return Resource{}, err
	}
	document = clone(document)
	if document["kind"] != kind {
		return Resource{}, fmt.Errorf("descriptor kind must match the requested resource")
	}
	metadata := packagefmt.Object(document["metadata"])
	if metadata == nil {
		return Resource{}, fmt.Errorf("descriptor requires metadata")
	}
	metadata["key"] = alias
	data, err := EncodeFile(document, descriptor(resource))
	if err != nil {
		return Resource{}, err
	}
	node, err := decodeNode(resource, data)
	if err != nil {
		return Resource{}, err
	}
	graph, err := LoadGraph(c)
	if err != nil {
		return Resource{}, err
	}
	graph.Nodes[resource.Key] = node
	if err = graph.Validate(); err != nil {
		return Resource{}, err
	}
	writes := map[string][]byte{filepath.Join(c.RootPath(), descriptor(resource)): data}
	sources, err := authorSupportPaths(document, descriptor(resource))
	if err != nil {
		return Resource{}, err
	}
	for _, source := range sources {
		name, err := filepath.Rel(filepath.Dir(filepath.FromSlash(descriptor(resource))), filepath.FromSlash(source))
		if err != nil {
			return Resource{}, err
		}
		content, exists := supports[filepath.ToSlash(name)]
		if !exists {
			return Resource{}, fmt.Errorf("declared support file must be copied explicitly: %s", name)
		}
		writes[filepath.Join(c.RootPath(), filepath.FromSlash(source))] = content
	}
	for path := range writes {
		if err := c.validateAuthorWrite(path); err != nil {
			return Resource{}, err
		}
		if _, err := os.Lstat(path); !os.IsNotExist(err) {
			return Resource{}, fmt.Errorf("destination already exists or cannot be inspected")
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
	return resource, nil
}

func (c *Config) Clone(kind, reference, alias, destination string, dryRun bool) (Resource, error) {
	return c.CloneWithState(kind, reference, alias, destination, nil, dryRun)
}

func (c *Config) CloneWithState(kind, reference, alias, destination string, state *State, dryRun bool) (Resource, error) {
	resource, err := c.Resolve(kind, reference)
	if err != nil {
		return Resource{}, err
	}
	graph, err := LoadGraph(c)
	if err != nil {
		return Resource{}, err
	}
	node := graph.Nodes[resource.Key]
	if kind == "Agent" {
		return c.cloneAgent(graph, node, alias, destination, state, dryRun)
	}
	sources, err := authorSupportPaths(node.Document, node.Descriptor)
	if err != nil {
		return Resource{}, err
	}
	root, err := os.OpenRoot(c.RootPath())
	if err != nil {
		return Resource{}, err
	}
	defer root.Close()
	supports := map[string][]byte{}
	for _, source := range sources {
		name, err := filepath.Rel(filepath.Dir(filepath.FromSlash(node.Descriptor)), filepath.FromSlash(source))
		if err != nil {
			return Resource{}, err
		}
		data, err := packagebundle.ReadConfined(root, source, packagebundle.MaxFileBytes)
		if err != nil {
			return Resource{}, err
		}
		supports[filepath.ToSlash(name)] = data
	}
	document := clone(node.Document)
	if kind == "Skill" {
		if err := cloneSkillManifest(document, supports, alias); err != nil {
			return Resource{}, err
		}
	}
	if kind == "Skill" {
		packagefmt.Object(document["metadata"])["name"] = alias
	}
	return c.Add(resource.Kind, alias, destination, document, supports, dryRun)
}

// Register links an existing descriptor. Files stay in place and metadata is
// committed only after the complete resulting graph passes validation.
func (c *Config) Register(kind, alias, path string, dryRun bool) (Resource, error) {
	uid, err := NewID()
	if err != nil {
		return Resource{}, err
	}
	resource := Resource{UID: uid, Kind: kind, Alias: alias, Path: path}
	if _, err := c.ResourcePath(resource); err != nil {
		return Resource{}, err
	}
	root, err := os.OpenRoot(c.RootPath())
	if err != nil {
		return Resource{}, err
	}
	defer root.Close()
	data, err := readConfined(root, descriptor(resource))
	if err != nil {
		return Resource{}, err
	}
	// Decode the key without changing the existing author file.
	var parsed map[string]any
	if err = yaml.Unmarshal(data, &parsed); err != nil {
		return Resource{}, err
	}
	resource.Key = packagefmt.Text(packagefmt.Object(parsed["metadata"])["key"])
	next := *c
	next.Resources = append(append([]Resource{}, c.Resources...), resource)
	if _, err := LoadGraph(&next); err != nil {
		return Resource{}, err
	}
	encoded, err := yaml.Marshal(&next)
	if err != nil {
		return Resource{}, err
	}
	if !dryRun {
		if err = c.Commit(map[string][]byte{c.File: encoded}); err != nil {
			return Resource{}, err
		}
		*c = next
	}
	return resource, nil
}

func (c *Config) Unregister(kind, reference string, dryRun bool) error {
	resource, err := c.Resolve(kind, reference)
	if err != nil {
		return err
	}
	// Native bindings and files remain recoverable. This operation never calls
	// remote deletion and never removes shared author files.
	next := *c
	next.Resources = []Resource{}
	for _, candidate := range c.Resources {
		if candidate.UID != resource.UID {
			next.Resources = append(next.Resources, candidate)
		}
	}
	// Validate the registry that would remain, allowing a missing selected
	// descriptor to be unregistered while still rejecting live consumers.
	if _, err := LoadGraph(&next); err != nil {
		return err
	}
	data, err := yaml.Marshal(&next)
	if err != nil {
		return err
	}
	if !dryRun {
		if err = c.Commit(map[string][]byte{c.File: data}); err != nil {
			return err
		}
		*c = next
	}
	return nil
}

func CanonicalKind(kind string) string {
	for candidate := range kinds {
		if strings.EqualFold(candidate, kind) {
			return candidate
		}
	}
	return ""
}

// Move preserves UID, logical key and native bindings. Only the descriptor and
// declared support files move; unregistered files and shared supports remain.
func (c *Config) Move(kind, reference, destination string, dryRun bool) error {
	resource, err := c.Resolve(kind, reference)
	if err != nil {
		return err
	}
	next := *c
	next.Resources = append([]Resource{}, c.Resources...)
	for i := range next.Resources {
		if next.Resources[i].UID == resource.UID {
			next.Resources[i].Path = destination
		}
	}
	if err := next.Validate(); err != nil {
		return err
	}
	moved := *resource
	moved.Path = destination
	graph, err := LoadGraph(c)
	if err != nil {
		return err
	}
	node := graph.Nodes[resource.Key]
	sources, err := authorSupportPaths(node.Document, node.Descriptor)
	if err != nil {
		return err
	}
	targets, err := authorSupportPaths(node.Document, descriptor(moved))
	if err != nil || len(targets) != len(sources) {
		return fmt.Errorf("invalid destination support paths")
	}
	sources = append(sources, node.Descriptor)
	targets = append(targets, descriptor(moved))
	shared := map[string]bool{}
	for _, other := range graph.Nodes {
		if other.Resource.UID == resource.UID {
			continue
		}
		paths, err := authorSupportPaths(other.Document, other.Descriptor)
		if err != nil {
			return err
		}
		for _, path := range append(paths, other.Descriptor) {
			shared[path] = true
		}
	}
	root, err := os.OpenRoot(c.RootPath())
	if err != nil {
		return err
	}
	defer root.Close()
	writes := map[string][]byte{}
	removals := []string{}
	for i, source := range sources {
		target := filepath.Join(c.RootPath(), filepath.FromSlash(targets[i]))
		if err := c.validateAuthorWrite(target); err != nil {
			return err
		}
		if _, err := os.Lstat(target); !os.IsNotExist(err) {
			return fmt.Errorf("move destination already exists")
		}
		data, err := packagebundle.ReadConfined(root, source, packagebundle.MaxFileBytes)
		if err != nil {
			return err
		}
		if source == node.Descriptor && strings.EqualFold(filepath.Ext(source), ".json") != strings.EqualFold(filepath.Ext(targets[i]), ".json") {
			data, err = EncodeFile(node.Document, targets[i])
			if err != nil {
				return err
			}
		}
		writes[target] = data
		if !shared[source] {
			removals = append(removals, filepath.Join(c.RootPath(), filepath.FromSlash(source)))
		}
	}
	// Move portable tracking/history with the stable UID. Objects stay shared at
	// the workspace root; private operational state is not copied into author files.
	oldHistory, err := c.historyDirectory(*resource)
	if err != nil {
		return err
	}
	newHistory, err := c.historyDirectory(moved)
	if err != nil {
		return err
	}
	if oldHistory != newHistory {
		if _, err := c.ReadTracking(*resource); err == nil {
			if _, err := c.VerifyHistory(*resource); err != nil {
				return err
			}
			names := []string{strings.ToLower(resource.Kind) + ".lock.yaml", "revisions", "releases", "deployments"}
			for _, name := range names {
				sourceBase := filepath.Join(oldHistory, name)
				walkErr := filepath.WalkDir(sourceBase, func(path string, entry fs.DirEntry, readErr error) error {
					if os.IsNotExist(readErr) && path == sourceBase {
						return nil
					}
					if readErr != nil {
						return readErr
					}
					if entry.IsDir() {
						return nil
					}
					if strings.HasPrefix(entry.Name(), ".asac-") {
						return nil
					}
					relative, err := filepath.Rel(oldHistory, path)
					if err != nil {
						return err
					}
					target := filepath.Join(newHistory, relative)
					if err := c.validateAuthorWrite(target); err != nil {
						return err
					}
					if _, err := os.Lstat(target); !os.IsNotExist(err) {
						return fmt.Errorf("move history destination already exists")
					}
					data, err := c.ReadOperationalFile(path, packagebundle.MaxFileBytes)
					if err != nil {
						return err
					}
					writes[target] = data
					removals = append(removals, path)
					return nil
				})
				if walkErr != nil {
					return walkErr
				}
			}
		} else if !os.IsNotExist(err) {
			return err
		}
	}
	data, err := yaml.Marshal(&next)
	if err != nil {
		return err
	}
	writes[c.File] = data
	if !dryRun {
		if err := c.CommitFiles(writes, removals); err != nil {
			return err
		}
		*c = next
	}
	return nil
}

func (c *Config) Alias(kind, reference, alias string, dryRun bool) error {
	resource, err := c.Resolve(kind, reference)
	if err != nil {
		return err
	}
	next := *c
	next.Resources = append([]Resource{}, c.Resources...)
	for i := range next.Resources {
		if next.Resources[i].UID == resource.UID {
			next.Resources[i].Alias = alias
		}
	}
	if err := next.Validate(); err != nil {
		return err
	}
	data, err := yaml.Marshal(&next)
	if err != nil {
		return err
	}
	if !dryRun {
		if err := c.Commit(map[string][]byte{c.File: data}); err != nil {
			return err
		}
		*c = next
	}
	return nil
}
