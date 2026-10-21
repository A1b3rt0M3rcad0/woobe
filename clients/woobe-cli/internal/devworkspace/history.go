package devworkspace

import (
	"bytes"
	"crypto/sha256"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/asac"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagefmt"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/requestinput"
)

type Revision struct {
	Format           string            `json:"format"`
	SchemaVersion    string            `json:"schema_version"`
	ID               string            `json:"revision_id"`
	UID              string            `json:"resource_uid"`
	Kind             string            `json:"kind"`
	Parents          []string          `json:"parents"`
	Message          string            `json:"message"`
	AuthorDigest     string            `json:"author_artifact_digest,omitempty"`
	ArtifactDigest   string            `json:"artifact_digest"`
	DefinitionDigest string            `json:"definition_digest"`
	DefinitionScope  string            `json:"definition_digest_scope,omitempty"`
	Components       map[string]string `json:"component_digests"`
	RecordDigest     string            `json:"record_digest,omitempty"`
}
type TrackingSource struct {
	Target       string `json:"target"`
	Workspace    string `json:"workspace_id"`
	Project      string `json:"project_id"`
	ResourceID   string `json:"resource_id"`
	Environment  string `json:"environment"`
	SnapshotID   string `json:"snapshot_id,omitempty"`
	OriginStatus string `json:"origin_status"`
}
type Tracking struct {
	Format             string         `json:"format"`
	SchemaVersion      string         `json:"schema_version"`
	UID                string         `json:"resource_uid"`
	Origin             TrackingSource `json:"origin"`
	Working            string         `json:"working_revision,omitempty"`
	TrackedEnvironment string         `json:"tracking_environment"`
	WriteEnvironment   string         `json:"write_environment"`
	Requirements       map[string]any `json:"requires,omitempty"`
}

var revisionID = regexp.MustCompile(`^rv_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$`)
var historyDigest = regexp.MustCompile(`^sha256:[a-f0-9]{64}$`)

func (c *Config) historyDirectory(resource Resource) (string, error) {
	file, err := c.ResourcePath(resource)
	if err != nil {
		return "", err
	}
	if strings.EqualFold(filepath.Ext(file), ".yaml") || strings.EqualFold(filepath.Ext(file), ".yml") || strings.EqualFold(filepath.Ext(file), ".json") {
		file = strings.TrimSuffix(file, filepath.Ext(file)) + ".asac"
	}
	return file, nil
}
func (c *Config) TrackingPath(resource Resource) (string, error) {
	dir, err := c.historyDirectory(resource)
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, strings.ToLower(resource.Kind)+".lock.yaml"), nil
}

func readHistoryJSON(c *Config, file string, value any) error {
	data, err := c.ReadOperationalFile(file, requestinput.MaxBytes)
	if err != nil {
		return err
	}
	data, err = requestinput.Decode(data, file, "auto")
	if err != nil {
		return err
	}
	d := json.NewDecoder(bytes.NewReader(data))
	d.DisallowUnknownFields()
	d.UseNumber()
	return d.Decode(value)
}
func (c *Config) ReadTracking(resource Resource) (*Tracking, error) {
	file, err := c.TrackingPath(resource)
	if err != nil {
		return nil, err
	}
	var tracking Tracking
	if err = readHistoryJSON(c, file, &tracking); err != nil {
		return nil, err
	}
	if tracking.Format != "woobe-tracking" || tracking.SchemaVersion != asac.Version || tracking.UID != resource.UID || tracking.WriteEnvironment != "draft" {
		return nil, fmt.Errorf("ASAC_TRACKING_INVALID: tracking identity or write environment mismatch")
	}
	if tracking.Working != "" && !revisionID.MatchString(tracking.Working) {
		return nil, fmt.Errorf("ASAC_TRACKING_INVALID: invalid working revision")
	}
	return &tracking, nil
}
func (c *Config) WriteTracking(resource Resource, tracking Tracking) error {
	if tracking.UID != resource.UID || tracking.Format != "woobe-tracking" || tracking.SchemaVersion != asac.Version || tracking.WriteEnvironment != "draft" {
		return fmt.Errorf("ASAC_TRACKING_INVALID")
	}
	file, err := c.TrackingPath(resource)
	if err != nil {
		return err
	}
	data, err := json.Marshal(tracking)
	if err != nil {
		return err
	}
	var document map[string]any
	if err = json.Unmarshal(data, &document); err != nil {
		return err
	}
	data, err = Encode(document)
	if err != nil {
		return err
	}
	if err = c.validateAuthorWrite(file); err != nil {
		return err
	}
	return writeConfined(c.RootPath(), file, data)
}

