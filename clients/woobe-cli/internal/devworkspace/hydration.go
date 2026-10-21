package devworkspace

import (
	"bytes"
	"fmt"
	"path/filepath"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/packagebundle"
)

func ValidateExecutableObject(resource Resource, record Revision, bundle *packagebundle.Bundle) error {
	if err := ValidateRemoteRevision(resource, record); err != nil {
		return err
	}
	if "sha256:"+bundle.ArtifactDigest != record.ArtifactDigest {
		return fmt.Errorf("ASAC_ARTIFACT_MISMATCH: executable object differs from selected revision")
	}
	definition, _, err := PortableDefinition(bundle)
	if err != nil || definition != record.DefinitionDigest || DefinitionScope(bundle.Graph.Manifest) != record.DefinitionScope {
		return fmt.Errorf("ASAC_ARTIFACT_MISMATCH: executable definition differs from selected revision")
	}
	return nil
}

// OpenExecutableObject verifies the retained archive without reading today's YAML.
func (c *Config) OpenExecutableObject(resource Resource, record Revision) (*packagebundle.Bundle, error) {
	file := filepath.Join(c.RootPath(), "objects", "sha256", strings.TrimPrefix(record.ArtifactDigest, "sha256:")+".tar.gz")
	if err := confinedParents(c.RootPath(), file); err != nil {
		return nil, err
	}
	data, err := c.ReadOperationalFile(file, packagebundle.MaxArchiveBytes)
	if err != nil {
		return nil, err
	}
	bundle, err := packagebundle.ReceiveArchive(bytes.NewReader(data), true)
	if err != nil {
		return nil, err
	}
	if err := ValidateExecutableObject(resource, record, bundle); err != nil {
		bundle.Close()
		return nil, err
	}
	return bundle, nil
}

// StoreExecutableObject does not restore author files, bindings or working heads.
func (c *Config) StoreExecutableObject(resource Resource, record Revision, bundle *packagebundle.Bundle) error {
	if err := ValidateExecutableObject(resource, record, bundle); err != nil {
		return err
	}
	var archive bytes.Buffer
	if err := bundle.Archive(&boundedArchiveWriter{buffer: &archive, remaining: packagebundle.MaxArchiveBytes}, true); err != nil {
		return err
	}
	path := filepath.Join(c.RootPath(), "objects", "sha256", strings.TrimPrefix(record.ArtifactDigest, "sha256:")+".tar.gz")
	return c.immutableWrite(path, archive.Bytes())
}
