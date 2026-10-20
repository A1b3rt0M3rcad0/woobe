package devworkspace

import (
	"bytes"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"reflect"
	"sort"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/asac"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/requestinput"
	"gopkg.in/yaml.v3"
)

const maxAuthorObjectBytes = 128 << 20

type AuthorComponent struct {
	Resource Resource          `json:"resource"`
	Document map[string]any    `json:"document"`
	Raw      string            `json:"raw"`
	Supports map[string]string `json:"supports"`
}
type AuthorObject struct {
	CompilerRecipe string                     `json:"compiler_recipe,omitempty"`
	Format         string                     `json:"format"`
	Version        string                     `json:"schema_version"`
	UID            string                     `json:"resource_uid"`
	Components     map[string]AuthorComponent `json:"components"`
}

func authorDigest(value *AuthorObject) (string, error) {
	raw, err := json.Marshal(value)
	if err != nil {
		return "", err
	}
	if len(raw) > maxAuthorObjectBytes {
		return "", fmt.Errorf("author object exceeds the bounded source limit")
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	var generic any
	if err = decoder.Decode(&generic); err != nil {
		return "", err
	}
	return asac.Digest("author-object", generic)
}

func (g *Graph) captureAuthors(resource Resource, bundle *packagebundle.Bundle) (*AuthorObject, error) {
	nodes, err := g.Closure(resource.Key)
	if err != nil {
		return nil, err
	}
	root, err := os.OpenRoot(g.Config.RootPath())
	if err != nil {
		return nil, err
	}
	defer root.Close()
	captured, err := os.OpenRoot(bundle.Root)
	if err != nil {
		return nil, err
	}
	defer captured.Close()
	recipe := previousCompilerRecipe
	if bundle.Graph.Manifest["schema_version"] == "2.0" {
		recipe = CurrentCompilerRecipe
	}
	result := &AuthorObject{CompilerRecipe: recipe, Format: "woobe-author-object", Version: "1.0", UID: resource.UID, Components: map[string]AuthorComponent{}}
	total := 0
	for _, node := range nodes {
		raw, err := packagebundle.ReadConfined(root, node.Descriptor, requestinput.MaxBytes)
		if err != nil {
			return nil, err
		}
		total += len(raw)
		if total > 90<<20 {
			return nil, fmt.Errorf("author source capture exceeds source object limit")
		}
		decoded, err := decodeNode(node.Resource, raw)
		if err != nil {
			return nil, err
		}
		if !reflect.DeepEqual(decoded.Document, node.Document) {
			return nil, fmt.Errorf("author descriptor changed during capture; retry the read")
		}
		if node.Resource.Kind == "Provider" && uuidPattern.MatchString(packagefmt.Text(packagefmt.Object(node.Document["spec"])["credential_ref"])) {
			return nil, fmt.Errorf("Provider credential UUID belongs in private bindings, not revision source; bind the Provider before checkpointing")
		}
		item := AuthorComponent{Resource: node.Resource, Document: clone(node.Document), Raw: string(raw), Supports: map[string]string{}}
		supports, err := authorSupportPaths(node.Document, node.Descriptor)
		if err != nil {
			return nil, err
		}
		for i, source := range supports {
			name, err := filepath.Rel(filepath.Dir(filepath.FromSlash(node.Descriptor)), filepath.FromSlash(source))
			if err != nil {
				return nil, err
			}
			sealed := fmt.Sprintf("support/%s/%d/%s", node.Resource.UID, i, path.Base(source))
			data, err := packagebundle.ReadConfined(captured, sealed, packagebundle.MaxFileBytes)
			if err != nil {
				return nil, err
			}
			total += len(data)
			if total > 90<<20 {
				return nil, fmt.Errorf("author support capture exceeds source object limit")
			}
			item.Supports[filepath.ToSlash(name)] = base64.StdEncoding.EncodeToString(data)
		}
		result.Components[node.Resource.UID] = item
	}
	return result, nil
}

func (c *Config) ReadAuthorObject(resource Resource, record *Revision) (*AuthorObject, error) {
	if record.AuthorDigest == "" {
		return nil, fmt.Errorf("revision predates retained author source; export or restore its source explicitly")
	}
	file := filepath.Join(c.RootPath(), "objects", "author", strings.TrimPrefix(record.AuthorDigest, "sha256:")+".json")
	raw, err := c.ReadOperationalFile(file, maxAuthorObjectBytes)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, fmt.Errorf("retained author object unavailable for revision %s; hydrate this revision before guarded checkout: %w", record.ID, os.ErrNotExist)
		}
		return nil, fmt.Errorf("retained author object unavailable: %w", err)
	}
	return ValidateAuthorObject(resource, record, raw)
}