// BootstrapTracking persists only durable origin identities, never credentials,
// export tickets, CAS observations, leases or private operational checkpoints.
func (c *Config) BootstrapTracking(resource Resource, state *State, environment string) error {
	if _, err := c.ReadTracking(resource); err == nil {
		return nil
	} else if !os.IsNotExist(err) {
		return err
	}
	b := state.Bindings[resource.UID]
	status := "unknown_origin"
	if b.SnapshotID != "" {
		status = "captured_snapshot"
	}
	return c.WriteTracking(resource, Tracking{Format: "woobe-tracking", SchemaVersion: asac.Version, UID: resource.UID,
		Origin: TrackingSource{Target: state.API, Workspace: state.Workspace, Project: state.Project, ResourceID: b.ResourceID, Environment: environment, SnapshotID: b.SnapshotID, OriginStatus: status}, TrackedEnvironment: environment, WriteEnvironment: "draft", Requirements: state.Requirements})
}

func (g *Graph) DefinitionDigests(key string) (map[string]string, error) {
	return g.definitionDigests(key, nil)
}

func (g *Graph) definitionDigests(key string, captured map[string]Binding) (map[string]string, error) {
	nodes, err := g.Closure(key)
	if err != nil {
		return nil, err
	}
	result := map[string]string{}
	root, err := os.OpenRoot(g.Config.RootPath())
	if err != nil {
		return nil, err
	}
	defer root.Close()
	for _, node := range nodes {
		doc := clone(node.Document)
		delete(packagefmt.Object(doc["metadata"]), "key")
		delete(doc, "provenance")
		RewriteReferences(doc, result)
		spec := packagefmt.Object(doc["spec"])
		if ref := packagefmt.Text(spec["provider_ref"]); ref != "" {
			spec["provider_ref"] = result[ref]
		}
		if node.Resource.Kind == "Model" {
			delete(spec, "credential")
		}
		if node.Resource.Kind == "Provider" {
			delete(spec, "credential_ref")
		}
		if node.Resource.Kind == "Skill" {
			for _, raw := range packagefmt.List(spec["tool_refs"]) {
				item := packagefmt.Object(raw)
				item["ref"] = result[packagefmt.Text(item["ref"])]
			}
		}
		supports := map[string]string{}
		paths, err := authorSupportPaths(node.Document, node.Descriptor)
		if err != nil {
			return nil, err
		}
		for _, path := range paths {
			data, err := packagebundle.ReadConfined(root, path, packagebundle.MaxFileBytes)
			if err != nil {
				return nil, err
			}
			name, err := filepath.Rel(filepath.Dir(filepath.FromSlash(node.Descriptor)), filepath.FromSlash(path))
			if err != nil {
				return nil, err
			}
			digest := fmt.Sprintf("sha256:%x", sha256.Sum256(data))
			if captured != nil {
				digest = "sha256:" + captured[node.Resource.UID].Supports[filepath.ToSlash(name)]
			}
			supports[filepath.ToSlash(name)] = digest
		}
		value := map[string]any{"document": doc, "support": supports}
		digest, err := asac.Digest("definition", value)
		if err != nil {
			return nil, err
		}
		result[node.Resource.Key] = digest
	}
	return result, nil
}

