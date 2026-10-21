package packagefmt

import (
	"fmt"
	"sort"
)

type Reference struct{ Key, Kind, Path string }
type Graph struct {
	Manifest   map[string]any
	Components map[string]map[string]any
	Paths      map[string]string
	Order      []string
}

func Object(value any) map[string]any { object, _ := value.(map[string]any); return object }
func Text(value any) string           { text, _ := value.(string); return text }
func List(value any) []any            { list, _ := value.([]any); return list }

func Requirements(manifest map[string]any) map[string]any {
	spec := Object(manifest["spec"])
	if manifest["schema_version"] != "2.0" {
		return Object(spec["requires"])
	}
	credentials := []any{}
	for alias, raw := range Object(spec["connections"]) {
		credentials = append(credentials, map[string]any{"ref": alias, "provider": Object(raw)["provider"]})
	}
	return map[string]any{"credentials": credentials, "project_environment": Object(spec["configuration"])["keys"], "knowledge": Object(spec["requires"])["knowledge"]}
}

func References(document map[string]any) []Reference {
	spec := Object(document["spec"])
	refs := []Reference{}
	add := func(value any, kind, path string) {
		if key := Text(value); key != "" {
			refs = append(refs, Reference{key, kind, path})
		}
	}
	switch Text(document["kind"]) {
	case "Agent":
		for _, role := range []string{"primary", "fallback"} {
			add(Object(Object(spec["model"])[role])["ref"], "Model", "/spec/model/"+role+"/ref")
		}
		for _, pair := range []struct{ Name, Kind string }{{"tools", "Tool"}, {"skills", "Skill"}} {
			for i, value := range List(spec[pair.Name]) {
				add(Object(value)["ref"], pair.Kind, fmt.Sprintf("/spec/%s/%d/ref", pair.Name, i))
			}
		}
		add(spec["prompt_ref"], "Prompt", "/spec/prompt_ref")
		add(Object(spec["output"])["contract_ref"], "Contract", "/spec/output/contract_ref")
		add(Object(Object(spec["knowledge"])["source"])["ref"], "Knowledge", "/spec/knowledge/source/ref")
	case "Network":
		for i, value := range List(spec["nodes"]) {
			add(Object(value)["agent_ref"], "Agent", fmt.Sprintf("/spec/nodes/%d/agent_ref", i))
		}
	case "Knowledge":
		add(Object(spec["embedding"])["model_ref"], "Model", "/spec/embedding/model_ref")
	}
	return refs
}