// ValidateAuthorObject verifies identity, exact YAML and support closure without writes.
func ValidateAuthorObject(resource Resource, record *Revision, raw []byte) (*AuthorObject, error) {
	if err := jsoninput.Validate(raw); err != nil {
		return nil, fmt.Errorf("ambiguous retained author object: %w", err)
	}
	if len(raw) > maxAuthorObjectBytes {
		return nil, fmt.Errorf("author object exceeds source limit")
	}
	decoder := json.NewDecoder(bytes.NewReader(raw))
	decoder.UseNumber()
	decoder.DisallowUnknownFields()
	var object AuthorObject
	if decoder.Decode(&object) != nil {
		return nil, fmt.Errorf("invalid retained author object")
	}
	var trailing any
	if decoder.Decode(&trailing) != io.EOF {
		return nil, fmt.Errorf("trailing author source content")
	}
	digest, err := authorDigest(&object)
	if err != nil || digest != record.AuthorDigest || object.Format != "woobe-author-object" || !supportedCompilerRecipe(object.CompilerRecipe) || object.Version != "1.0" || object.UID != resource.UID || len(object.Components) == 0 || len(object.Components) > 1024 {
		return nil, fmt.Errorf("author object integrity or identity mismatch")
	}
	entry, ok := object.Components[resource.UID]
	if !ok || entry.Resource.Kind != resource.Kind || entry.Resource.Key != resource.Key {
		return nil, fmt.Errorf("retained author root identity mismatch")
	}
	for uid, item := range object.Components {
		if uid != item.Resource.UID || !uuidPattern.MatchString(uid) {
			return nil, fmt.Errorf("invalid source component identity")
		}
		declared, err := authorSupportPaths(item.Document, descriptor(item.Resource))
		if err != nil || len(declared) != len(item.Supports) {
			return nil, fmt.Errorf("retained support inventory disagrees with its descriptor")
		}
		for _, source := range declared {
			name, err := filepath.Rel(filepath.Dir(filepath.FromSlash(descriptor(item.Resource))), filepath.FromSlash(source))
			if err != nil {
				return nil, err
			}
			if _, ok := item.Supports[filepath.ToSlash(name)]; !ok {
				return nil, fmt.Errorf("retained support inventory is incomplete")
			}
		}
		decoded, err := decodeNode(item.Resource, []byte(item.Raw))
		if err != nil || !reflect.DeepEqual(decoded.Document, item.Document) {
			return nil, fmt.Errorf("author source bytes disagree with their descriptor")
		}
	}
	return &object, nil
}