func revisionRecordDigest(record Revision) (string, error) {
	record.RecordDigest = ""
	return asac.Digest("record", record)
}
func (c *Config) ReadRevision(resource Resource, id string) (*Revision, error) {
	if !revisionID.MatchString(id) {
		return nil, fmt.Errorf("ASAC_REVISION_INVALID: invalid revision ID")
	}
	dir, err := c.historyDirectory(resource)
	if err != nil {
		return nil, err
	}
	var record Revision
	if err = readHistoryJSON(c, filepath.Join(dir, "revisions", id+".yaml"), &record); err != nil {
		return nil, err
	}
	return validateRevision(resource, id, record)
}

func validateRevision(resource Resource, id string, record Revision) (*Revision, error) {
	if record.Format != "woobe-revision" || record.SchemaVersion != asac.Version || record.ID != id || record.UID != resource.UID || record.Kind != resource.Kind || !historyDigest.MatchString(record.ArtifactDigest) || !historyDigest.MatchString(record.DefinitionDigest) || record.AuthorDigest != "" && !historyDigest.MatchString(record.AuthorDigest) {
		return nil, fmt.Errorf("ASAC_REVISION_INVALID: record identity mismatch")
	}
	if len(record.Parents) > 64 || len(record.Components) > 1024 || len(record.Message) > 4096 || strings.TrimSpace(record.Message) == "" {
		return nil, fmt.Errorf("ASAC_REVISION_INVALID: record exceeds canonical bounds")
	}
	for uid, digest := range record.Components {
		if !uuidPattern.MatchString(uid) || !historyDigest.MatchString(digest) {
			return nil, fmt.Errorf("ASAC_REVISION_INVALID: invalid component identity or digest")
		}
	}
	digest, err := revisionRecordDigest(record)
	if err != nil || record.RecordDigest != digest {
		return nil, fmt.Errorf("ASAC_REVISION_INVALID: record digest mismatch")
	}
	seen := map[string]bool{}
	for _, parent := range record.Parents {
		if !revisionID.MatchString(parent) || parent == id || seen[parent] {
			return nil, fmt.Errorf("ASAC_REVISION_INVALID: invalid parents")
		}
		seen[parent] = true
	}
	return &record, nil
}

func ValidateRemoteRevision(resource Resource, record Revision) error {
	if !revisionID.MatchString(record.ID) || !SupportedDefinitionScope(record.DefinitionScope) {
		return fmt.Errorf("ASAC_REVISION_INVALID: remote revision scope mismatch")
	}
	_, err := validateRevision(resource, record.ID, record)
	return err
}

// StoreRemoteRevision appends metadata without moving the working head or
// claiming that executable/author objects were downloaded.
func (c *Config) StoreRemoteRevision(resource Resource, record Revision) error {
	if err := ValidateRemoteRevision(resource, record); err != nil {
		return err
	}
	dir, err := c.historyDirectory(resource)
	if err != nil {
		return err
	}
	data, err := json.Marshal(record)
	if err != nil {
		return err
	}
	var document map[string]any
	if err := json.Unmarshal(data, &document); err != nil {
		return err
	}
	encoded, err := Encode(document)
	if err != nil {
		return err
	}
	return c.immutableWrite(filepath.Join(dir, "revisions", record.ID+".yaml"), encoded)
}

