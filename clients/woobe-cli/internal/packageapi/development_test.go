package packageapi

import (
	"context"
	"net/http"
	"strings"
	"testing"
	"time"
)

func TestSyncPlanPinsRegistryNativeResourceAndSourceEvidence(t *testing.T) {
	for _, alteration := range []string{"none", "registry", "uid", "native", "source", "release"} {
		t.Run(alteration, func(t *testing.T) {
			bindings := map[string]any{"schema_version": "1.0", "spec": map[string]any{}}
			digest, _ := BindingsDigest(bindings)
			target := DevelopmentTarget{ResourceUID: "uid", ResourceID: "native", ExpectedRevision: 7, SourceExportID: "export", SourceComponent: "agent", SnapshotID: "release"}
			request := PlanRequest{Mode: "sync", RegistryID: "registry", ResourceBindings: map[string]DevelopmentTarget{"agent": target}, UploadID: "upload", ArtifactDigest: strings.Repeat("a", 64), Bindings: bindings, Lifecycle: "draft"}
			var base string
			client, close := testClient(t, func(w http.ResponseWriter, r *http.Request) {
				observed := target
				registry := "registry"
				switch alteration {
				case "registry":
					registry = "other"
				case "uid":
					observed.ResourceUID = "other"
				case "native":
					observed.ResourceID = "other"
				case "source":
					observed.SourceExportID = "other"
				case "release":
					observed.SnapshotID = "other"
				}
				serveOperation(w, map[string]any{"package_schema_version": "1.0", "mode": "sync", "registry_id": registry, "resource_bindings": map[string]DevelopmentTarget{"agent": observed}, "api_origin": base, "project_id": "project", "plan_id": "plan", "upload_id": "upload", "artifact_digest": request.ArtifactDigest, "plan_digest": strings.Repeat("a", 64), "definition_digest": strings.Repeat("a", 64), "capabilities_digest": strings.Repeat("a", 64), "bindings_digest": digest, "bindings": bindings, "lifecycle": "draft", "expires_at": time.Now().Add(time.Hour).Format(time.RFC3339), "effects": []Effect{{Action: "prepare_existing_agent"}}})
			})
			defer close()
			base = client.Control.Base
			_, err := client.Plan(context.Background(), request)
			if (err == nil) != (alteration == "none") {
				t.Fatalf("unexpected qualification for %s: %v", alteration, err)
			}
		})
	}
}
