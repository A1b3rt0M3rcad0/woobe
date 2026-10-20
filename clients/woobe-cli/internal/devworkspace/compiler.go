package devworkspace

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"os"
	"path"
	"path/filepath"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

// AcceptedBases uses the compiled inventory, rather than rereading support files
// after a request: local edits made during upload must remain unsynchronized.
func (g *Graph) AcceptedBases(bundle *packagebundle.Bundle) (map[string]Binding, error) {
	files := map[string]string{}
	for _, item := range bundle.Inventory {
		files[item.Path] = item.SHA256
	}
	result := map[string]Binding{}
	for key := range bundle.Graph.Components {
		node := g.Nodes[key]
		binding := Binding{Base: node.Document, Supports: map[string]string{}}
		sources, err := authorSupportPaths(node.Document, node.Descriptor)
		if err != nil {
			return nil, err
		}
		for i, source := range sources {
			name, err := filepath.Rel(filepath.Dir(filepath.FromSlash(node.Descriptor)), filepath.FromSlash(source))
			if err != nil {
				return nil, err
			}
			compiled := fmt.Sprintf("support/%s/%d/%s", node.Resource.UID, i, path.Base(source))
			binding.Supports[filepath.ToSlash(name)] = files[compiled]
		}
		result[node.Resource.UID] = binding
	}
	return result, nil
}

func (g *Graph) Changes(resource Resource, binding Binding) ([]Change, error) {
	node := g.Nodes[resource.Key]
	changes := Diff(binding.Base, node.Document)
	root, err := os.OpenRoot(g.Config.RootPath())
	if err != nil {
		return nil, err
	}
	defer root.Close()
	sources, err := authorSupportPaths(node.Document, node.Descriptor)
	if err != nil {
		return nil, err
	}
	for _, source := range sources {
		name, err := filepath.Rel(filepath.Dir(filepath.FromSlash(node.Descriptor)), filepath.FromSlash(source))
		if err != nil {
			return nil, err
		}
		data, err := packagebundle.ReadConfined(root, source, packagebundle.MaxFileBytes)
		if err != nil {
			return nil, err
		}
		if fmt.Sprintf("%x", sha256.Sum256(data)) != binding.Supports[filepath.ToSlash(name)] {
			changes = append(changes, Change{Path: "/files/" + filepath.ToSlash(name), Status: "modified"})
		}
	}
	return changes, nil
}

func (g *Graph) ClosureChanges(resource Resource, state *State) ([]Change, error) {
	nodes, err := g.Closure(resource.Key)
	if err != nil {
		return nil, err
	}
	result := []Change{}
	for _, node := range nodes {
		changes, err := g.Changes(node.Resource, state.Bindings[node.Resource.UID])
		if err != nil {
			return nil, err
		}
		for _, change := range changes {
			if node.Resource.UID != resource.UID {
				change.Path = "/dependencies/" + node.Resource.Kind + "/" + node.Resource.Alias + change.Path
			}
			result = append(result, change)
		}
	}
	return result, nil
}

func clone(document map[string]any) map[string]any {
	raw, _ := json.Marshal(document)
	var result map[string]any
	decoder := json.NewDecoder(strings.NewReader(string(raw)))
	decoder.UseNumber()
	_ = decoder.Decode(&result)
	return result
}

// Compile creates a closed, disposable bundle. It follows registered graph
// edges, copies declared support files and never broadens package path rules.
const CurrentCompilerRecipe = "woobe-development-compiler@3.0"
const previousCompilerRecipe = "woobe-development-compiler@2.0"

func supportedCompilerRecipe(recipe string) bool {
	return recipe == "" || recipe == previousCompilerRecipe || recipe == CurrentCompilerRecipe
}

func (g *Graph) Compile(key string, requirements map[string]any, credentialIDs map[string]string) (*packagebundle.Bundle, map[string]any, error) {
	return g.compileRecipe(key, requirements, credentialIDs, CurrentCompilerRecipe)
}