// immutableWrite publishes complete bytes with an exclusive link. Existing IDs
// never change; temporary hard links disappear before subsequent confined reads.
func (c *Config) immutableWrite(file string, data []byte) error {
	if err := confinedParents(c.RootPath(), file); err != nil {
		return err
	}
	root, err := os.OpenRoot(c.RootPath())
	if err != nil {
		return err
	}
	defer root.Close()
	name, err := filepath.Rel(c.RootPath(), file)
	if err != nil {
		return err
	}
	if err = root.MkdirAll(filepath.Dir(name), 0700); err != nil {
		return err
	}
	id, err := NewID()
	if err != nil {
		return err
	}
	tmp := filepath.Join(filepath.Dir(name), ".asac-"+id)
	f, err := root.OpenFile(tmp, os.O_CREATE|os.O_EXCL|os.O_WRONLY, 0600)
	if err != nil {
		return err
	}
	defer root.Remove(tmp)
	_, err = f.Write(data)
	if err == nil {
		err = f.Sync()
	}
	closed := f.Close()
	if err != nil {
		return err
	}
	if closed != nil {
		return closed
	}
	if err = root.Link(tmp, name); err != nil {
		if !os.IsExist(err) {
			return err
		}
		existing, readErr := c.ReadOperationalFile(file, int64(len(data))+1)
		if readErr != nil || !bytes.Equal(existing, data) {
			return fmt.Errorf("ASAC_INTEGRITY_CONFLICT: immutable ID already has different bytes")
		}
	}
	return nil
}

func (g *Graph) CreateRevision(resource Resource, state *State, message string, parents []string) (*Revision, error) {
	if strings.TrimSpace(message) == "" || len(message) > 4096 {
		return nil, fmt.Errorf("revision message must be 1–4096 bytes")
	}
	c := g.Config
	if err := c.BootstrapTracking(resource, state, "unknown"); err != nil {
		return nil, err
	}
	tracking, err := c.ReadTracking(resource)
	if err != nil {
		return nil, err
	}
	if len(state.Requirements) == 0 {
		state.Requirements = tracking.Requirements
	}
	if parents == nil {
		parents = []string{}
		if tracking.Working != "" {
			parents = append(parents, tracking.Working)
		}
	}
	if len(parents) > 64 {
		return nil, fmt.Errorf("revision supports at most 64 parents")
	}
	seen := map[string]bool{}
	for _, parent := range parents {
		if seen[parent] {
			return nil, fmt.Errorf("duplicate parent")
		}
		seen[parent] = true
		if _, err = c.ReadRevision(resource, parent); err != nil {
			return nil, err
		}
	}
	bundle, _, err := g.Compile(resource.Key, state.Requirements, state.Credentials)
	if err != nil {
		return nil, err
	}
	defer bundle.Close()
	definition, digests, err := PortableDefinition(bundle)
	if err != nil {
		return nil, err
	}
	var archive bytes.Buffer
	if err = bundle.Archive(&boundedArchiveWriter{buffer: &archive, remaining: packagebundle.MaxArchiveBytes}, true); err != nil {
		return nil, err
	}
	if archive.Len() > int(packagebundle.MaxArchiveBytes) {
		return nil, fmt.Errorf("ASaC object exceeds archive limit")
	}
	object := filepath.Join(c.RootPath(), "objects", "sha256", bundle.ArtifactDigest+".tar.gz")
	if err = c.immutableWrite(object, archive.Bytes()); err != nil {
		return nil, err
	}
	authors, err := g.captureAuthors(resource, bundle)
	if err != nil {
		return nil, err
	}
	authorHash, err := authorDigest(authors)
	if err != nil {
		return nil, err
	}
	source, err := json.Marshal(authors)
	if err != nil {
		return nil, err
	}
	if err = c.immutableWrite(filepath.Join(c.RootPath(), "objects", "author", strings.TrimPrefix(authorHash, "sha256:")+".json"), source); err != nil {
		return nil, err
	}
	id, err := NewID()
	if err != nil {
		return nil, err
	}
	components := map[string]string{}
	for key, digest := range digests {
		components[g.Nodes[key].Resource.UID] = digest
	}
	providers, err := PortableProviderDigests(bundle)
	if err != nil {
		return nil, err
	}
	closure, err := g.Closure(resource.Key)
	if err != nil {
		return nil, err
	}
	for _, node := range closure {
		if node.Resource.Kind == "Provider" {
			if digest, ok := providers[node.Resource.Key]; ok {
				components[node.Resource.UID] = digest
			}
		}
	}
	record := Revision{Format: "woobe-revision", SchemaVersion: asac.Version, ID: "rv_" + id, UID: resource.UID, Kind: resource.Kind, Parents: parents, Message: message, AuthorDigest: authorHash, ArtifactDigest: "sha256:" + bundle.ArtifactDigest, DefinitionDigest: definition, DefinitionScope: DefinitionScope(bundle.Graph.Manifest), Components: components}
	record.RecordDigest, err = revisionRecordDigest(record)
	if err != nil {
		return nil, err
	}
	raw, err := json.Marshal(record)
	if err != nil {
		return nil, err
	}
	var doc map[string]any
	if err = json.Unmarshal(raw, &doc); err != nil {
		return nil, err
	}
	raw, err = Encode(doc)
	if err != nil {
		return nil, err
	}
	dir, err := c.historyDirectory(resource)
	if err != nil {
		return nil, err
	}
	if err = c.immutableWrite(filepath.Join(dir, "revisions", record.ID+".yaml"), raw); err != nil {
		return nil, err
	}
	tracking.Working = record.ID
	if err = c.WriteTracking(resource, *tracking); err != nil {
		return nil, err
	}
	return &record, nil
}