func Resolve(manifest map[string]any, documents map[string]*Document) (*Graph, error) {
	graph := &Graph{Manifest: manifest, Components: map[string]map[string]any{}, Paths: map[string]string{}}
	fail := func(code, message, file, path string) error {
		return &Diagnostic{Code: code, Message: message, File: file, Path: path}
	}
	paths := make([]string, 0, len(documents))
	for path := range documents {
		paths = append(paths, path)
	}
	sort.Strings(paths)
	for _, path := range paths {
		document := documents[path].Value
		if document["schema_version"] != manifest["schema_version"] {
			return nil, fail("PACKAGE_SCHEMA_UNSUPPORTED", "Components must use the manifest schema version", path, "")
		}
		kind := Text(document["kind"])
		if kind == "Package" || kind == "PackageLock" || kind == "ImportBindings" {
			return nil, fail("PACKAGE_RESOURCE_INVALID", "Operational documents cannot be components", path, "")
		}
		key := Text(Object(document["metadata"])["key"])
		if _, exists := graph.Components[key]; exists {
			return nil, fail("PACKAGE_REFERENCE_DUPLICATE", "Component key is duplicated", path, "/metadata/key")
		}
		graph.Components[key], graph.Paths[key] = document, path
	}
	entry := Object(Object(manifest["spec"])["entrypoint"])
	if target, ok := graph.Components[Text(entry["ref"])]; !ok || target["kind"] != entry["kind"] {
		return nil, fail("PACKAGE_REFERENCE_NOT_FOUND", "Entrypoint does not resolve to its declared kind", "", "")
	}
	adjacency := map[string][]string{}
	declared := Requirements(manifest)
	knowledgeRequirements := map[string]bool{}
	for _, group := range []string{"credentials", "project_environment", "secrets", "knowledge"} {
		field := "ref"
		if group == "project_environment" {
			field = "key"
		}
		aliases := map[string]bool{}
		for _, raw := range List(declared[group]) {
			alias := Text(Object(raw)[field])
			if aliases[alias] {
				return nil, fail("PACKAGE_REQUIREMENT_DUPLICATE", "Destination requirement is duplicated", "", "/spec/requires/"+group)
			}
			aliases[alias] = true
		}
		if group == "knowledge" {
			knowledgeRequirements = aliases
		}
	}
	requirements := map[string]string{}
	for _, raw := range List(declared["credentials"]) {
		requirement := Object(raw)
		alias := Text(requirement["ref"])
		if _, exists := requirements[alias]; exists {
			return nil, fail("PACKAGE_REQUIREMENT_DUPLICATE", "Credential requirement is duplicated", "", "")
		}
		requirements[alias] = Text(requirement["provider"])
	}
	if manifest["schema_version"] == "2.0" {
		keys := map[string]string{}
		for _, raw := range List(declared["project_environment"]) {
			item := Object(raw)
			kind := Text(item["kind"])
			if kind == "" {
				kind = "secret"
			}
			if _, exists := keys[Text(item["key"])]; exists {
				return nil, fail("PACKAGE_REQUIREMENT_DUPLICATE", "Configuration key is duplicated", "", "")
			}
			keys[Text(item["key"])] = kind
		}
		auths := []map[string]any{}
		for _, raw := range Object(Object(manifest["spec"])["connections"]) {
			auths = append(auths, Object(Object(raw)["authentication"]))
		}
		for _, item := range graph.Components {
			if item["kind"] == "Tool" {
				config := Object(Object(item["spec"])["config"])
				auths = append(auths, Object(config["authentication"]))
				for _, raw := range List(config["routes"]) {
					if auth := Object(raw)["authentication"]; auth != nil {
						auths = append(auths, Object(auth))
					}
				}
			}
		}
		for _, auth := range auths {
			for _, raw := range Object(auth["fields"]) {
				if keys[Text(Object(raw)["key"])] != "secret" {
					return nil, fail("PACKAGE_REQUIREMENT_INVALID", "Authentication requires a declared secret configuration key", "", "")
				}
			}
		}
	}
	keys := make([]string, 0, len(graph.Components))
	for key := range graph.Components {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	for _, key := range keys {
		document := graph.Components[key]
		spec := Object(document["spec"])
		if document["kind"] == "Model" {
			provider, exists := requirements[Text(Object(spec["credential"])["ref"])]
			if !exists || provider != Text(spec["provider"]) {
				return nil, fail("PACKAGE_REQUIREMENT_INVALID", "Model credential must reference a declared requirement with the same provider", graph.Paths[key], "/spec/credential/ref")
			}
		}
		if document["kind"] == "Network" {
			if err := validateNetworkStructure(spec, graph.Paths[key]); err != nil {
				return nil, err
			}
		}
		for _, ref := range References(document) {
			target, exists := graph.Components[ref.Key]
			if !exists {
				return nil, fail("PACKAGE_REFERENCE_NOT_FOUND", "Component reference is missing", graph.Paths[key], ref.Path)
			}
			if target["kind"] != ref.Kind {
				return nil, fail("PACKAGE_REFERENCE_KIND", "Component reference has the wrong kind", graph.Paths[key], ref.Path)
			}
			adjacency[key] = append(adjacency[key], ref.Key)
		}
		if document["kind"] == "Agent" {
			sources := 0
			for _, field := range []string{"behavior", "prompt_ref", "legacy_system_prompt"} {
				if value, ok := spec[field]; ok && value != nil {
					sources++
				}
			}
			if sources != 1 {
				return nil, fail("PACKAGE_BEHAVIOR_CONFLICT", "Agent requires exactly one instruction source", graph.Paths[key], "")
			}
			for _, value := range List(spec["skills"]) {
				binding := Object(value)
				target := graph.Components[Text(binding["ref"])]
				if Object(target["spec"])["version"] != binding["version"] {
					return nil, fail("PACKAGE_REFERENCE_VERSION", "Skill version assertion differs from descriptor", graph.Paths[key], "")
				}
			}
		}
		if document["kind"] == "Knowledge" {
			if spec["mode"] == "binding" && !knowledgeRequirements[Text(Object(spec["binding"])["ref"])] {
				return nil, fail("PACKAGE_REQUIREMENT_NOT_FOUND", "Knowledge binding must declare a destination requirement", graph.Paths[key], "")
			}
			if spec["mode"] == "portable" {
				if len(Object(spec["collection"])) == 0 || len(List(spec["documents"])) == 0 || len(Object(spec["embedding"])) == 0 || Object(spec["vector_snapshot"]) == nil || len(Object(spec["binding"])) != 0 {
					return nil, fail("PACKAGE_KNOWLEDGE_INVALID", "Portable Knowledge requires documents, collection, embedding and build configuration", graph.Paths[key], "")
				}
			} else if len(Object(spec["binding"])) == 0 || len(Object(spec["collection"])) != 0 || len(List(spec["documents"])) != 0 || len(Object(spec["embedding"])) != 0 || len(Object(spec["vector_snapshot"])) != 0 {
				return nil, fail("PACKAGE_KNOWLEDGE_INVALID", "Binding Knowledge must contain only a destination requirement", graph.Paths[key], "")
			}
		}
	}
	visiting, visited := map[string]bool{}, map[string]bool{}
	var visit func(string) error
	visit = func(key string) error {
		if visiting[key] {
			return fail("PACKAGE_REFERENCE_CYCLE", "Component reference cycle", graph.Paths[key], "")
		}
		if visited[key] {
			return nil
		}
		visiting[key] = true
		for _, child := range adjacency[key] {
			if err := visit(child); err != nil {
				return err
			}
		}
		delete(visiting, key)
		visited[key] = true
		graph.Order = append(graph.Order, key)
		return nil
	}
	for _, key := range keys {
		if err := visit(key); err != nil {
			return nil, err
		}
	}
	return graph, nil
}

func validateNetworkStructure(spec map[string]any, file string) error {
	fail := func(message string) error {
		return &Diagnostic{Code: "PACKAGE_NETWORK_INVALID", Message: message, File: file}
	}
	nodes := map[string]bool{}
	adjacency := map[string][]string{}
	for _, raw := range List(spec["nodes"]) {
		key := Text(Object(raw)["key"])
		if nodes[key] {
			return fail("Network requires unique node keys and a declared root")
		}
		nodes[key] = true
	}
	root := Text(spec["root"])
	if !nodes[root] {
		return fail("Network requires unique node keys and a declared root")
	}
	edges := map[[2]string]bool{}
	for _, raw := range List(spec["edges"]) {
		edge := Object(raw)
		pair := [2]string{Text(edge["from"]), Text(edge["to"])}
		if edges[pair] || !nodes[pair[0]] || !nodes[pair[1]] {
			return fail("Network edge is duplicated or references an unknown node")
		}
		edges[pair] = true
		adjacency[pair[0]] = append(adjacency[pair[0]], pair[1])
	}
	colors := map[string]uint8{}
	var visit func(string) error
	visit = func(key string) error {
		if colors[key] == 1 {
			return fail("Network graph contains a cycle")
		}
		if colors[key] == 2 {
			return nil
		}
		colors[key] = 1
		for _, child := range adjacency[key] {
			if err := visit(child); err != nil {
				return err
			}
		}
		colors[key] = 2
		return nil
	}
	if err := visit(root); err != nil {
		return err
	}
	if len(colors) != len(nodes) {
		return fail("Network contains nodes unreachable from the root")
	}
	return nil
}
