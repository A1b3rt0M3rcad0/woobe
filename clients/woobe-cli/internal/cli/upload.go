package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
	"io"
	"mime/multipart"
	"os"
	"path/filepath"
)

func (a *App) uploadCommands() {
	var source, collection, title string
	c := &cobra.Command{Use: "upload", Short: "Stream a document file to Knowledge", Args: cobra.NoArgs, RunE: func(cmd *cobra.Command, _ []string) error {
		client, e := a.client()
		if e != nil {
			return e
		}
		if source == "" || collection == "" || a.Project == "" {
			return output.New(2, "--document-file, --collection and --project required")
		}
		f, e := os.Open(source)
		if e != nil {
			return output.New(2, "cannot read document")
		}
		defer f.Close()
		if a.DryRun {
			return a.emit(map[string]any{"path": "/knowledge/documents/upload", "project_id": a.Project, "collection_id": collection, "executed": false})
		}
		reader, writer := io.Pipe()
		defer reader.Close()
		m := multipart.NewWriter(writer)
		go func() {
			err := m.WriteField("project_id", a.Project)
			if err == nil {
				err = m.WriteField("collection_id", collection)
			}
			if err == nil && title != "" {
				err = m.WriteField("title", title)
			}
			if err == nil {
				var part io.Writer
				part, err = m.CreateFormFile("file", filepath.Base(source))
				if err == nil {
					_, err = io.Copy(part, f)
				}
			}
			if err == nil {
				err = m.Close()
			}
			_ = writer.CloseWithError(err)
		}()
		v, _, e := client.RequestReader(cmd.Context(), "POST", "/knowledge/documents/upload", nil, reader, m.FormDataContentType())
		if e != nil {
			return e
		}
		return a.emit(v)
	}}
	c.Flags().StringVar(&source, "document-file", "", "Local document path")
	c.Flags().StringVar(&collection, "collection", "", "Collection ID")
	c.Flags().StringVar(&title, "title", "", "Document title")
	a.group("project knowledge document").AddCommand(c)
}