// sourceWrites preserves logical identities and current aliases/paths. It never
// rewrites destination bindings, origins or sealed revision records.
func (c *Config) sourceWrites(object *AuthorObject) (map[string][]byte, error) {
	writes := map[string][]byte{}
	staged := *c
	staged.Resources = append([]Resource{}, c.Resources...)
	for uid, item := range object.Components {
		resource := item.Resource
		found := false
		for _, current := range staged.Resources {
			if current.UID == uid {
				if current.Kind != resource.Kind || current.Key != resource.Key {
					return nil, fmt.Errorf("source identity collides with current registry")
				}
				resource = current
				found = true
				break
			}
		}
		if !found {
			staged.Resources = append(staged.Resources, resource)
		}
		// Validate the complete resulting registry before writing any source path.
		if err := staged.Validate(); err != nil {
			return nil, err
		}
		target := filepath.Join(c.RootPath(), descriptor(resource))
		if _, exists := writes[target]; exists {
			return nil, fmt.Errorf("source descriptor paths collide")
		}
		writes[target] = []byte(item.Raw)
		for name, encoded := range item.Supports {
			if err := validateAuthorPath(name); err != nil {
				return nil, fmt.Errorf("invalid retained support path")
			}
			data, err := base64.StdEncoding.DecodeString(encoded)
			if err != nil || len(data) > int(packagebundle.MaxFileBytes) {
				return nil, fmt.Errorf("invalid retained support bytes")
			}
			file := filepath.Join(filepath.Dir(target), filepath.FromSlash(name))
			if err = c.validateWrite(file); err != nil {
				return nil, err
			}
			if _, duplicate := writes[file]; duplicate {
				return nil, fmt.Errorf("source support paths collide")
			}
			writes[file] = data
		}
	}
	raw, err := yaml.Marshal(&staged)
	if err != nil {
		return nil, err
	}
	writes[c.File] = raw
	return writes, nil
}

// CheckoutRevision restores exact retained author bytes only when the working
// tree still matches its source checkpoint. --yes cannot bypass this protection.
func (g *Graph) prepareAuthorRestore(resource Resource, selected *AuthorObject) (map[string][]byte, *Tracking, error) {
	tracking, err := g.Config.ReadTracking(resource)
	if err != nil {
		return nil, nil, err
	}
	if tracking.Working == "" {
		return nil, nil, fmt.Errorf("checkpoint current author files before checkout")
	}
	current, err := g.Config.ReadRevision(resource, tracking.Working)
	if err != nil {
		return nil, nil, err
	}
	baseline, err := g.Config.ReadAuthorObject(resource, current)
	if err != nil {
		return nil, nil, err
	}
	root, err := os.OpenRoot(g.Config.RootPath())
	if err != nil {
		return nil, nil, err
	}
	defer root.Close()
	for uid, item := range baseline.Components {
		var node *Node
		for _, candidate := range g.Nodes {
			if candidate.Resource.UID == uid {
				node = candidate
				break
			}
		}
		if node == nil {
			return nil, nil, fmt.Errorf("working dependency is missing; restore it before checkout")
		}
		raw, err := packagebundle.ReadConfined(root, node.Descriptor, requestinput.MaxBytes)
		if err != nil || string(raw) != item.Raw {
			return nil, nil, fmt.Errorf("local author edits would be replaced; checkpoint or stash explicitly before checkout")
		}
		for name, encoded := range item.Supports {
			relative := path.Join(path.Dir(node.Descriptor), name)
			data, err := packagebundle.ReadConfined(root, relative, packagebundle.MaxFileBytes)
			if err != nil || base64.StdEncoding.EncodeToString(data) != encoded {
				return nil, nil, fmt.Errorf("local support edits would be replaced; checkpoint or stash explicitly before checkout")
			}
		}
	}
	writes, err := g.Config.sourceWrites(selected)
	if err != nil {
		return nil, nil, err
	}
	// Check that unrelated files are not displaced when restoring a component
	// absent from the current closure, even if a target path now belongs to it.
	baselineUIDs := map[string]bool{}
	for uid := range baseline.Components {
		baselineUIDs[uid] = true
	}
	for uid, item := range selected.Components {
		if baselineUIDs[uid] {
			// A restored revision may introduce a support path absent from the
			// current checkpoint. Its existing bytes are unregistered local work.
			for _, existing := range g.Config.Resources {
				if existing.UID == uid {
					for name, encoded := range item.Supports {
						if _, tracked := baseline.Components[uid].Supports[name]; !tracked {
							target := filepath.Join(g.Config.RootPath(), filepath.Dir(descriptor(existing)), filepath.FromSlash(name))
							data, err := g.Config.ReadOperationalFile(target, packagebundle.MaxFileBytes)
							if err == nil && base64.StdEncoding.EncodeToString(data) == encoded {
								delete(writes, target)
							} else if !os.IsNotExist(err) {
								return nil, nil, fmt.Errorf("restore would replace an unregistered support file")
							}
						}
					}
				}
			}
			continue
		}
		managed := false
		for _, existing := range g.Config.Resources {
			if existing.UID == uid {
				managed = true
				file := filepath.Join(g.Config.RootPath(), descriptor(existing))
				raw, err := g.Config.ReadOperationalFile(file, requestinput.MaxBytes)
				if err != nil || string(raw) != item.Raw {
					return nil, nil, fmt.Errorf("checkout would replace an independently edited shared dependency")
				}
				for name, encoded := range item.Supports {
					data, err := g.Config.ReadOperationalFile(filepath.Join(filepath.Dir(file), filepath.FromSlash(name)), packagebundle.MaxFileBytes)
					if err != nil || base64.StdEncoding.EncodeToString(data) != encoded {
						return nil, nil, fmt.Errorf("checkout would replace an independently edited shared support file")
					}
				}
			}
		}
		if !managed {
			targets := []string{filepath.Join(g.Config.RootPath(), descriptor(item.Resource))}
			for name := range item.Supports {
				targets = append(targets, filepath.Join(filepath.Dir(targets[0]), filepath.FromSlash(name)))
			}
			for _, file := range targets {
				if _, err := os.Lstat(file); !os.IsNotExist(err) {
					return nil, nil, fmt.Errorf("checkout would replace an unregistered file")
				}
			}
		}
	}

	return writes, tracking, nil
}

