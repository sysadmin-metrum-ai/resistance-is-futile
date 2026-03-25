package main

import (
	"github.com/sysadmin-metrum-ai/resistance-is-futile/tools/drone-acharya/cmd"
	"github.com/spf13/cobra"
)

func main() {
	root := &cobra.Command{
		Use:   "drone-acharya",
		Short: "Crazyflie Loco positioning node coordinate calculator",
		Long: `Computes 3D coordinates for Loco positioning nodes from JSONL graph
measurements using the graph-based solver.

  Step 1: Create a graph.jsonl with anchor/latent nodes and distance edges.
  Step 2: Run solve on the graph file to get node coordinates.
  Step 3: Export anchors for Crazyflie/LPS with --crazyflie --z-down.

Examples:
  drone-acharya solve graph.jsonl
  drone-acharya solve graph.jsonl --validate
  drone-acharya solve graph.jsonl --crazyflie --z-down
  make build
  make dist`,
	}
	root.AddCommand(cmd.TemplateCmd(), cmd.SolveCmd())
	root.Execute()
}
