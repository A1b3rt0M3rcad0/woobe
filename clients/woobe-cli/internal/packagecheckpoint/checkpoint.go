// Package packagecheckpoint owns durable client state, separate from Manifest.
package packagecheckpoint

import (
	"bytes"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"time"
	"unicode/utf8"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/jsoninput"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

type State string

const (
	Prepared        State = "prepared"
	RequestInFlight State = "request_in_flight"
	Accepted        State = "accepted"
	Observing       State = "observing"
	Terminal        State = "terminal"
	OutcomeUnknown  State = "outcome_unknown"
)

type Checkpoint struct {
	Format               string    `json:"format"`
	SchemaVersion        string    `json:"schema_version"`
	APIOrigin            string    `json:"api_origin"`
	ProjectID            string    `json:"project_id"`
	ArtifactDigest       string    `json:"artifact_digest"`
	UploadID             string    `json:"upload_id"`
	PlanID               string    `json:"plan_id"`
	PlanDigest           string    `json:"plan_digest"`
	IdempotencyKey       string    `json:"idempotency_key"`
	OperationID          string    `json:"operation_id,omitempty"`
	PrincipalFingerprint string    `json:"principal_fingerprint"`
	RequestIdentity      string    `json:"request_identity"`
	Lifecycle            string    `json:"lifecycle"`
	State                State     `json:"state"`
	LastRemoteState      string    `json:"last_remote_state,omitempty"`
	LastRevision         int64     `json:"last_revision"`
	CreatedAt            time.Time `json:"created_at"`
	UpdatedAt            time.Time `json:"updated_at"`
}

var digest = regexp.MustCompile(`^[a-f0-9]{64}$`)
var identifier = regexp.MustCompile(`^[A-Za-z0-9_.:-]{1,128}$`)
var remoteStates = map[string]bool{"accepted": true, "resolving": true, "materializing": true, "verifying": true, "waiting_dependency": true, "succeeded": true, "failed": true, "cancelling": true, "cancelled": true}

func (c Checkpoint) Validate() error {
	fail := func() error { return output.New(2, "invalid package checkpoint identity or state") }
	if c.Format != "woobe-package-checkpoint" || c.SchemaVersion != "1.0" {
		return fail()
	}
	origin, err := url.Parse(c.APIOrigin)
	if err != nil || origin.Host == "" || origin.User != nil || origin.RawQuery != "" || origin.Fragment != "" || origin.Path != "" && origin.Path != "/" || (origin.Scheme != "https" && origin.Scheme != "http") {
		return fail()
	}
	for _, value := range []string{c.ArtifactDigest, c.PlanDigest, c.PrincipalFingerprint, c.RequestIdentity} {
		if !digest.MatchString(value) {
			return fail()
		}
	}
	for _, value := range []string{c.ProjectID, c.UploadID, c.PlanID, c.IdempotencyKey} {
		if !identifier.MatchString(value) {
			return fail()
		}
	}
	if c.OperationID != "" && !identifier.MatchString(c.OperationID) {
		return fail()
	}
	if c.CreatedAt.IsZero() || c.UpdatedAt.Before(c.CreatedAt) || c.LastRevision < 0 {
		return fail()
	}
	if c.Lifecycle != "draft" && c.Lifecycle != "staging" && c.Lifecycle != "release" && c.Lifecycle != "production" {
		return fail()
	}
	switch c.State {
	case Prepared, RequestInFlight, OutcomeUnknown:
	case Accepted, Observing, Terminal:
		if c.OperationID == "" {
			return fail()
		}
	default:
		return fail()
	}
	if c.LastRemoteState != "" && !remoteStates[c.LastRemoteState] {
		return fail()
	}
	if c.State == Terminal && c.LastRemoteState != "succeeded" && c.LastRemoteState != "failed" && c.LastRemoteState != "cancelled" {
		return fail()
	}
	return nil
}

func Parse(data []byte) (Checkpoint, error) {
	var checkpoint Checkpoint
	if len(data) > 1<<20 || !utf8.Valid(data) || jsoninput.Validate(data) != nil {
		return checkpoint, output.New(2, "invalid package checkpoint JSON")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&checkpoint); err != nil {
		return checkpoint, output.New(2, "invalid package checkpoint fields")
	}
	return checkpoint, checkpoint.Validate()
}

func (c *Checkpoint) Move(next State) error {
	allowed := map[State][]State{
		Prepared: {RequestInFlight}, RequestInFlight: {Accepted, OutcomeUnknown},
		OutcomeUnknown: {Accepted, Observing, Terminal}, Accepted: {Observing, Terminal},
		Observing: {Observing, Terminal, OutcomeUnknown}, Terminal: {Terminal},
	}
	valid := c.State == next
	for _, target := range allowed[c.State] {
		valid = valid || target == next
	}
	if !valid {
		return output.New(2, "package checkpoint transition requires reconciliation")
	}
	candidate := *c
	candidate.State, candidate.UpdatedAt = next, time.Now().UTC()
	if err := candidate.Validate(); err != nil {
		return err
	}
	*c = candidate
	return nil
}

type Store struct {
	Path string
	lock *os.File
	root *os.Root
	name string
}

func Open(path string) (*Store, error) {
	if err := supportedProtection(); err != nil {
		return nil, err
	}
	absolute, err := filepath.Abs(path)
	if err != nil {
		return nil, err
	}
	if err = os.MkdirAll(filepath.Dir(absolute), 0700); err != nil {
		return nil, err
	}
	root, err := os.OpenRoot(filepath.Dir(absolute))
	if err != nil {
		return nil, err
	}
	if err = checkPrivateParent(root); err != nil {
		root.Close()
		return nil, err
	}
	name := filepath.Base(absolute)
	lock, err := lockCheckpoint(root, name+".lock")
	if err != nil {
		root.Close()
		return nil, err
	}
	return &Store{Path: absolute, lock: lock, root: root, name: name}, nil
}

func (s *Store) Close() error {
	err := s.lock.Close()
	rootErr := s.root.Close()
	if err != nil {
		return err
	}
	return rootErr
}

func (s *Store) Read() (Checkpoint, error) {
	data, err := s.ReadDocument()
	if err != nil {
		return Checkpoint{}, err
	}
	return Parse(data)
}

// ReadDocument shares the OS protection and bounded no-follow read used by
// package checkpoints. Callers own the schema and immutable identity checks.
func (s *Store) ReadDocument() ([]byte, error) {
	var empty []byte
	info, err := s.root.Lstat(s.name)
	if err != nil {
		return empty, err
	}
	if !privateMode(info) || info.Size() > 1<<20 {
		return empty, output.New(3, "package checkpoint must be a bounded private regular file")
	}
	file, err := openConfinedRead(s.root, s.name)
	if err != nil {
		return empty, err
	}
	defer file.Close()
	opened, err := file.Stat()
	if err != nil || !os.SameFile(info, opened) || !privateMode(opened) {
		return empty, output.New(3, "package checkpoint changed while opening")
	}
	if err = checkPrivateFile(file); err != nil {
		return empty, err
	}
	data, err := io.ReadAll(io.LimitReader(file, 1<<20+1))
	if err != nil {
		return empty, err
	}
	if len(data) > 1<<20 || jsoninput.Validate(data) != nil {
		return nil, output.New(2, "invalid private checkpoint JSON")
	}
	return data, nil
}

func sameIdentity(left, right Checkpoint) bool {
	return left.CreatedAt.Equal(right.CreatedAt) && left.APIOrigin == right.APIOrigin && left.ProjectID == right.ProjectID && left.ArtifactDigest == right.ArtifactDigest && left.UploadID == right.UploadID && left.PlanID == right.PlanID && left.PlanDigest == right.PlanDigest && left.IdempotencyKey == right.IdempotencyKey && left.PrincipalFingerprint == right.PrincipalFingerprint && left.RequestIdentity == right.RequestIdentity && left.Lifecycle == right.Lifecycle
}

func (s *Store) Save(checkpoint Checkpoint) error {
	if err := checkpoint.Validate(); err != nil {
		return err
	}
	previous, err := s.Read()
	existing := err == nil
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	if existing && (!sameIdentity(previous, checkpoint) || previous.OperationID != "" && previous.OperationID != checkpoint.OperationID || checkpoint.LastRevision < previous.LastRevision) {
		return output.New(2, "package checkpoint identity or revision changed")
	}
	if existing {
		candidate := checkpoint
		candidate.State = previous.State
		if err = candidate.Move(checkpoint.State); err != nil {
			return err
		}
	}
	data, err := json.Marshal(checkpoint)
	if err != nil {
		return err
	}
	return s.SaveDocument(data)
}

// SaveDocument is atomic and durable, retaining the same private file,
// hardlink/symlink, parent-directory and Windows DACL checks as Save.
func (s *Store) SaveDocument(data []byte) error {
	if len(data) > 1<<20 || jsoninput.Validate(data) != nil {
		return output.New(2, "invalid private checkpoint JSON")
	}
	_, err := s.ReadDocument()
	existing := err == nil
	if err != nil && !os.IsNotExist(err) {
		return err
	}
	nonce := make([]byte, 16)
	if _, err = rand.Read(nonce); err != nil {
		return err
	}
	temporaryName := ".woobe-package-checkpoint-" + hex.EncodeToString(nonce)
	file, err := s.root.OpenFile(temporaryName, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	defer s.root.Remove(temporaryName)
	if err = file.Chmod(0600); err == nil {
		_, err = file.Write(data)
	}
	if err == nil {
		err = file.Sync()
	}
	closeErr := file.Close()
	if err != nil {
		return err
	}
	if closeErr != nil {
		return closeErr
	}
	if existing {
		err = s.root.Rename(temporaryName, s.name)
	} else {
		err = s.root.Link(temporaryName, s.name)
	}
	if err != nil {
		return err
	}
	parent, err := s.root.Open(".")
	if err != nil {
		return err
	}
	defer parent.Close()
	return syncParent(parent)
}
