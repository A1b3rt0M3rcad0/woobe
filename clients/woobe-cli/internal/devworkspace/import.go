package devworkspace

import (
	"crypto/sha256"
	"encoding/json"
	"fmt"
	"gopkg.in/yaml.v3"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strconv"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

type CapturedBinding struct {
	ResourceUID  string            `json:"resource_uid,omitempty"`
	Identifiers  map[string]string `json:"identifiers,omitempty"`
	OwnerAgentID string            `json:"owner_agent_id"`
	Frozen       bool              `json:"frozen"`
	ExportID     string            `json:"export_id"`
	ResourceID   string            `json:"resource_id"`
	Revision     any               `json:"revision"`
	SourceKind   string            `json:"source_kind,omitempty"`
	SnapshotID   string            `json:"snapshot_id,omitempty"`
}

func RewriteReferences(document map[string]any, keys map[string]string) {
	for _, ref := range packagefmt.References(document) {
		next := keys[ref.Key]
		if next == "" {
			continue
		}
		var parent any = document
		parts := strings.Split(strings.TrimPrefix(ref.Path, "/"), "/")
		for _, part := range parts[:len(parts)-1] {
			if object, ok := parent.(map[string]any); ok {
				parent = object[part]
			} else {
				index, _ := strconv.Atoi(part)
				parent = packagefmt.List(parent)[index]
			}
		}
		if object, ok := parent.(map[string]any); ok {
			object[parts[len(parts)-1]] = next
		} else {
			index, _ := strconv.Atoi(parts[len(parts)-1])
			packagefmt.List(parent)[index] = next
		}
	}
}

func localAlias(name string) string {
	var result strings.Builder
	for _, c := range strings.ToLower(name) {
		if c >= 'a' && c <= 'z' || c >= '0' && c <= '9' {
			result.WriteRune(c)
		} else if result.Len() > 0 && !strings.HasSuffix(result.String(), "-") {
			result.WriteByte('-')
		}
	}
	value := strings.Trim(result.String(), "-")
	if value == "" {
		value = "resource"
	}
	if len(value) > 80 {
		value = value[:80]
	}
	if err := validateAuthorPath(value); err != nil {
		value = "resource-" + value
	}
	return value
}

// ImportCapture plans every merge before writing. A conflict returns paths and
// leaves author files, base and registry untouched.
func (c *Config) ImportCapture(bundle *packagebundle.Bundle, state *State, captured map[string]CapturedBinding, credentials map[string]string, alias, destination string) (*Resource, []Conflict, error) {
	entryKey := packagefmt.Text(packagefmt.Object(packagefmt.Object(bundle.Graph.Manifest["spec"])["entrypoint"])["ref"])
	staged := *c
	staged.Resources = append([]Resource{}, c.Resources...)
	nextState := *state
	nextState.Bindings = map[string]Binding{}
	for k, v := range state.Bindings {
		nextState.Bindings[k] = v
	}
	nextState.Credentials = map[string]string{}
	for k, v := range state.Credentials {
		nextState.Credentials[k] = v
	}
	keys := map[string]string{}
	resources := map[string]Resource{}
	ordered := append([]string{}, bundle.Graph.Order...)
	for _, oldKey := range ordered {
		document := bundle.Graph.Components[oldKey]
		kind := packagefmt.Text(document["kind"])
		native := captured[oldKey]
		if native.ResourceUID != "" && !uuidPattern.MatchString(native.ResourceUID) {
			return nil, nil, fmt.Errorf("server returned an invalid logical resource UID")
		}
		if kind != "Prompt" && kind != "Contract" && !uuidPattern.MatchString(native.ResourceID) {
			return nil, nil, fmt.Errorf("server omitted development identity for %s; upgrade Woobe", kind)
		}
		var existing *Resource
		for _, r := range staged.Resources {
			b := state.Bindings[r.UID]
			if r.Kind == kind && native.ResourceID != "" && (b.ResourceID == native.ResourceID || (kind == "Prompt" || kind == "Contract") && native.OwnerAgentID != "" && b.OwnerAgentID == native.OwnerAgentID) {
				// Frozen Network constituents retain a distinct artifact per snapshot.
				frozen := kind == "Agent" && oldKey != entryKey && native.Frozen
				if frozen && b.SnapshotID != native.SnapshotID {
					continue
				}
				if !frozen && r.Frozen {
					continue
				}
				copy := r
				existing = &copy
				break
			}
		}
		if existing == nil {
			uid, err := NewID()
			if err != nil {
				return nil, nil, err
			}
			if native.ResourceUID != "" && !native.Frozen {
				uid = native.ResourceUID
				for _, registered := range staged.Resources {
					if registered.UID == uid {
						return nil, nil, fmt.Errorf("logical UID is already registered with another native binding; recover bindings before pull")
					}
				}
			}
			key := strings.ToLower(kind) + "-" + strings.ReplaceAll(uid, "-", "")[:12]
			name := localAlias(packagefmt.Text(packagefmt.Object(document["metadata"])["name"]))
			if oldKey == entryKey && alias != "" {
				name = alias
			}
			for _, r := range staged.Resources {
				if r.Kind == kind && r.Alias == name {
					name += "-" + key[len(key)-8:]
					break
				}
			}
			folder := KindDirectory(kind) + "/" + name
			frozen := kind == "Agent" && oldKey != entryKey && native.Frozen
			if frozen {
				folder = "snapshots/" + native.ResourceID + "/" + native.SnapshotID
				name += "-" + key[len(key)-8:]
			}
			if oldKey == entryKey && destination != "" {
				absolute, err := filepath.Abs(destination)
				if err != nil {
					return nil, nil, err
				}
				relative, err := filepath.Rel(c.RootPath(), absolute)
				if err != nil {
					return nil, nil, err
				}
				folder = filepath.ToSlash(relative)
			}
			existing = &Resource{UID: uid, Kind: kind, Key: key, Alias: name, Path: folder, Frozen: frozen}
			if frozen {
				existing.SnapshotID = native.SnapshotID
			}
			staged.Resources = append(staged.Resources, *existing)
		}
		if native.ResourceUID != "" && !native.Frozen && existing.UID != native.ResourceUID {
			return nil, nil, fmt.Errorf("local resource UID differs from the owner's canonical identity; recover the original history instead of rewriting identity")
		}
		keys[oldKey] = existing.Key
		resources[oldKey] = *existing
	}
	// Promote credential requirements to explicit Provider resources; native UUIDs
	// are private bindings, while models reference stable logical Provider keys.
	providers := map[string]string{}
	manifestSpec := packagefmt.Object(bundle.Graph.Manifest["spec"])
	requirements := packagefmt.List(packagefmt.Object(manifestSpec["requires"])["credentials"])
	v2 := bundle.Graph.Manifest["schema_version"] == "2.0"
	if v2 {
		aliases := []string{}
		for name := range packagefmt.Object(manifestSpec["connections"]) {
			aliases = append(aliases, name)
		}
		sort.Strings(aliases)
		for _, name := range aliases {
			item := clone(packagefmt.Object(packagefmt.Object(manifestSpec["connections"])[name]))
			item["ref"] = name
			requirements = append(requirements, item)
		}
	}
	for _, raw := range requirements {
		requirement := packagefmt.Object(raw)
		oldAlias := packagefmt.Text(requirement["ref"])
		nativeID := credentials[oldAlias]
		if !uuidPattern.MatchString(nativeID) {
			return nil, nil, fmt.Errorf("server omitted Provider binding")
		}
		var provider Resource
		for _, r := range staged.Resources {
			if r.Kind == "Provider" && state.Bindings[r.UID].ResourceID == nativeID {
				provider = r
				break
			}
		}
		if provider.UID == "" {
			uid, err := NewID()
			if err != nil {
				return nil, nil, err
			}
			key := "provider-" + strings.ReplaceAll(uid, "-", "")[:12]
			provider = Resource{UID: uid, Kind: "Provider", Key: key, Alias: key, Path: "providers/" + key}
			staged.Resources = append(staged.Resources, provider)
		}
		providers[oldAlias] = provider.Key
		nextState.Credentials[provider.Key] = nativeID
		spec := clone(packagefmt.Object(requirement["metadata"]))
		if spec == nil {
			spec = map[string]any{}
		}
		spec["provider"] = requirement["provider"]
		spec["credential_ref"] = provider.Key
		document := map[string]any{"kind": "Provider", "metadata": map[string]any{"key": provider.Key, "name": provider.Alias}, "spec": spec}
		if v2 {
			spec["authentication"] = requirement["authentication"]
			document["format"], document["schema_version"] = "woobe-package", "2.0"
		}
		resources["provider:"+oldAlias] = provider
		nextState.Bindings[provider.UID] = Binding{ResourceID: nativeID, Base: document}
	}
	if err := staged.Validate(); err != nil {
		return nil, nil, err
	}
	writes := map[string][]byte{}
	conflicts := []Conflict{}
	for _, oldKey := range ordered {
		r := resources[oldKey]
		document := clone(bundle.Graph.Components[oldKey])
		RewriteReferences(document, keys)
		packagefmt.Object(document["metadata"])["key"] = r.Key
		spec := packagefmt.Object(document["spec"])
		if r.Kind == "Model" {
			oldAlias := packagefmt.Text(packagefmt.Object(spec["credential"])["ref"])
			delete(spec, "credential")
			spec["provider_ref"] = providers[oldAlias]
		}
		supports, err := packagebundle.SupportPaths(bundle.Graph.Components[oldKey], bundle.Graph.Paths[oldKey])
		if err != nil {
			return nil, nil, err
		}
		mappings := map[string]string{}
		supportBases := map[string]string{}
		for i, source := range supports {
			name := fmt.Sprintf("files/%d/%s", i, filepath.Base(source))
			mappings[source] = name
			data, err := os.ReadFile(filepath.Join(bundle.Root, filepath.FromSlash(source)))
			if err != nil {
				return nil, nil, err
			}
			target := filepath.Join(c.RootPath(), filepath.Dir(filepath.FromSlash(descriptor(r))), filepath.FromSlash(name))
			remoteHash := fmt.Sprintf("%x", sha256.Sum256(data))
			supportBases[name] = remoteHash
			if previous, err := os.ReadFile(target); err == nil {
				localHash := fmt.Sprintf("%x", sha256.Sum256(previous))
				baseHash := state.Bindings[r.UID].Supports[name]
				if localHash == remoteHash {
					continue
				}
				if remoteHash == baseHash {
					continue
				}
				if localHash != baseHash {
					conflicts = append(conflicts, Conflict{Path: r.Path + "/" + name})
					continue
				}
			} else if !os.IsNotExist(err) {
				return nil, nil, err
			}
			writes[target] = data
		}
		rewrite := func(v any) string {
			source, _ := packagebundle.PortablePath(packagefmt.Text(v), bundle.Graph.Paths[oldKey])
			return mappings[source]
		}
		if r.Kind == "Skill" {
			files := packagefmt.Object(spec["package"])
			files["manifest"] = rewrite(files["manifest"])
			values := []any{}
			for _, v := range packagefmt.List(files["resources"]) {
				values = append(values, rewrite(v))
			}
			files["resources"] = values
		}
		if r.Kind == "Knowledge" {
			for _, raw := range packagefmt.List(spec["documents"]) {
				item := packagefmt.Object(raw)
				item["path"] = rewrite(item["path"])
			}
		}
		base := state.Bindings[r.UID].Base
		merged := document
		if base != nil {
			current, err := LoadGraph(c)
			if err != nil {
				return nil, nil, err
			}
			var found []Conflict
			merged, found = Merge(base, current.Nodes[r.Key].Document, document)
			for _, item := range found {
				item.Path = r.Path + item.Path
				conflicts = append(conflicts, item)
			}
		} else if _, err := os.Lstat(filepath.Join(c.RootPath(), descriptor(r))); err == nil {
			return nil, nil, fmt.Errorf("unregistered destination exists; choose another path")
		}
		data, err := EncodeFile(merged, descriptor(r))
		if err != nil {
			return nil, nil, err
		}
		writes[filepath.Join(c.RootPath(), descriptor(r))] = data
		native := captured[oldKey]
		nextState.Bindings[r.UID] = Binding{Identifiers: native.Identifiers, Supports: supportBases, OwnerAgentID: native.OwnerAgentID, ResourceID: native.ResourceID, Revision: native.Revision, SourceKind: native.SourceKind, SnapshotID: native.SnapshotID, ExportID: native.ExportID, SourceComponent: oldKey, Base: document}
	}
	if len(conflicts) > 0 {
		return nil, conflicts, nil
	}
	for oldKey, r := range resources {
		if strings.HasPrefix(oldKey, "provider:") {
			data, err := EncodeFile(nextState.Bindings[r.UID].Base, descriptor(r))
			if err != nil {
				return nil, nil, err
			}
			target := filepath.Join(c.RootPath(), descriptor(r))
			if previous, err := os.ReadFile(target); err == nil {
				existing, err := LoadGraph(c)
				if err != nil {
					return nil, nil, err
				}
				author := existing.Nodes[r.Key].Document
				incoming := nextState.Bindings[r.UID].Base
				authorSpec := packagefmt.Object(author["spec"])
				incomingSpec := packagefmt.Object(incoming["spec"])
				for field, value := range authorSpec {
					if field != "credential_ref" && !reflect.DeepEqual(value, incomingSpec[field]) {
						return nil, nil, fmt.Errorf("Provider connection intent differs at %s; reconcile it explicitly", field)
					}
				}
				// Display metadata and schema markers are local author intent;
				// native connection metadata is authoritative and secret-free.
				merged := clone(author)
				merged["spec"] = clone(incomingSpec)
				binding := nextState.Bindings[r.UID]
				binding.Base = merged
				nextState.Bindings[r.UID] = binding
				data, err = EncodeFile(merged, descriptor(r))
				if err != nil {
					return nil, nil, err
				}
				writes[target] = data
				_ = previous
			} else {
				writes[target] = data
			}
		}
	}
	nextState.Requirements = clone(state.Requirements)
	if nextState.Requirements == nil {
		nextState.Requirements = map[string]any{}
	}
	for group, raw := range packagefmt.Object(packagefmt.Object(bundle.Graph.Manifest["spec"])["requires"]) {
		if group == "credentials" {
			continue
		}
		field := "ref"
		if group == "project_environment" {
			field = "key"
		}
		items := append([]any{}, packagefmt.List(nextState.Requirements[group])...)
		for _, incoming := range packagefmt.List(raw) {
			name := packagefmt.Text(packagefmt.Object(incoming)[field])
			found := false
			for _, existing := range items {
				if packagefmt.Text(packagefmt.Object(existing)[field]) != name {
					continue
				}
				found = true
				if !reflect.DeepEqual(existing, incoming) {
					return nil, nil, fmt.Errorf("shared requirement %s/%s has conflicting definitions", group, name)
				}
			}
			if !found {
				items = append(items, incoming)
			}
		}
		nextState.Requirements[group] = items
	}
	// These requirements retain portable environment/secret names; credentials
	// themselves are represented by Providers and transformed by the compiler.
	delete(nextState.Requirements, "credentials")
	if v2 {
		// Merge declarations as metadata, never resolve a key from local env/files.
		declarations := append([]any{}, packagefmt.List(packagefmt.Object(nextState.Requirements["configuration"])["keys"])...)
		for _, incoming := range packagefmt.List(packagefmt.Object(manifestSpec["configuration"])["keys"]) {
			name := packagefmt.Text(packagefmt.Object(incoming)["key"])
			found := false
			for _, existing := range declarations {
				if packagefmt.Text(packagefmt.Object(existing)["key"]) != name {
					continue
				}
				found = true
				if !reflect.DeepEqual(existing, incoming) {
					return nil, nil, fmt.Errorf("shared configuration declaration %s has conflicting definitions", name)
				}
			}
			if !found {
				declarations = append(declarations, incoming)
			}
		}
		nextState.Requirements["configuration"] = map[string]any{"keys": declarations}
	}
	stateBytes, err := json.MarshalIndent(&nextState, "", "  ")
	if err != nil {
		return nil, nil, err
	}
	configBytes, err := yaml.Marshal(&staged)
	if err != nil {
		return nil, nil, err
	}
	writes[staged.StatePath(nextState.API, nextState.Workspace, nextState.Project)] = stateBytes
	writes[staged.File] = configBytes
	if err := staged.Commit(writes); err != nil {
		return nil, nil, err
	}
	*c = staged
	*state = nextState
	resource := resources[entryKey]
	return &resource, nil, nil
}
