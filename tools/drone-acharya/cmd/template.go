package cmd

import (
	"fmt"
	"os"

	"github.com/metrum-ai/drone-acharya/io"
	"github.com/spf13/cobra"
)

var (
	templateNodes  int
	templateFormat string
	templateOut    string
)

func init() {
	templateCmd.Flags().IntVarP(&templateNodes, "nodes", "n", 4, "Number of nodes (4-8)")
	templateCmd.Flags().StringVarP(&templateFormat, "format", "f", "csv", "Format: csv or tsv")
	templateCmd.Flags().StringVarP(&templateOut, "output", "o", "", "Output file (default stdout)")
}

var templateCmd = &cobra.Command{
	Use:   "template",
	Short: "Generate measurement template for pairwise distances",
	Long:  "Writes an upper-triangle CSV/TSV template. Fill in measured distances (meters), then run solve.",
	Example: `  drone-acharya template -n 6 -f csv -o distances.csv
  drone-acharya template -n 8 -f tsv -o distances.tsv`,
	RunE: runTemplate,
}

// TemplateCmd returns the template subcommand.
func TemplateCmd() *cobra.Command { return templateCmd }

func runTemplate(cmd *cobra.Command, args []string) error {
	if templateNodes < 4 || templateNodes > 8 {
		return fmt.Errorf("nodes must be 4-8, got %d", templateNodes)
	}
	var format io.Format
	switch templateFormat {
	case "csv":
		format = io.FormatCSV
	case "tsv":
		format = io.FormatTSV
	default:
		return fmt.Errorf("format must be csv or tsv, got %q", templateFormat)
	}
	out := os.Stdout
	if templateOut != "" {
		f, err := os.Create(templateOut)
		if err != nil {
			return err
		}
		defer f.Close()
		out = f
	}
	return io.WriteTemplate(out, templateNodes, format)
}
