package main

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"fmt"
	"io"
	"log"
	"os"

	woobe "github.com/A1b3rt0M3rcad0/woobe-sdk-go"
)

func operationID() string {
	var value [16]byte
	if _, err := rand.Read(value[:]); err != nil {
		log.Fatal(err)
	}
	return fmt.Sprintf("%x", value[:])
}

func fileDigest(path string) (int64, string, error) {
	file, err := os.Open(path)
	if err != nil {
		return 0, "", err
	}
	defer file.Close()
	hasher := sha256.New()
	size, err := io.Copy(hasher, file)
	if err != nil {
		return 0, "", err
	}
	return size, fmt.Sprintf("%x", hasher.Sum(nil)), nil
}

func main() {
	ctx := context.Background()
	projectID := os.Getenv("WOOBE_PROJECT_ID")
	key := os.Getenv("WOOBE_RUNTIME_KEY")
	path := "./handout.pdf"
	if projectID == "" || key == "" {
		log.Fatal("set WOOBE_PROJECT_ID and WOOBE_RUNTIME_KEY")
	}

	client, err := woobe.New()
	if err != nil {
		log.Fatal(err)
	}
	defer client.CloseIdleConnections()
	artifacts, err := client.Artifacts(projectID, key, woobe.ArtifactStaging)
	if err != nil {
		log.Fatal(err)
	}

	workspace, err := artifacts.CreateWorkspace(ctx, woobe.CreateArtifactWorkspaceRequest{
		ExternalNamespace: "example-project",
		ExternalKey:       "handout-collection",
		Name:              "Handout collection",
		QuotaBytes:        100 * 1024 * 1024,
		RetentionDays:     30,
	})
	if err != nil {
		log.Fatal(err)
	}

	size, digest, err := fileDigest(path)
	if err != nil {
		log.Fatal(err)
	}
	file, err := os.Open(path)
	if err != nil {
		log.Fatal(err)
	}
	defer file.Close()
	upload, err := artifacts.Upload(ctx, workspace.ID, woobe.BeginArtifactUploadRequest{
		OperationID: operationID(),
		Path:        "handout.pdf",
		SizeBytes:   size,
		SHA256:      digest,
		ContentType: "application/pdf",
	}, file)
	if err != nil {
		if upload != nil {
			log.Printf("upload %s may need explicit status reconciliation: %v", upload.ID, err)
		}
		log.Fatal(err)
	}
	if upload.Receipt == nil {
		log.Fatalf("upload %s completed without an Artifact receipt", upload.ID)
	}

	job, err := artifacts.RequestProcessing(ctx, workspace.ID, upload.Receipt.ArtifactID,
		woobe.ArtifactProcessingRequest{
			OperationID: operationID(),
			RevisionID:  upload.Receipt.RevisionID,
		})
	if err != nil {
		log.Fatal(err)
	}
	fmt.Printf("workspace=%s artifact=%s revision=%s processing=%s\n",
		workspace.ID, upload.Receipt.ArtifactID, upload.Receipt.RevisionID, job.ID)
}
