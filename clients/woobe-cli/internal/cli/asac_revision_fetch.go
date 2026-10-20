package cli

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/url"
	"reflect"
	"strings"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/devworkspace"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
)

func (a *App) asacFetchRevisions(cmd *cobra.Command, kind string, c *devworkspace.Config, state *devworkspace.State, resource *devworkspace.Resource) error {
	client, err := a.packageClient(cmd.Context(), "registry")
	if err != nil {
		return err
	}
	capabilities, err := client.Capabilities(cmd.Context())
	if err != nil {
		return err
	}
	if !capabilities.ASaC.RevisionCatalog {
		return output.New(9, "Server does not advertise isolated revision catalog support")
	}
	id := state.Bindings[resource.UID].ResourceID
	if id == "" {
		tracking, err := c.ReadTracking(*resource)
		if err != nil {
			return output.New(2, "Revision fetch needs a native binding or tracking origin")
		}
		if tracking.Origin.Target != strings.TrimRight(client.Control.Base, "/") || tracking.Origin.Workspace != a.Workspace || tracking.Origin.Project != a.Project {
			return output.New(9, "Tracking origin belongs to another selected destination")
		}
		id = tracking.Origin.ResourceID
	}
	if err := resourceID(id); err != nil {
		return err
	}
	path := fmt.Sprintf("/projects/%s/%ss/%s/asac/revisions", url.PathEscape(a.Project), kind, url.PathEscape(id))
	cursor := ""
	seen := map[string]bool{}
	identities := map[string]bool{}
	var watermark any
	total := 0
	for page := 0; page < 100; page++ {
		query := url.Values{"limit": {"100"}}
		if cursor != "" {
			query.Set("cursor", cursor)
		}
		response, _, err := client.Control.Request(cmd.Context(), "GET", path, query, nil)
		if err != nil {
			return err
		}
		data, err := developmentResponseData(response)
		if err != nil {
			return err
		}
		if data["schema_version"] != "1.0" || data["resource_id"] != id || data["kind"] != resource.Kind || data["stream"] != "revisions" || data["coverage"] != "authorized_resource_metadata" {
			return output.New(9, "Revision catalog scope mismatch")
		}
		if page == 0 {
			watermark = data["watermark"]
		} else if !reflect.DeepEqual(watermark, data["watermark"]) {
			return output.New(9, "Revision watermark changed during traversal")
		}
		records, ok := data["records"].([]any)
		if !ok || len(records) > 100 {
			return output.New(9, "Invalid revision page")
		}
		for _, raw := range records {
			entry, ok := raw.(map[string]any)
			if !ok {
				return output.New(9, "Invalid revision metadata")
			}
			encoded, err := json.Marshal(entry["record"])
			if err != nil {
				return output.New(9, "Invalid revision record")
			}
			decoder := json.NewDecoder(bytes.NewReader(encoded))
			decoder.DisallowUnknownFields()
			var record devworkspace.Revision
			if decoder.Decode(&record) != nil || identities[record.ID] {
				return output.New(9, "Invalid or repeated revision identity")
			}
			identities[record.ID] = true
			// Dry-run verifies the same immutable record without storing it.
			if a.DryRun {
				if err := devworkspace.ValidateRemoteRevision(*resource, record); err != nil {
					return output.New(9, err.Error())
				}
			} else if err := c.StoreRemoteRevision(*resource, record); err != nil {
				return output.New(9, err.Error())
			}
			total++
		}
		more, ok := data["has_more"].(bool)
		if !ok || data["complete"] != !more {
			return output.New(9, "Revision completeness mismatch")
		}
		if !more {
			return a.emit(map[string]any{"resource_uid": resource.UID, "resource_id": id, "fetched": total, "stream": "revisions", "watermark": watermark, "metadata_complete": true, "coverage": "authorized_resource_metadata", "objects_available": "not_downloaded", "author_files_changed": false, "production_changed": false, "executed": !a.DryRun})
		}
		cursor, ok = data["next_cursor"].(string)
		if !ok || cursor == "" || seen[cursor] {
			return output.New(9, "Revision cursor missing or repeated")
		}
		seen[cursor] = true
	}
	return output.New(9, "Revision catalog exceeds traversal bound; retained metadata is incomplete")
}
