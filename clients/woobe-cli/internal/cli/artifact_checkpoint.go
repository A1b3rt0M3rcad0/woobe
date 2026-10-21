package cli

import (
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"io"
	"net/url"
	"os"
	"regexp"
	"time"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagecheckpoint"
)

type artifactUploadCheckpoint struct {
	Format           string    `json:"format"`
	SchemaVersion    string    `json:"schema_version"`
	APIOrigin        string    `json:"api_origin"`
	ProjectID        string    `json:"project_id"`
	Environment      string    `json:"environment"`
	WorkspaceID      string    `json:"workspace_id"`
	UploadID         string    `json:"upload_id"`
	ArtifactID       string    `json:"artifact_id,omitempty"`
	ExpectedRevision string    `json:"expected_revision,omitempty"`
	OperationID      string    `json:"operation_id"`
	SourcePath       string    `json:"source_path"`
	ArtifactPath     string    `json:"artifact_path"`
	ContentType      string    `json:"content_type"`
	SizeBytes        int64     `json:"size_bytes"`
	SHA256           string    `json:"sha256"`
	Offset           int64     `json:"offset"`
	State            string    `json:"state"`
	UpdatedAt        time.Time `json:"updated_at"`
}

var artifactCheckpointDigest = regexp.MustCompile(`^[0-9a-f]{64}$`)
var artifactCheckpointID = regexp.MustCompile(`^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$`)

func (checkpoint artifactUploadCheckpoint) validate() error {
	origin, err := url.Parse(checkpoint.APIOrigin)
	if err != nil || origin.Host == "" || origin.User != nil || origin.RawQuery != "" || origin.Fragment != "" || (origin.Scheme != "https" && origin.Scheme != "http") {
		return output.New(2, "invalid Artifact upload checkpoint origin")
	}
	for _, value := range []string{checkpoint.ProjectID, checkpoint.WorkspaceID, checkpoint.OperationID} {
		if !artifactCheckpointID.MatchString(value) {
			return output.New(2, "invalid Artifact upload checkpoint identity")
		}
	}
	if (checkpoint.ArtifactID == "") != (checkpoint.ExpectedRevision == "") || checkpoint.ArtifactID != "" && (!artifactCheckpointID.MatchString(checkpoint.ArtifactID) || !artifactCheckpointID.MatchString(checkpoint.ExpectedRevision)) {
		return output.New(2, "invalid Artifact upload checkpoint identity")
	}
	if checkpoint.Format != "woobe-artifact-upload-checkpoint" || checkpoint.SchemaVersion != "1" || checkpoint.Environment != "draft" && checkpoint.Environment != "staging" && checkpoint.Environment != "production" || checkpoint.SizeBytes < 0 || checkpoint.Offset < 0 || checkpoint.Offset > checkpoint.SizeBytes || !artifactCheckpointDigest.MatchString(checkpoint.SHA256) || checkpoint.SourcePath == "" || checkpoint.ArtifactPath == "" || checkpoint.ContentType == "" || checkpoint.UpdatedAt.IsZero() {
		return output.New(2, "invalid Artifact upload checkpoint state")
	}
	switch checkpoint.State {
	case "begin_unknown":
		if checkpoint.UploadID != "" || checkpoint.Offset != 0 {
			return output.New(2, "invalid Artifact upload checkpoint state")
		}
	case "uploading", "outcome_unknown", "completed", "aborted":
		if !artifactCheckpointID.MatchString(checkpoint.UploadID) {
			return output.New(2, "invalid Artifact upload checkpoint identity")
		}
	default:
		return output.New(2, "invalid Artifact upload checkpoint state")
	}
	return nil
}

func loadArtifactUploadCheckpoint(path string) (*packagecheckpoint.Store, artifactUploadCheckpoint, error) {
	var checkpoint artifactUploadCheckpoint
	store, err := packagecheckpoint.Open(path)
	if err != nil {
		return nil, checkpoint, output.New(2, "private upload checkpoint unavailable")
	}
	data, err := store.ReadDocument()
	if err != nil {
		store.Close()
		return nil, checkpoint, output.New(2, "private upload checkpoint unavailable")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err = decoder.Decode(&checkpoint); err == nil && decoder.Decode(new(any)) != io.EOF {
		err = io.ErrUnexpectedEOF
	}
	if err != nil || checkpoint.validate() != nil {
		store.Close()
		return nil, checkpoint, output.New(2, "invalid private Artifact upload checkpoint")
	}
	return store, checkpoint, nil
}

func saveArtifactUploadCheckpoint(store *packagecheckpoint.Store, checkpoint *artifactUploadCheckpoint) error {
	checkpoint.UpdatedAt = time.Now().UTC()
	if err := checkpoint.validate(); err != nil {
		return err
	}
	data, err := json.Marshal(checkpoint)
	if err != nil {
		return output.New(2, "could not encode Artifact upload checkpoint")
	}
	if err = store.SaveDocument(data); err != nil {
		return output.New(2, "could not securely save Artifact upload checkpoint")
	}
	return nil
}

func artifactSourceDigest(file *os.File) (int64, string, error) {
	if file == nil {
		return 0, "", output.New(2, "cannot open upload source file")
	}
	info, err := file.Stat()
	if err != nil || !info.Mode().IsRegular() || info.Size() < 0 {
		return 0, "", output.New(2, "upload source must be a regular file")
	}
	if _, err = file.Seek(0, io.SeekStart); err != nil {
		return 0, "", output.New(2, "cannot seek upload source file")
	}
	hash := sha256.New()
	if _, err = io.Copy(hash, file); err != nil {
		return 0, "", output.New(2, "cannot hash upload source file")
	}
	if _, err = file.Seek(0, io.SeekStart); err != nil {
		return 0, "", output.New(2, "cannot seek upload source file")
	}
	return info.Size(), hex.EncodeToString(hash.Sum(nil)), nil
}