func (g *Graph) CheckoutRevision(resource Resource, record *Revision) (map[string]any, error) {
	selected, err := g.Config.ReadAuthorObject(resource, record)
	if err != nil {
		return nil, err
	}
	writes, tracking, err := g.prepareAuthorRestore(resource, selected)
	if err != nil {
		return nil, err
	}
	if err = g.validateAuthorExecution(resource, record, selected, tracking); err != nil {
		return nil, err
	}
	tracking.Working = record.ID
	raw, err := json.Marshal(tracking)
	if err != nil {
		return nil, err
	}
	lock, err := g.Config.TrackingPath(resource)
	if err != nil {
		return nil, err
	}
	var document map[string]any
	if err = json.Unmarshal(raw, &document); err != nil {
		return nil, err
	}
	raw, err = Encode(document)
	if err != nil {
		return nil, err
	}
	writes[lock] = raw
	if err = g.Config.Commit(writes); err != nil {
		return nil, err
	}
	// Config resource ordering is stable for future compilations.
	loaded, err := Load(g.Config.File)
	if err != nil {
		return nil, err
	}
	*g.Config = *loaded
	return map[string]any{"resource_uid": resource.UID, "working_revision": record.ID, "origin_preserved": true, "scope": "local", "remote_changed": false}, nil
}

