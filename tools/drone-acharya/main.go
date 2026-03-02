package main

import (
	"github.com/sysadmin-metrum-ai/resistance-is-futile/tools/drone-acharya/cmd"
	"github.com/spf13/cobra"
)

func main() {
	root := &cobra.Command{
		Use:   "drone-acharya",
		Short: "Crazyflie Loco positioning node coordinate calculator",
		Long: `Computes 3D coordinates for Loco positioning nodes from pairwise distance
measurements using trilateration.

  Step 1: Generate a template, fill in measured distances (meters).
  Step 2: Run solve on the filled file to get node coordinates.

Examples:
  drone-acharya template -n 6 -f csv -o distances.csv
  drone-acharya solve distances.csv
  drone-acharya solve distances.csv -o coords.csv --crazyflie`,
	}
	root.AddCommand(cmd.TemplateCmd(), cmd.SolveCmd())
	root.Execute()
}
