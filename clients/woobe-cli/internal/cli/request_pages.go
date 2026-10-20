package cli

import (
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/controlplane"
	"github.com/A1b3rt0M3rcad0/woobe-cli/internal/output"
	"github.com/spf13/cobra"
)

type partialPages struct {
	Data    any
	Message string
	Code    int
	Meta    map[string]any
	Cause   *output.Error
}

func (p *partialPages) Error() string { return p.Message }
func (a *App) requestPagesCommand() {
	var limit int
	var protocol string
	c := &cobra.Command{Use: "request-pages <path>", Short: "Read bounded pages under a reviewed or explicit pagination contract", Args: cobra.ExactArgs(1), RunE: func(cmd *cobra.Command, args []string) error {
		if e := controlplane.ValidatePath(args[0]); e != nil {
			return e
		}
		if limit < 1 || limit > 100 {
			return output.New(2, "max-pages must be between 1 and 100")
		}
		contract := controlplane.PaginationContract(protocol)
		if protocol == "auto" {
			contract = paginationForPath(args[0])
			if contract == "" {
				contract = controlplane.LinkPages
			}
		}
		if !contract.Valid() {
			return output.New(2, "unsupported pagination contract")
		}
		if a.File != "" {
			return output.New(2, "paginated reads do not accept --file")
		}
		q, e := a.query()
		if e != nil {
			return e
		}
		if a.DryRun {
			return a.emit(map[string]any{"method": "GET", "path": args[0], "query": q, "pagination": contract, "max_pages": limit, "executed": false})
		}
		client, e := a.client()
		if e != nil {
			return e
		}
		pages, e := client.RequestPagesWithContract(cmd.Context(), args[0], q, limit, contract)
		return a.emitPages(pages, e)
	}}
	c.Flags().IntVar(&limit, "max-pages", 20, "Bounded page count (1 to 100)")
	c.Flags().StringVar(&protocol, "pagination", "auto", "auto, link, cursor-complete, cursor-has-next or revision-complete")
	a.Root.AddCommand(c)
}
