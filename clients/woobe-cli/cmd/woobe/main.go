package main

import (
	"context"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/cli"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	os.Exit(cli.New(os.Stdin, os.Stdout, os.Stderr).Execute(ctx, os.Args[1:]))
}