func (c *Config) Revisions(resource Resource) ([]Revision, error) {
	dir, err := c.historyDirectory(resource)
	if err != nil {
		return nil, err
	}
	if err = confinedParents(c.RootPath(), filepath.Join(dir, "revisions", "record.yaml")); err != nil {
		return nil, err
	}
	files, err := os.ReadDir(filepath.Join(dir, "revisions"))
	if os.IsNotExist(err) {
		return []Revision{}, nil
	}
	if err != nil {
		return nil, err
	}
	if len(files) > 10000 {
		return nil, fmt.Errorf("ASaC history exceeds local record limit")
	}
	records := []Revision{}
	for _, file := range files {
		if strings.HasPrefix(file.Name(), ".asac-") {
			continue
		}
		if !strings.HasSuffix(file.Name(), ".yaml") {
			return nil, fmt.Errorf("unexpected revision file")
		}
		record, err := c.ReadRevision(resource, strings.TrimSuffix(file.Name(), ".yaml"))
		if err != nil {
			return nil, err
		}
		records = append(records, *record)
	}
	sort.Slice(records, func(i, j int) bool { return records[i].ID < records[j].ID })
	return records, nil
}

func (c *Config) VerifyHistory(resource Resource) (map[string]any, error) {
	records, err := c.Revisions(resource)
	if err != nil {
		return nil, err
	}
	byID := map[string]Revision{}
	parents := map[string]bool{}
	for _, record := range records {
		byID[record.ID] = record
		for _, parent := range record.Parents {
			parents[parent] = true
		}
	}
	missing := []string{}
	verifiedObjects := map[string]bool{}
	missingObjects := []string{}
	missingAuthors := []string{}
	legacyAuthors := []string{}
	verifiedAuthors := map[string]bool{}
	visiting, done := map[string]bool{}, map[string]bool{}
	var visit func(string) error
	visit = func(id string) error {
		if visiting[id] {
			return fmt.Errorf("ASAC_HISTORY_CYCLE")
		}
		if done[id] {
			return nil
		}
		record, ok := byID[id]
		if !ok {
			missing = append(missing, id)
			done[id] = true
			return nil
		}
		visiting[id] = true
		for _, parent := range record.Parents {
			if err := visit(parent); err != nil {
				return err
			}
		}
		delete(visiting, id)
		done[id] = true
		return nil
	}
	heads := []string{}
	for _, record := range records {
		if err = visit(record.ID); err != nil {
			return nil, err
		}
		if !parents[record.ID] {
			heads = append(heads, record.ID)
		}
		if record.AuthorDigest == "" {
			legacyAuthors = append(legacyAuthors, record.ID)
		} else if !verifiedAuthors[record.AuthorDigest] {
			_, err := c.ReadAuthorObject(resource, &record)
			if errors.Is(err, os.ErrNotExist) {
				missingAuthors = append(missingAuthors, record.AuthorDigest)
			} else if err != nil {
				return nil, err
			}
			verifiedAuthors[record.AuthorDigest] = true
		}
		if verifiedObjects[record.ArtifactDigest] {
			continue
		}
		file := filepath.Join(c.RootPath(), "objects", "sha256", strings.TrimPrefix(record.ArtifactDigest, "sha256:")+".tar.gz")
		if err = confinedParents(c.RootPath(), file); err != nil {
			return nil, err
		}
		data, err := c.ReadOperationalFile(file, packagebundle.MaxArchiveBytes)
		if os.IsNotExist(err) {
			missingObjects = append(missingObjects, record.ArtifactDigest)
			verifiedObjects[record.ArtifactDigest] = true
			continue
		}
		if err != nil {
			return nil, err
		}
		bundle, err := packagebundle.ReceiveArchive(bytes.NewReader(data), true)
		if err != nil {
			return nil, err
		}
		actual := "sha256:" + bundle.ArtifactDigest
		bundle.Close()
		if actual != record.ArtifactDigest {
			return nil, fmt.Errorf("ASAC_OBJECT_DIGEST_MISMATCH")
		}
		verifiedObjects[record.ArtifactDigest] = true
	}
	receipts, err := c.VerifyHistoryReceipts(resource)
	if err != nil {
		return nil, err
	}
	publications, err := c.VerifyPublicationReceipts(resource)
	if err != nil {
		return nil, err
	}
	cancellations, err := c.VerifyPublicationCancellations(resource)
	if err != nil {
		return nil, err
	}
	deployments, err := c.VerifyDeploymentReceipts(resource, false)
	if err != nil {
		return nil, err
	}
	plans, err := c.VerifyDeploymentReceipts(resource, true)
	if err != nil {
		return nil, err
	}
	return map[string]any{"deployment_receipts": deployments, "deployment_plans": plans, "deployment_authenticity": "integrity_checked_connection_unverified", "publication_cancellations": cancellations, "publication_receipts": publications, "publication_authenticity": "integrity_checked_connection_unverified", "receipts": receipts, "records": len(records), "heads": heads, "missing_history": missing, "missing_objects": missingObjects, "missing_author_objects": missingAuthors, "revisions_without_author_source": legacyAuthors, "author_sources_available": len(missingAuthors) == 0 && len(legacyAuthors) == 0, "metadata_complete": len(missing) == 0, "objects_available": len(missingObjects) == 0, "runtime_executable": "not_evaluated", "scope": "local", "remote_status": "unverified"}, nil
}

