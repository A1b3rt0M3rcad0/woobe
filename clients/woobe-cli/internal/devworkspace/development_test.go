package devworkspace

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
)

func completeGraph(t *testing.T) (*Config, *Graph) {
	t.Helper()
	data, err := os.ReadFile("../../testdata/package/shared/complete.json")
	if err != nil {
		t.Fatal(err)
	}
	var fixture struct {
		Files map[string]string `json:"files"`
	}
	if err = json.Unmarshal(data, &fixture); err != nil {
		t.Fatal(err)
	}
	c, err := Create(t.TempDir(), ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	os.MkdirAll(c.RootPath(), 0700)
	for path, content := range fixture.Files {
		target := filepath.Join(c.RootPath(), filepath.FromSlash(path))
		os.MkdirAll(filepath.Dir(target), 0700)
		os.WriteFile(target, []byte(content), 0600)
	}
	bundle, err := packagebundle.Load(c.RootPath(), false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	for key, document := range bundle.Graph.Components {
		uid, _ := NewID()
		c.Resources = append(c.Resources, Resource{UID: uid, Kind: packagefmt.Text(document["kind"]), Key: key, Alias: key, Path: bundle.Graph.Paths[key]})
	}
	g, err := LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	return c, g
}
func TestCompilerKeepsClosureSupportTypesAndFrozenNodes(t *testing.T) {
	_, g := completeGraph(t)
	req := map[string]any{"credentials": []any{map[string]any{"ref": "primary", "provider": "custom"}}, "project_environment": []any{map[string]any{"key": "PACKAGE_TEST_TOKEN", "kind": "secret"}}, "secrets": []any{map[string]any{"ref": "package-tool-token"}}}
	bundle, _, err := g.Compile("support-network", req, nil)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	if len(bundle.Graph.Components) != len(g.Nodes) {
		t.Fatal("closure dropped components", len(bundle.Graph.Components), len(g.Nodes))
	}
	if !reflect.DeepEqual(packagefmt.Object(bundle.Graph.Components["support-network"]["spec"])["nodes"], packagefmt.Object(g.Nodes["support-network"].Document["spec"])["nodes"]) {
		t.Fatal("Network node identities changed")
	}
	if _, ok := packagefmt.Object(packagefmt.Object(bundle.Graph.Components["specialist"]["spec"])["model"])["parameters"].(map[string]any); !ok {
		t.Fatal("model parameters lost")
	}
	for _, file := range bundle.Inventory {
		if strings.HasPrefix(file.Path, ".state") {
			t.Fatal("private state exported")
		}
	}
}
func TestThreeWayMergeHandlesIndependentEditsNullDeletionAndAtomicLists(t *testing.T) {
	base := map[string]any{"spec": map[string]any{"name": "before", "description": "before", "nullable": nil, "nodes": []any{"a", "b"}}}
	local := clone(base)
	remote := clone(base)
	packagefmt.Object(local["spec"])["name"] = "local"
	packagefmt.Object(remote["spec"])["description"] = "remote"
	merged, conflicts := Merge(base, local, remote)
	if len(conflicts) != 0 || packagefmt.Object(merged["spec"])["name"] != "local" || packagefmt.Object(merged["spec"])["description"] != "remote" {
		t.Fatal(merged, conflicts)
	}
	delete(packagefmt.Object(local["spec"]), "nullable")
	packagefmt.Object(remote["spec"])["nullable"] = "value"
	_, conflicts = Merge(base, local, remote)
	if len(conflicts) != 1 || conflicts[0].Path != "/spec/nullable" {
		t.Fatal(conflicts)
	}
	local = clone(base)
	remote = clone(base)
	packagefmt.Object(local["spec"])["nodes"] = []any{"a", "b", "c"}
	packagefmt.Object(remote["spec"])["nodes"] = []any{"b", "a"}
	_, conflicts = Merge(base, local, remote)
	if len(conflicts) != 1 || conflicts[0].Path != "/spec/nodes" {
		t.Fatal(conflicts)
	}
}
func TestStateScopesConnectionsAndPreservesNumericRevisions(t *testing.T) {
	c, _ := Create(t.TempDir(), ".woobe", "")
	a, _ := c.ReadState("https://one", "workspace", "project")
	a.Bindings["agent"] = Binding{ResourceID: "native", Revision: json.Number("7"), Base: map[string]any{"temperature": json.Number("0.23")}}
	if err := c.WriteState(a); err != nil {
		t.Fatal(err)
	}
	loaded, err := c.ReadState("https://one", "workspace", "project")
	if err != nil || loaded.Bindings["agent"].Revision != json.Number("7") {
		t.Fatal(loaded, err)
	}
	other, err := c.ReadState("https://two", "workspace", "project")
	if err != nil || len(other.Bindings) != 0 {
		t.Fatal("cross-connection binding leak", other, err)
	}
}
func TestCompilerRejectsEscapedAndSymlinkSupport(t *testing.T) {
	c, g := completeGraph(t)
	spec := packagefmt.Object(g.Nodes["support-skill"].Document["spec"])
	packagefmt.Object(spec["package"])["manifest"] = "../../outside.md"
	if b, _, err := g.Compile("support", nil, nil); err == nil {
		b.Close()
		t.Fatal("escaped support accepted")
	}
	c, g = completeGraph(t)
	spec = packagefmt.Object(g.Nodes["support-skill"].Document["spec"])
	manifest := filepath.Join(c.RootPath(), filepath.FromSlash(packagefmt.Text(packagefmt.Object(spec["package"])["manifest"])))
	outside := filepath.Join(t.TempDir(), "SKILL.md")
	if err := os.WriteFile(outside, []byte("outside"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(manifest); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink(outside, manifest); err != nil {
		t.Skip("symlink creation unavailable")
	}
	if b, _, err := g.Compile("support", nil, nil); err == nil {
		b.Close()
		t.Fatal("linked support accepted")
	}
}

func TestLocalTransactionRecoversInterruptedWritesAndPreservesExternalEdits(t *testing.T) {
	c, err := Create(t.TempDir(), ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	a := filepath.Join(c.RootPath(), "agents/support/agent.yaml")
	b := filepath.Join(c.RootPath(), ".state/destination.json")
	if err := c.Commit(map[string][]byte{a: []byte("old"), b: []byte("state-old")}); err != nil {
		t.Fatal(err)
	}
	journal := localJournal{RegistryID: c.RegistryID, Changes: []localChange{{Path: a, Before: []byte("old"), Exists: true, After: []byte("new")}, {Path: b, Before: []byte("state-old"), Exists: true, After: []byte("state-new")}}}
	data, _ := json.Marshal(journal)
	if err := privateWrite(c.journalPath(), data); err != nil {
		t.Fatal(err)
	}
	if err := privateWrite(a, []byte("new")); err != nil {
		t.Fatal(err)
	}
	if err := c.Recover(); err != nil {
		t.Fatal(err)
	}
	actual, _ := os.ReadFile(b)
	if string(actual) != "state-new" {
		t.Fatal("interrupted state was not recovered")
	}
	if _, err := os.Stat(c.journalPath()); !os.IsNotExist(err) {
		t.Fatal("completed journal retained")
	}
	if err := privateWrite(c.journalPath(), data); err != nil {
		t.Fatal(err)
	}
	if err := privateWrite(a, []byte("external edit")); err != nil {
		t.Fatal(err)
	}
	if err := c.Recover(); err == nil {
		t.Fatal("external edit overwritten during recovery")
	}
	actual, _ = os.ReadFile(a)
	if string(actual) != "external edit" {
		t.Fatal("external edit lost")
	}
}

func TestDevelopmentLockSerializesProcesses(t *testing.T) {
	c, _ := Create(t.TempDir(), ".woobe", "")
	// Match the CLI initializer, including its protected Windows state directory.
	if err := packagecheckpoint.EnsurePrivateDirectory(filepath.Join(c.RootPath(), ".state")); err != nil {
		t.Fatal(err)
	}
	unlock, err := c.Lock()
	if err != nil {
		t.Fatal(err)
	}
	defer unlock()
	if second, err := c.Lock(); err == nil {
		second()
		t.Fatal("another command acquired the same registry lock")
	}
}

func TestManagedCaptureReusesRegistryAndConflictsWithoutWriting(t *testing.T) {
	source, _ := completeGraph(t)
	bundle, err := packagebundle.Load(source.RootPath(), false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	target, _ := Create(t.TempDir(), ".woobe", "")
	os.MkdirAll(target.RootPath(), 0700)
	state, _ := target.ReadState("http://local", "workspace", "project")
	captured := map[string]CapturedBinding{}
	for key, d := range bundle.Graph.Components {
		id, _ := NewID()
		uid := ""
		if d["kind"] == "Agent" || d["kind"] == "Network" {
			uid, _ = NewID()
		}
		captured[key] = CapturedBinding{ResourceUID: uid, ResourceID: id, Revision: json.Number("1"), SourceKind: "draft"}
	}
	credential, _ := NewID()
	publicSpec := clone(packagefmt.Object(packagefmt.Object(packagefmt.List(packagefmt.Object(packagefmt.Object(bundle.Graph.Manifest["spec"])["requires"])["credentials"])[0])["metadata"]))
	if publicSpec == nil {
		publicSpec = map[string]any{}
	}
	publicSpec["provider"] = "custom"
	provider, err := target.Add("Provider", "my-provider", "", map[string]any{"format": "woobe-package", "schema_version": "1.0", "kind": "Provider", "metadata": map[string]any{"name": "My provider"}, "spec": publicSpec}, nil, false)
	if err != nil {
		t.Fatal(err)
	}
	providerGraph, _ := LoadGraph(target)
	state.Credentials[provider.Key] = credential
	state.Bindings[provider.UID] = Binding{ResourceID: credential, Base: providerGraph.Nodes[provider.Key].Document}
	resource, conflicts, err := target.ImportCapture(bundle, state, captured, map[string]string{"primary": credential}, "support", "")
	if err != nil || len(conflicts) > 0 {
		t.Fatal(resource, conflicts, err)
	}
	if resource.UID != captured["support-network"].ResourceUID {
		t.Fatal("owner's canonical logical UID was replaced during capture")
	}
	fresh, _ := Create(t.TempDir(), ".woobe", "")
	freshState, _ := fresh.ReadState("http://local", "workspace", "project")
	freshRoot, freshConflicts, freshErr := fresh.ImportCapture(bundle, freshState, captured, map[string]string{"primary": credential}, "other-alias", "")
	if freshErr != nil || len(freshConflicts) != 0 || freshRoot.UID != resource.UID {
		t.Fatal("fresh registry changed the same native root's logical identity", freshErr, freshConflicts)
	}
	count := len(target.Resources)
	providers := 0
	for _, item := range target.Resources {
		if item.Kind == "Provider" {
			providers++
		}
	}
	if providers != 1 {
		t.Fatal("verified Provider duplicated", providers)
	}
	reused, err := target.Resolve("Provider", "@my-provider")
	if err != nil || reused.UID != provider.UID {
		t.Fatal("Provider identity lost", reused, err)
	}
	if _, conflicts, err = target.ImportCapture(bundle, state, captured, map[string]string{"primary": credential}, "", ""); err != nil || len(conflicts) > 0 || len(target.Resources) != count {
		t.Fatal("duplicated capture", conflicts, err, len(target.Resources), count)
	}
	originalIdentity := captured["support-network"]
	changedIdentity := originalIdentity
	changedIdentity.ResourceUID, _ = NewID()
	captured["support-network"] = changedIdentity
	if _, _, err = target.ImportCapture(bundle, state, captured, map[string]string{"primary": credential}, "", ""); err == nil || !strings.Contains(err.Error(), "canonical identity") {
		t.Fatal("capture rewrote an established logical identity", err)
	}
	captured["support-network"] = originalIdentity
	graph, err := LoadGraph(target)
	if err != nil {
		t.Fatal(err)
	}
	node := graph.Nodes[resource.Key]
	document := clone(node.Document)
	packagefmt.Object(document["metadata"])["description"] = "local"
	data, _ := Encode(document)
	file := graph.Path(node)
	os.WriteFile(file, data, 0600)
	packagefmt.Object(bundle.Graph.Components["support-network"]["metadata"])["description"] = "remote"
	original, _ := os.ReadFile(file)
	if _, conflicts, err = target.ImportCapture(bundle, state, captured, map[string]string{"primary": credential}, "", ""); err != nil || len(conflicts) != 1 {
		t.Fatal(conflicts, err)
	}
	after, _ := os.ReadFile(file)
	if !reflect.DeepEqual(original, after) {
		t.Fatal("conflicting pull changed author files")
	}
}

func TestCaptureSupportsRespectRegisteredFileDescriptor(t *testing.T) {
	for _, extension := range []string{".yaml", ".yml", ".json"} {
		t.Run(extension, func(t *testing.T) { testCaptureSupportsRespectRegisteredFileDescriptor(t, extension) })
	}
}

func testCaptureSupportsRespectRegisteredFileDescriptor(t *testing.T, extension string) {
	source, _ := completeGraph(t)
	bundle, err := packagebundle.Load(source.RootPath(), false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	target, err := Create(t.TempDir(), ".woobe", "")
	if err != nil {
		t.Fatal(err)
	}
	state, err := target.ReadState("http://local", "workspace", "project")
	if err != nil {
		t.Fatal(err)
	}
	captured := map[string]CapturedBinding{}
	for key := range bundle.Graph.Components {
		id, err := NewID()
		if err != nil {
			t.Fatal(err)
		}
		captured[key] = CapturedBinding{ResourceID: id, Revision: json.Number("1"), SourceKind: "draft"}
	}
	credential, err := NewID()
	if err != nil {
		t.Fatal(err)
	}
	if _, conflicts, err := target.ImportCapture(bundle, state, captured, map[string]string{"primary": credential}, "support", ""); err != nil || len(conflicts) != 0 {
		t.Fatal(conflicts, err)
	}
	var skill Resource
	for _, resource := range target.Resources {
		if resource.Kind == "Skill" {
			skill = resource
			break
		}
	}
	if skill.UID == "" {
		t.Fatal("fixture has no Skill")
	}
	if err := target.Move("Skill", "@"+skill.Alias, "descriptors/skill"+extension, false); err != nil {
		t.Fatal(err)
	}
	var remoteKey string
	for key, binding := range captured {
		if binding.ResourceID == state.Bindings[skill.UID].ResourceID {
			remoteKey = key
			break
		}
	}
	paths, err := packagebundle.SupportPaths(bundle.Graph.Components[remoteKey], bundle.Graph.Paths[remoteKey])
	if err != nil || len(paths) == 0 {
		t.Fatal(paths, err)
	}
	file := filepath.Join(source.RootPath(), filepath.FromSlash(paths[0]))
	before, err := os.ReadFile(file)
	if err != nil {
		t.Fatal(err)
	}
	updated := append(before, []byte("\nUpdated portable author instructions.\n")...)
	if err := os.WriteFile(file, updated, 0600); err != nil {
		t.Fatal(err)
	}
	fresh, err := packagebundle.Load(source.RootPath(), false)
	if err != nil {
		t.Fatal(err)
	}
	defer fresh.Close()
	count := len(target.Resources)
	if _, conflicts, err := target.ImportCapture(fresh, state, captured, map[string]string{"primary": credential}, "", ""); err != nil || len(conflicts) != 0 {
		t.Fatal(conflicts, err)
	}
	if len(target.Resources) != count {
		t.Fatal("capture duplicated registered resources")
	}
	if _, err := LoadGraph(target); err != nil {
		t.Fatalf("capture left an unreadable descriptor: %v", err)
	}
	after, err := os.ReadFile(filepath.Join(target.RootPath(), "descriptors", "files", "0", filepath.Base(paths[0])))
	if err != nil || !bytes.Equal(after, updated) {
		t.Fatal("support did not follow file descriptor's parent", err)
	}
}
func TestPrivateStateRefusesLinkedParents(t *testing.T) {
	c, _ := Create(t.TempDir(), ".woobe", "")
	os.MkdirAll(c.RootPath(), 0700)
	if err := os.Symlink(t.TempDir(), filepath.Join(c.RootPath(), ".state")); err != nil {
		t.Skip("platform does not allow symlink creation")
	}
	if _, err := c.ReadState("http://local", "workspace", "project"); err == nil {
		t.Fatal("linked private state accepted")
	}
}

func TestCaptureOfMinimalPackageKeepsEmptyRequirementArraysCompilable(t *testing.T) {
	source := t.TempDir()
	documents := map[string]string{
		"woobe.yaml": `{"format":"woobe-package","schema_version":"1.0","kind":"Package","metadata":{"name":"Support","version":"1.0.0"},"spec":{"entrypoint":{"kind":"Agent","ref":"support"},"resources":["agent.yaml","model.yaml"],"requires":{"credentials":[{"ref":"primary","provider":"custom"}],"knowledge":[],"secrets":[],"project_environment":[]}}}`,
		"agent.yaml": `{"format":"woobe-package","schema_version":"1.0","kind":"Agent","metadata":{"key":"support","name":"Support"},"spec":{"model":{"primary":{"ref":"chat"}},"legacy_system_prompt":"Help"}}`,
		"model.yaml": `{"format":"woobe-package","schema_version":"1.0","kind":"Model","metadata":{"key":"chat","name":"Chat"},"spec":{"provider":"custom","model":"fake","credential":{"ref":"primary"}}}`,
	}
	for name, data := range documents {
		if err := os.WriteFile(filepath.Join(source, name), []byte(data), 0600); err != nil {
			t.Fatal(err)
		}
	}
	bundle, err := packagebundle.Load(source, false)
	if err != nil {
		t.Fatal(err)
	}
	defer bundle.Close()
	c, _ := Create(t.TempDir(), ".woobe", "")
	state, err := c.ReadState("http://local", "workspace", "project")
	if err != nil {
		t.Fatal(err)
	}
	credentialID, _ := NewID()
	agentID, _ := NewID()
	modelID, _ := NewID()
	resource, conflicts, err := c.ImportCapture(bundle, state, map[string]CapturedBinding{"support": {ResourceID: agentID, Revision: 1, SourceKind: "draft"}, "chat": {ResourceID: modelID, Revision: "revision"}}, map[string]string{"primary": credentialID}, "support", "")
	if err != nil || len(conflicts) > 0 {
		t.Fatal(err, conflicts)
	}
	graph, err := LoadGraph(c)
	if err != nil {
		t.Fatal(err)
	}
	compiled, _, err := graph.Compile(resource.Key, state.Requirements, state.Credentials)
	if err != nil {
		t.Fatal("pulled minimal package became uncompilable", err)
	}
	compiled.Close()
}

func TestCompilerPreservesModelEndpointOverrideAndProviderDefaultSeparately(t *testing.T) {
	for _, override := range []string{"", "https://model.example/v1"} {
		t.Run(override, func(t *testing.T) {
			c, g := completeGraph(t)
			uid, _ := NewID()
			provider := Resource{UID: uid, Kind: "Provider", Key: "endpoint-provider", Alias: "endpoint-provider", Path: "providers/endpoint-provider"}
			c.Resources = append(c.Resources, provider)
			if err := os.MkdirAll(filepath.Join(c.RootPath(), provider.Path), 0700); err != nil {
				t.Fatal(err)
			}
			doc := map[string]any{"kind": "Provider", "metadata": map[string]any{"key": provider.Key, "name": provider.Alias}, "spec": map[string]any{"provider": "custom", "credential_ref": provider.Key, "base_url": "https://provider.example/v1"}}
			encoded, err := EncodeFile(doc, descriptor(provider))
			if err != nil {
				t.Fatal(err)
			}
			if err = os.WriteFile(filepath.Join(c.RootPath(), descriptor(provider)), encoded, 0600); err != nil {
				t.Fatal(err)
			}
			var modelKey string
			for key, node := range g.Nodes {
				if node.Resource.Kind != "Model" {
					continue
				}
				modelKey = key
				model := clone(node.Document)
				spec := packagefmt.Object(model["spec"])
				delete(spec, "credential")
				spec["provider_ref"] = provider.Key
				if override == "" {
					delete(spec, "base_url")
				} else {
					spec["base_url"] = override
				}
				encoded, err = EncodeFile(model, node.Descriptor)
				if err != nil {
					t.Fatal(err)
				}
				if err = os.WriteFile(filepath.Join(c.RootPath(), node.Descriptor), encoded, 0600); err != nil {
					t.Fatal(err)
				}
			}
			graph, err := LoadGraph(c)
			if err != nil {
				t.Fatal(err)
			}
			bundle, _, err := graph.Compile("support-network", nil, nil)
			if err != nil {
				t.Fatal(err)
			}
			defer bundle.Close()
			spec := packagefmt.Object(bundle.Graph.Components[modelKey]["spec"])
			if got := packagefmt.Text(spec["base_url"]); got != override {
				t.Fatalf("Model override changed: %q", got)
			}
			legacy, _, err := graph.compileRecipe("support-network", nil, nil, "")
			if err != nil {
				t.Fatal(err)
			}
			defer legacy.Close()
			if packagefmt.Text(packagefmt.Object(legacy.Graph.Components[modelKey]["spec"])["base_url"]) != "https://provider.example/v1" {
				t.Fatal("legacy retained compiler recipe was silently rewritten")
			}
			if _, _, err = graph.compileRecipe("support-network", nil, nil, "unknown@9"); err == nil {
				t.Fatal("unknown compiler recipe accepted")
			}
			// A retained pre-recipe source must still verify against its old
			// executable object, even though compiling it today gives a new one.
			root := graph.Nodes["support-network"].Resource
			source, err := graph.captureAuthors(root, legacy)
			if err != nil {
				t.Fatal(err)
			}
			source.CompilerRecipe = ""
			definition, components, err := PortableDefinition(legacy)
			if err != nil {
				t.Fatal(err)
			}
			record := &Revision{UID: root.UID, Kind: root.Kind, ArtifactDigest: "sha256:" + legacy.ArtifactDigest, DefinitionDigest: definition, DefinitionScope: PortableDefinitionScope, Components: map[string]string{}}
			for key, digest := range components {
				record.Components[graph.Nodes[key].Resource.UID] = digest
			}
			providers, err := PortableProviderDigests(legacy)
			if err != nil {
				t.Fatal(err)
			}
			record.Components[provider.UID] = providers[provider.Key]
			var archive bytes.Buffer
			if err = legacy.Archive(&archive, true); err != nil {
				t.Fatal(err)
			}
			if err = c.immutableWrite(filepath.Join(c.RootPath(), "objects", "sha256", legacy.ArtifactDigest+".tar.gz"), archive.Bytes()); err != nil {
				t.Fatal(err)
			}
			tracking := &Tracking{Requirements: packagefmt.Object(packagefmt.Object(legacy.Graph.Manifest["spec"])["requires"])}
			if err = graph.validateAuthorExecution(root, record, source, tracking); err != nil {
				t.Fatalf("historical source no longer verifies: %v", err)
			}
			source.CompilerRecipe = CurrentCompilerRecipe
			if err = graph.validateAuthorExecution(root, record, source, tracking); err == nil {
				t.Fatal("rewritten compiler recipe incorrectly matched the old executable")
			}

			credentials := packagefmt.List(packagefmt.Object(packagefmt.Object(bundle.Graph.Manifest["spec"])["requires"])["credentials"])
			if len(credentials) != 1 || packagefmt.Text(packagefmt.Object(packagefmt.Object(credentials[0])["metadata"])["base_url"]) != "https://provider.example/v1" {
				t.Fatal("Provider connection default was dropped")
			}
		})
	}
}