func sortedAuthorUIDs(object *AuthorObject) []string {
	keys := []string{}
	for key := range object.Components {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

// Compile the source in an isolated scratch registry before touching user files.
// Source digests are not server attestations; executable equality is mandatory.
func (g *Graph) validateAuthorExecution(resource Resource, record *Revision, object *AuthorObject, tracking *Tracking) error {
	archive, err := g.Config.ReadOperationalFile(filepath.Join(g.Config.RootPath(), "objects", "sha256", strings.TrimPrefix(record.ArtifactDigest, "sha256:")+".tar.gz"), packagebundle.MaxArchiveBytes)
	if err != nil {
		return fmt.Errorf("sealed executable object unavailable: %w", err)
	}
	sealed, err := packagebundle.ReceiveArchive(bytes.NewReader(archive), true)
	if err != nil {
		return err
	}
	actual := "sha256:" + sealed.ArtifactDigest
	sealed.Close()
	if actual != record.ArtifactDigest {
		return fmt.Errorf("sealed executable object digest mismatch")
	}
	dir, err := os.MkdirTemp("", "woobe-source-verify-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(dir)
	config := *g.Config
	config.File = filepath.Join(dir, Filename)
	config.Root = ".woobe"
	config.Resources = nil
	for _, uid := range sortedAuthorUIDs(object) {
		config.Resources = append(config.Resources, object.Components[uid].Resource)
	}
	if err = config.Validate(); err != nil {
		return err
	}
	writes, err := config.sourceWrites(object)
	if err != nil {
		return err
	}
	for file, data := range writes {
		if err = os.MkdirAll(filepath.Dir(file), 0700); err != nil {
			return err
		}
		if err = os.WriteFile(file, data, 0600); err != nil {
			return err
		}
	}
	graph, err := LoadGraph(&config)
	if err != nil {
		return err
	}
	bundle, _, err := graph.compileRecipe(resource.Key, tracking.Requirements, nil, object.CompilerRecipe)
	if err != nil {
		return err
	}
	defer bundle.Close()
	definition, digests, err := PortableDefinition(bundle)
	if err != nil {
		return err
	}
	if definition != record.DefinitionDigest || DefinitionScope(bundle.Graph.Manifest) != record.DefinitionScope {
		return fmt.Errorf("retained author source disagrees with sealed executable definition")
	}
	expected := map[string]string{}
	for key, digest := range digests {
		expected[graph.Nodes[key].Resource.UID] = digest
	}
	providers, err := PortableProviderDigests(bundle)
	if err != nil {
		return err
	}
	for key, digest := range providers {
		if node := graph.Nodes[key]; node != nil && node.Resource.Kind == "Provider" {
			expected[node.Resource.UID] = digest
		}
	}
	if !reflect.DeepEqual(expected, record.Components) {
		return fmt.Errorf("retained author components disagree with sealed identities")
	}
	return nil
}

// ValidateRetainedAuthor verifies source with its recorded compiler recipe against
// the retained executable closure in private scratch storage, without moving a head.
func (c *Config) ValidateRetainedAuthor(resource Resource, record *Revision, raw []byte, requirements map[string]any, bundle *packagebundle.Bundle) error {
	object, err := ValidateAuthorObject(resource, record, raw)
	if err != nil {
		return err
	}
	if len(object.Components) != len(record.Components) {
		return fmt.Errorf("author closure differs from sealed component identities")
	}
	for uid := range object.Components {
		if _, ok := record.Components[uid]; !ok {
			return fmt.Errorf("author closure contains unsealed identity")
		}
	}
	dir, err := os.MkdirTemp("", "woobe-author-hydrate-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(dir)
	scratch := *c
	scratch.File = filepath.Join(dir, Filename)
	scratch.Root = ".woobe"
	scratch.Resources = nil
	if err = os.MkdirAll(scratch.RootPath(), 0700); err != nil {
		return err
	}
	if err = scratch.StoreExecutableObject(resource, *record, bundle); err != nil {
		return err
	}
	return (&Graph{Config: &scratch}).validateAuthorExecution(resource, record, object, &Tracking{Requirements: requirements})
}

func (c *Config) StoreAuthorObject(resource Resource, record *Revision, raw []byte) error {
	if _, err := ValidateAuthorObject(resource, record, raw); err != nil {
		return err
	}
	return c.immutableWrite(filepath.Join(c.RootPath(), "objects", "author", strings.TrimPrefix(record.AuthorDigest, "sha256:")+".json"), raw)
}