// StoreHistoryReceipt verifies the server record and stores it under a destination
// namespace. A hash proves integrity; it is not a server signature or Git attestation.
func (c *Config) StoreHistoryReceipt(resource Resource, target, workspace, project string, record map[string]any) error {
	value := clone(record)
	expected := packagefmt.Text(value["record_digest"])
	delete(value, "record_digest")
	digest, err := asac.Digest("history-receipt", value)
	if err != nil || digest != expected {
		return fmt.Errorf("ASAC_RECEIPT_INVALID: digest mismatch")
	}
	id := packagefmt.Text(record["id"])
	if !uuidPattern.MatchString(id) || record["schema_version"] != "1.0" || record["kind"] != resource.Kind || record["project_id"] != project {
		return fmt.Errorf("ASAC_RECEIPT_INVALID: identity mismatch")
	}
	stream := packagefmt.Text(record["stream"])
	if stream != "releases" && stream != "deployments" {
		return fmt.Errorf("ASAC_RECEIPT_INVALID: invalid stream")
	}
	namespace, err := asac.Digest("destination", []string{target, workspace, project})
	if err != nil {
		return err
	}
	dir, err := c.historyDirectory(resource)
	if err != nil {
		return err
	}
	wrapper := map[string]any{"format": "woobe-observed-history", "schema_version": "1.0", "resource_uid": resource.UID, "target": target, "workspace_id": workspace, "project_id": project, "receipt": record, "authenticity": "authenticated_connection_observation"}
	data, err := Encode(wrapper)
	if err != nil {
		return err
	}
	return c.immutableWrite(filepath.Join(dir, stream, strings.TrimPrefix(namespace, "sha256:")+"_"+id+".yaml"), data)
}