// Historical source verification preserves the exact previous compiler recipe.
// New writes/checkpoints always use the current recipe.
func (g *Graph) compileRecipe(key string, requirements map[string]any, credentialIDs map[string]string, recipe string) (*packagebundle.Bundle, map[string]any, error) {
	if !supportedCompilerRecipe(recipe) {
		return nil, nil, fmt.Errorf("unsupported retained compiler recipe")
	}

	nodes, err := g.Closure(key)
	if err != nil {
		return nil, nil, err
	}
	entry := g.Nodes[key]
	version := "1.0"
	for _, node := range nodes {
		if node.Document["schema_version"] == "2.0" || packagefmt.Object(node.Document["spec"])["authentication"] != nil {
			version = "2.0"
		}
	}
	if version == "2.0" && recipe != CurrentCompilerRecipe {
		return nil, nil, fmt.Errorf("retained compiler recipe does not support configuration references")
	}
	if entry.Resource.Kind != "Agent" && entry.Resource.Kind != "Network" {
		return nil, nil, fmt.Errorf("package entrypoint must be an Agent or Network")
	}
	directory, err := os.MkdirTemp("", "woobe-development-compile-")
	if err != nil {
		return nil, nil, err
	}
	defer os.RemoveAll(directory)
	root, err := os.OpenRoot(g.Config.RootPath())
	if err != nil {
		return nil, nil, err
	}
	defer root.Close()
	req := clone(requirements)
	if req == nil {
		req = map[string]any{}
	}
	if version == "1.0" {
		delete(req, "configuration")
	}
	credentials := map[string]any{}
	connections := map[string]any{}
	declared := map[string]bool{}
	for _, item := range packagefmt.List(req["credentials"]) {
		declared[packagefmt.Text(packagefmt.Object(item)["ref"])] = true
	}
	descriptors := []string{}
	copied := map[string]bool{}
	write := func(name string, data []byte) error {
		if copied[name] {
			return fmt.Errorf("compiled support path is duplicated")
		}
		copied[name] = true
		target := filepath.Join(directory, filepath.FromSlash(name))
		if err := os.MkdirAll(filepath.Dir(target), 0700); err != nil {
			return err
		}
		return os.WriteFile(target, data, 0600)
	}
	for _, node := range nodes {
		if node.Resource.Kind == "Provider" {
			continue
		}
		document := clone(node.Document)
		if version == "2.0" {
			document["schema_version"] = version
		}
		spec := packagefmt.Object(document["spec"])
		if node.Resource.Kind == "Model" {
			if providerKey := packagefmt.Text(spec["provider_ref"]); providerKey != "" {
				provider := packagefmt.Object(g.Nodes[providerKey].Document["spec"])
				delete(spec, "provider_ref")
				spec["provider"] = provider["provider"]
				spec["credential"] = map[string]any{"ref": providerKey}
				if recipe == "" {
					// Source objects issued before recipes were explicit used this
					// lowering, including its override. Verify those immutable
					// objects as issued instead of relabeling their definition.
					if base := packagefmt.Text(provider["base_url"]); base != "" {
						spec["base_url"] = base
					}
				}
				// Provider connection defaults belong to credential requirements.
				// Preserve the Model's explicit override (including its absence),
				// otherwise an untouched frozen export changes definition on push.
				if version == "2.0" {
					if provider["authentication"] == nil {
						return nil, nil, fmt.Errorf("Provider %s needs explicit remote authentication before compiling schema 2.0", providerKey)
					}
					connection := map[string]any{"provider": provider["provider"], "name": packagefmt.Object(g.Nodes[providerKey].Document["metadata"])["name"], "authentication": provider["authentication"]}
					metadata := map[string]any{}
					for _, field := range []string{"base_url", "compatibility", "provider_family"} {
						if value := packagefmt.Text(provider[field]); value != "" {
							metadata[field] = value
						}
					}
					if len(metadata) > 0 {
						connection["metadata"] = metadata
					}
					connections[providerKey] = connection
				} else if !declared[providerKey] {
					requirement := map[string]any{"ref": providerKey, "provider": provider["provider"]}
					metadata := map[string]any{}
					for _, field := range []string{"base_url", "compatibility", "provider_family"} {
						if value := packagefmt.Text(provider[field]); value != "" {
							metadata[field] = value
						}
					}
					if len(metadata) > 0 {
						requirement["metadata"] = metadata
					}
					req["credentials"] = append(packagefmt.List(req["credentials"]), requirement)
					declared[providerKey] = true
				}
				id := credentialIDs[providerKey]
				if id == "" && uuidPattern.MatchString(packagefmt.Text(provider["credential_ref"])) {
					id = packagefmt.Text(provider["credential_ref"])
				}
				if id != "" {
					credentials[providerKey] = map[string]any{"credential_id": id}
				}
			}
		}
		if node.Resource.Kind == "Skill" {
			for _, raw := range packagefmt.List(spec["tool_refs"]) {
				tool := g.Nodes[packagefmt.Text(packagefmt.Object(raw)["ref"])]
				spec["required_tools"] = append(packagefmt.List(spec["required_tools"]), packagefmt.Text(packagefmt.Object(tool.Document["metadata"])["name"]))
			}
			delete(spec, "tool_refs")
		}
		sourcePaths, err := authorSupportPaths(document, node.Descriptor)
		if err != nil {
			return nil, nil, err
		}
		pathMap := map[string]string{}
		for i, source := range sourcePaths {
			destination := fmt.Sprintf("support/%s/%d/%s", node.Resource.UID, i, path.Base(source))
			data, err := packagebundle.ReadConfined(root, source, packagebundle.MaxFileBytes)
			if err != nil {
				return nil, nil, fmt.Errorf("declared support file is unavailable")
			}
			if err = write(destination, data); err != nil {
				return nil, nil, err
			}
			pathMap[source] = destination
		}
		rewrite := func(value any) any {
			source, _ := packagebundle.PortablePath(packagefmt.Text(value), node.Descriptor)
			return pathMap[source]
		}
		if node.Resource.Kind == "Skill" {
			files := packagefmt.Object(spec["package"])
			files["manifest"] = rewrite(files["manifest"])
			values := []any{}
			for _, value := range packagefmt.List(files["resources"]) {
				values = append(values, rewrite(value))
			}
			files["resources"] = values
		}
		if node.Resource.Kind == "Knowledge" {
			for _, raw := range packagefmt.List(spec["documents"]) {
				item := packagefmt.Object(raw)
				item["path"] = rewrite(item["path"])
			}
		}
		descriptor := node.Resource.Key + ".yaml"
		descriptors = append(descriptors, descriptor)
		data, err := Encode(document)
		if err != nil {
			return nil, nil, err
		}
		if err = write(descriptor, data); err != nil {
			return nil, nil, err
		}
	}
	manifestSpec := map[string]any{"entrypoint": map[string]any{"kind": entry.Resource.Kind, "ref": key}, "resources": descriptors, "requires": req, "integrity": map[string]any{"algorithm": "sha256"}}
	if version == "2.0" {
		manifestSpec["configuration"] = packagefmt.Object(req["configuration"])
		if manifestSpec["configuration"] == nil {
			manifestSpec["configuration"] = map[string]any{"keys": []any{}}
		}
		manifestSpec["connections"] = connections
		structuralRequires := clone(req)
		for _, group := range []string{"configuration", "credentials", "secrets", "project_environment"} {
			delete(structuralRequires, group)
		}
		manifestSpec["requires"] = structuralRequires
	}
	manifest := map[string]any{"format": "woobe-package", "schema_version": version, "kind": "Package", "metadata": map[string]any{"name": packagefmt.Object(entry.Document["metadata"])["name"], "version": "0.0.0+development"}, "spec": manifestSpec}
	data, err := Encode(manifest)
	if err != nil {
		return nil, nil, err
	}
	if err = write("woobe.yaml", data); err != nil {
		return nil, nil, err
	}
	bundle, err := packagebundle.Load(directory, false)
	if err != nil {
		return nil, nil, err
	}
	bindingSpec := map[string]any{"credentials": credentials, "knowledge": map[string]any{}}
	for _, group := range []string{"project_environment", "secrets"} {
		values := map[string]any{}
		for _, raw := range packagefmt.List(req[group]) {
			item := packagefmt.Object(raw)
			field := "ref"
			if group == "project_environment" {
				field = "key"
			}
			alias := packagefmt.Text(item[field])
			values[alias] = map[string]any{"existing_key": alias}
		}
		bindingSpec[group] = values
	}
	if version == "2.0" {
		delete(bindingSpec, "secrets")
		for _, raw := range credentials {
			packagefmt.Object(raw)["create"] = false
		}
		values := map[string]any{}
		for _, raw := range packagefmt.List(packagefmt.Object(manifestSpec["configuration"])["keys"]) {
			name := packagefmt.Text(packagefmt.Object(raw)["key"])
			values[name] = map[string]any{"existing_key": name, "create": false}
		}
		bindingSpec["project_environment"] = values
	}
	bindings := map[string]any{"format": "woobe-package", "schema_version": version, "kind": "ImportBindings", "metadata": map[string]any{"name": "Development", "description": ""}, "spec": bindingSpec}
	return bundle, bindings, nil
}
