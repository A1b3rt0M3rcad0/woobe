package main

import (
	"context"
	"fmt"
	"log"
	"os"

	woobe "github.com/A1b3rt0M3rcad0/woobe-sdk-go"
)

func main() {
	client, err := woobe.New()
	if err != nil { log.Fatal(err) }
	defer client.CloseIdleConnections()

	agent, err := client.Connect.Agent("assistant", os.Getenv("WOOBE_RUNTIME_KEY"))
	if err != nil { log.Fatal(err) }

	chat, err := agent.Chat("Explique a Woobe em uma frase.", nil)
	if err != nil { log.Fatal(err) }

	stream, err := chat.Stream(context.Background())
	if err != nil { log.Fatal(err) }

	for event := range stream.Events {
		if event.Type == "token" {
			if content, ok := event.Payload["content"].(string); ok { fmt.Print(content) }
		}
	}
	if err := stream.Err(); err != nil { log.Fatal(err) }
	fmt.Println()

	if result := stream.Result(); result != nil {
		fmt.Printf("run=%s session=%s\n", result.RunID, result.SessionID)
	}
}