// Bound compressed output before allocation rather than after buffering it.
type boundedArchiveWriter struct {
	buffer    *bytes.Buffer
	remaining int64
}

func (w *boundedArchiveWriter) Write(data []byte) (int, error) {
	if int64(len(data)) > w.remaining {
		return 0, fmt.Errorf("ASaC object exceeds archive limit")
	}
	n, err := w.buffer.Write(data)
	w.remaining -= int64(n)
	if err == nil && n != len(data) {
		err = io.ErrShortWrite
	}
	return n, err
}

// Verify retained observations as well as local authored revisions. These checks
// detect corruption; only an authenticated fetch establishes the server source.
func (c *Config) VerifyHistoryReceipts(resource Resource) (int, error) {
	dir, err := c.historyDirectory(resource)
	if err != nil {
		return 0, err
	}
	count := 0
	for _, stream := range []string{"releases", "deployments"} {
		base := filepath.Join(dir, stream)
		if err := confinedParents(c.RootPath(), filepath.Join(base, "receipt.yaml")); err != nil {
			return 0, err
		}
		files, err := os.ReadDir(base)
		if os.IsNotExist(err) {
			continue
		}
		if err != nil {
			return 0, err
		}
		if len(files) > 10000 {
			return 0, fmt.Errorf("ASaC receipts exceed local record limit")
		}
		for _, file := range files {
			if strings.HasPrefix(file.Name(), ".asac-") {
				continue
			}
			var wrapper struct {
				Format       string         `json:"format"`
				Version      string         `json:"schema_version"`
				UID          string         `json:"resource_uid"`
				Target       string         `json:"target"`
				Workspace    string         `json:"workspace_id"`
				Project      string         `json:"project_id"`
				Record       map[string]any `json:"receipt"`
				Authenticity string         `json:"authenticity"`
			}
			if err := readHistoryJSON(c, filepath.Join(base, file.Name()), &wrapper); err != nil {
				return 0, err
			}
			record := wrapper.Record
			if wrapper.Format != "woobe-observed-history" || wrapper.Version != asac.Version || wrapper.UID != resource.UID || wrapper.Authenticity != "authenticated_connection_observation" || record["project_id"] != wrapper.Project || record["kind"] != resource.Kind || record["stream"] != stream || !uuidPattern.MatchString(packagefmt.Text(record["resource_id"])) {
				return 0, fmt.Errorf("ASAC_RECEIPT_INVALID: scope mismatch")
			}
			value := clone(record)
			expected := packagefmt.Text(value["record_digest"])
			delete(value, "record_digest")
			digest, err := asac.Digest("history-receipt", value)
			if err != nil || digest != expected {
				return 0, fmt.Errorf("ASAC_RECEIPT_INVALID: digest mismatch")
			}
			namespace, err := asac.Digest("destination", []string{wrapper.Target, wrapper.Workspace, wrapper.Project})
			if err != nil {
				return 0, err
			}
			id := packagefmt.Text(record["id"])
			if !uuidPattern.MatchString(id) || file.Name() != strings.TrimPrefix(namespace, "sha256:")+"_"+id+".yaml" {
				return 0, fmt.Errorf("ASAC_RECEIPT_INVALID: filename identity mismatch")
			}
			count++
		}
	}
	return count, nil
}
