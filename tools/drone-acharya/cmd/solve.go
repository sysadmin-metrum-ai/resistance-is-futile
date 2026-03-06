package cmd

import (
	"encoding/csv"
	"fmt"
	"os"
	"strings"

	"github.com/sysadmin-metrum-ai/resistance-is-futile/tools/drone-acharya/io"
	"github.com/sysadmin-metrum-ai/resistance-is-futile/tools/drone-acharya/trilat"
	"github.com/spf13/cobra"
)

var (
	solveOut        string
	solveCrazyflie  bool
	solveJSON       bool
	solveValidate   bool
	solvePrecision  int
	solveRotateNed  float64
	solveOffsetX    float64
	solveOffsetY    float64
	solveOffsetZ    float64
	solveZDown      bool
)

func init() {
	solveCmd.Flags().StringVarP(&solveOut, "output", "o", "", "Output file (default stdout)")
	solveCmd.Flags().BoolVarP(&solveCrazyflie, "crazyflie", "c", false, "Emit Python anchor dict")
	solveCmd.Flags().BoolVarP(&solveJSON, "json", "j", false, "JSON output")
	solveCmd.Flags().BoolVarP(&solveValidate, "validate", "v", false, "Show validation table")
	solveCmd.Flags().IntVarP(&solvePrecision, "precision", "p", 3, "Decimal places")
	solveCmd.Flags().Float64Var(&solveRotateNed, "rotate-ned", 0, "Clockwise rotation (degrees) from X-axis to North")
	solveCmd.Flags().Float64Var(&solveOffsetX, "offset-x", 0, "X translation (meters)")
	solveCmd.Flags().Float64Var(&solveOffsetY, "offset-y", 0, "Y translation (meters)")
	solveCmd.Flags().Float64Var(&solveOffsetZ, "offset-z", 0, "Z translation (meters)")
	solveCmd.Flags().BoolVar(&solveZDown, "z-down", false, "Flip Z-axis (+Z up → +Z down for NED)")
}

var solveCmd = &cobra.Command{
	Use:   "solve [input file]",
	Short: "Compute coordinates from distance matrix",
	Long:  "Reads CSV/TSV of pairwise distances and outputs node coordinates (table, --json, or --crazyflie). Use --validate to show recomputed vs measured errors.",
	Example: `  drone-acharya solve distances.csv
  drone-acharya solve distances.csv -o coords.csv --crazyflie
  drone-acharya solve distances.csv --json --validate`,
	Args: cobra.ExactArgs(1),
	RunE: runSolve,
}

// SolveCmd returns the solve subcommand.
func SolveCmd() *cobra.Command { return solveCmd }

func runSolve(cmd *cobra.Command, args []string) error {
	f, err := os.Open(args[0])
	if err != nil {
		return err
	}
	defer f.Close()
	format := io.FormatCSV
	if strings.HasSuffix(strings.ToLower(args[0]), ".tsv") {
		format = io.FormatTSV
	}
	n, dist, err := io.ReadDistances(f, format)
	if err != nil {
		return err
	}
	res, err := trilat.Solve(n, dist)
	if err != nil {
		return err
	}
	coords := res.Coords
	warnings := res.Warnings
	var validation []trilat.ValidationRow
	if solveValidate {
		validation, warnings = trilat.Validate(coords, dist, warnings)
		// Print validation table to stderr or stdout? Spec says "Show validation" - we print table and then output. Print validation table first.
		printValidationTable(validation)
		for _, w := range warnings {
			fmt.Fprintln(os.Stderr, "Warn:", w)
		}
	}
	out := os.Stdout
	if solveOut != "" {
		of, err := os.Create(solveOut)
		if err != nil {
			return err
		}
		defer of.Close()
		out = of
	}
	// Convert trilat.Coord to io.Coord
	ioCoords := make([]io.Coord, len(coords))
	for i, c := range coords {
		ioCoords[i] = io.Coord{c.X, c.Y, c.Z}
	}
	// Apply transformation (rotation, Z-flip, translation)
	ioCoords = io.Transform(ioCoords, solveRotateNed, solveOffsetX, solveOffsetY, solveOffsetZ, solveZDown)
	if solveJSON {
		valRows := make([]io.ValidationRow, len(validation))
		for i, v := range validation {
			valRows[i] = io.ValidationRow{Pair: v.Pair, Measured: v.Measured, Computed: v.Computed, ErrorM: v.ErrorM, ErrorPct: v.ErrorPct}
		}
		return io.WriteJSON(out, ioCoords, valRows, warnings, solvePrecision)
	}
	if solveCrazyflie {
		if !solveZDown {
			fmt.Fprintln(os.Stderr, "Note: for Crazyflie/LPS NED, use --z-down (see COORDINATES.md)")
		}
		io.WriteCrazyflie(out, ioCoords, solvePrecision)
		return nil
	}
	io.WriteTable(out, ioCoords, solvePrecision)
	return nil
}

func printValidationTable(rows []trilat.ValidationRow) {
	w := csv.NewWriter(os.Stderr)
	w.Comma = '\t'
	w.Write([]string{"Pair", "Measured", "Computed", "Error(m)", "Error(%)"})
	for _, r := range rows {
		w.Write([]string{
			r.Pair,
			fmt.Sprintf("%.3f", r.Measured),
			fmt.Sprintf("%.3f", r.Computed),
			fmt.Sprintf("%.3f", r.ErrorM),
			fmt.Sprintf("%.1f", r.ErrorPct),
		})
	}
	w.Flush()
}
