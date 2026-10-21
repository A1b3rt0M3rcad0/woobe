package packageapi

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"testing"

	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
)

const evidenceProjectUUID = "01a00d46-1ed7-71f7-99a4-aaa2cf81637c"
const evidenceOperationUUID = "01a0a033-7ef9-7776-bdd2-2ba5b782843e"

func TestPackageUUIDCaseMatchesCanonicalServerEvidence(t *testing.T) {
	for _, action := range []string{"status", "cancel", "resume", "registry"} {
		for _, scope := range []string{"same", "foreign", "opaque-case"} {
			t.Run(action+"/"+scope, func(t *testing.T) {
				project, requested, returned := evidenceProjectUUID, strings.ToUpper(evidenceOperationUUID), evidenceOperationUUID
				if scope == "foreign" {
					returned = "01a0a033-7ef9-7776-bdd2-2ba5b782843f"
				} else if scope == "opaque-case" {
					project, requested, returned = "project", "Operation", "operation"
				}
				client, close := testClient(t, func(w http.ResponseWriter, r *http.Request) {
					result := operationFixture()
					result["project_id"], result["operation_id"] = project, returned
					if action == "registry" {
						result = map[string]any{"package_schema_version": "1.0", "registry_id": returned, "resources": []any{}}
					}
					serveOperation(w, result)
				})
				defer close()
				projectInput := project
				if scope != "opaque-case" {
					projectInput = strings.ToUpper(project)
				}
				client, err := New(client.Control, projectInput)
				if err != nil {
					t.Fatal(err)
				}
				switch action {
				case "status":
					_, err = client.Status(context.Background(), requested)
				case "cancel":
					_, err = client.Cancel(context.Background(), requested)
				case "resume":
					_, err = client.Resume(context.Background(), requested, 2)
				case "registry":
					_, err = client.Registry(context.Background(), requested)
				}
				if scope == "same" && err != nil {
					t.Fatalf("rejected the same UUID returned in canonical form: %v", err)
				}
				if scope != "same" && (err == nil || output.Normalize(err).Code != 9) {
					t.Fatalf("accepted different identity: %v", err)
				}
			})
		}
	}
}

func TestProjectUUIDCaseDoesNotPermitForeignEvidence(t *testing.T) {
	client, close := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		result := operationFixture()
		result["project_id"] = "01a00d46-1ed7-71f7-99a4-aaa2cf81637d"
		serveOperation(w, result)
	})
	defer close()
	client, err := New(client.Control, strings.ToUpper(evidenceProjectUUID))
	if err != nil {
		t.Fatal(err)
	}
	if _, err = client.Status(context.Background(), "operation"); err == nil || output.Normalize(err).Code != 9 {
		t.Fatalf("accepted another project: %v", err)
	}
}

func TestLookupUUIDKeyRetainsExactCase(t *testing.T) {
	key := strings.ToUpper(evidenceOperationUUID)
	client, close := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		var body map[string]any
		if json.NewDecoder(r.Body).Decode(&body) != nil || body["idempotency_key"] != key {
			t.Error("UUID-shaped idempotency key was changed")
		}
		serveOperation(w, operationFixture())
	})
	defer close()
	if _, err := client.Lookup(context.Background(), key); err != nil {
		t.Fatal(err)
	}
}
