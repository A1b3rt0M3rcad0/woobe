package cli

import (
	"encoding/json"
	"net/url"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

func (w *deployWorkflow) checkLocalOrigin(resource *devworkspace.Resource, export string) error {
	data, err := w.read(w.base+"/drafts/preflight", url.Values{"source_export_id": {export}, "resource_uid": {resource.UID}})
	if err != nil {
		return err
	}
	if data["schema_version"] != "1.0" || data["kind"] != w.intent.Kind || data["project_id"] != w.intent.Project || data["resource_id"] != w.intent.Resource || data["resource_uid"] != resource.UID || data["source_export_id"] != export || data["valid"] != true || data["executed"] != false {
		return output.New(9, "Server returned incomplete or mismatched local source preflight evidence")
	}
	return nil
}

// Validate accepted ancestry before allocating a new local revision or writing a
// remote Draft. Only an exact authenticated server record establishes acceptance.
// Missing records are reported parents-first, never synthesized or auto-uploaded.
func (w *deployWorkflow) checkLocalParents(c *devworkspace.Config, resource *devworkspace.Resource, parents []string) error {
	visited := map[string]int{}
	missing := []string{}
	var visit func(string) error
	visit = func(id string) error {
		if visited[id] == 2 {
			return nil
		}
		if visited[id] == 1 {
			return output.New(9, "Local revision ancestry contains a cycle")
		}
		if len(visited) >= 256 {
			return output.New(9, "Local ancestry exceeds the preflight bound; recover history explicitly")
		}
		visited[id] = 1
		local, err := c.ReadRevision(*resource, id)
		if err != nil {
			return output.New(9, "Local ancestor unavailable: "+id+"; restore exact history before delivery")
		}
		data, err := w.read(w.base+"/revisions/"+url.PathEscape(id), nil)
		if err == nil {
			raw, encodeErr := json.Marshal(data["record"])
			var remote devworkspace.Revision
			if encodeErr != nil || json.Unmarshal(raw, &remote) != nil || data["complete"] != true || devworkspace.ValidateRemoteRevision(*resource, remote) != nil || remote.ID != id || remote.RecordDigest != local.RecordDigest {
				return output.New(9, "Remote ancestor differs from local identity or digest: "+id)
			}
		} else {
			failure := output.Normalize(err)
			if failure.Status != 404 || failure.DomainCode != "ASAC_REVISION_UNAVAILABLE" {
				return err
			}
			for _, parent := range local.Parents {
				if err := visit(parent); err != nil {
					return err
				}
			}
			missing = append(missing, id)
		}
		visited[id] = 2
		return nil
	}
	for _, parent := range parents {
		if err := visit(parent); err != nil {
			return err
		}
	}
	if len(missing) != 0 {
		return &output.Error{Code: 6, DomainCode: "ASAC_HISTORY_INCOMPLETE", Outcome: "not_attempted", Message: "Local ancestors are not accepted by this target (parents first): " + strings.Join(missing, ", ") + ". Reconcile previous intents and checkpoint each exact ancestor in a matching isolated Draft before a new deploy. Local history verify is not proof of server acceptance; do not delete or rewrite parents."}
	}
	return nil
}

// Select the exact checkpoint retained by the intent or recover its local commit
// after an intent journal failure. Never adopt another operation's revision.
func localDeployRevision(c *devworkspace.Config, resource *devworkspace.Resource, working, retained, message, content string) (*devworkspace.Revision, []string, error) {
	if retained != "" {
		record, err := c.ReadRevision(*resource, retained)
		if err != nil || record.ArtifactDigest != content || record.Message != message {
			return nil, nil, output.New(9, "Retained deploy revision unavailable or changed; recover its exact local history")
		}
		return record, record.Parents, nil
	}
	if working != "" {
		record, err := c.ReadRevision(*resource, working)
		if err != nil {
			return nil, nil, output.New(9, "Local working revision unavailable; recover its exact history")
		}
		if record.Message == message && record.ArtifactDigest == content {
			return record, record.Parents, nil
		}
		return nil, []string{working}, nil
	}
	return nil, nil, nil
}
