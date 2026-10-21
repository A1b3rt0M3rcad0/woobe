package main

import (
	"context"
	"fmt"
	"io"
	"log"
	"os"

	woobe "github.com/A1b3rt0M3rcad0/woobe-sdk-go"
)

func requiredEnv(name string) string {
	value := os.Getenv(name)
	if value == "" {
		log.Fatalf("set %s in the process environment", name)
	}
	return value
}

func main() {
	ctx := context.Background()
	client, err := woobe.New()
	if err != nil {
		log.Fatal(err)
	}
	defer client.CloseIdleConnections()

	projectID := requiredEnv("WOOBE_PROJECT_ID")
	runtimeKey := requiredEnv("WOOBE_RUNTIME_KEY")
	workspaceID := requiredEnv("WOOBE_ARTIFACT_WORKSPACE_ID")
	artifactID := requiredEnv("WOOBE_SOURCE_ARTIFACT_ID")
	revisionID := requiredEnv("WOOBE_SOURCE_REVISION_ID")

	artifacts, err := client.Artifacts(projectID, runtimeKey, woobe.ArtifactStaging)
	if err != nil {
		log.Fatal(err)
	}
	source, err := artifacts.GetRevision(ctx, workspaceID, artifactID, revisionID)
	if err != nil {
		log.Fatal(err)
	}

	tutor, err := client.Connect.Agent(requiredEnv("WOOBE_AGENT_ALIAS"), runtimeKey)
	if err != nil {
		log.Fatal(err)
	}
	chat, err := tutor.ChatParts([]woobe.ContentPart{
		woobe.TextPart("Summarize the handout's retention rule and cite its exact source page."),
		woobe.ArtifactPart(woobe.ArtifactRef{ArtifactID: source.ArtifactID, RevisionID: source.ID}, source.ContentType),
	}, nil)
	if err != nil {
		log.Fatal(err)
	}
	stream, err := chat.Stream(ctx)
	if err != nil {
		log.Fatal(err)
	}
	for range stream.Events {
	}
	if err := stream.Err(); err != nil {
		log.Fatal(err)
	}
	result := stream.Result()
	if result == nil {
		log.Fatal("Run ended without a terminal result")
	}
	fmt.Println(result.Answer)
	for _, ref := range result.SourceRefs {
		if ref.Locator != nil && ref.Locator.PageNumber != nil {
			fmt.Printf("source %s@%s page %d\n", ref.ArtifactID, ref.RevisionID, *ref.Locator.PageNumber)
		} else {
			fmt.Printf("source %s@%s\n", ref.ArtifactID, ref.RevisionID)
		}
	}

	if len(result.OutputArtifacts) == 0 {
		return
	}
	output := result.OutputArtifacts[0]
	download, err := artifacts.Download(ctx, workspaceID, output.Ref.ArtifactID, output.Ref.RevisionID, "")
	if err != nil {
		log.Fatal(err)
	}
	defer download.Body.Close()
	file, err := os.Create("./woobe-result.bin")
	if err != nil {
		log.Fatal(err)
	}
	_, copyErr := io.Copy(file, download.Body)
	closeErr := file.Close()
	if copyErr != nil {
		log.Fatal(copyErr)
	}
	if closeErr != nil {
		log.Fatal(closeErr)
	}
	fmt.Println("downloaded exact result revision to ./woobe-result.bin")
}
