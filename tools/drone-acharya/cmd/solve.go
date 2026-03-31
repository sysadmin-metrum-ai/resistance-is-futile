package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/sysadmin-metrum-ai/resistance-is-futile/tools/drone-acharya/graph"
	ioformat "github.com/sysadmin-metrum-ai/resistance-is-futile/tools/drone-acharya/io"
	"github.com/sysadmin-metrum-ai/resistance-is-futile/tools/drone-acharya/legacy"
	"github.com/spf13/cobra"
)

var (
	solveOut       string
	solveCrazyflie bool
	solveJSON      bool
	solveValidate  bool
	solvePrecision int
	solveRotateNed float64
	solveOffsetX   float64
	solveOffsetY   float64
	solveOffsetZ   float64
	solveZDown     bool

	surveyXFrom     string
	surveyXTo       string
	surveyPlaneNode string
	surveyPosZNode  string
)

func init() {
	solveCmd.Flags().StringVarP(&solveOut, "output", "o", "", "Output file (default stdout)")
	solveCmd.Flags().BoolVarP(&solveCrazyflie, "crazyflie", "c", false, "Emit Python anchor dict (anchors only)")
	solveCmd.Flags().BoolVarP(&solveJSON, "json", "j", false, "JSON output")
	solveCmd.Flags().BoolVarP(&solveValidate, "validate", "v", false, "Show validation table (residuals)")
	solveCmd.Flags().IntVarP(&solvePrecision, "precision", "p", 3, "Decimal places")
	solveCmd.Flags().Float64Var(&solveRotateNed, "rotate-ned", 0, "Clockwise rotation (degrees) from X-axis to North")
	solveCmd.Flags().Float64Var(&solveOffsetX, "offset-x", 0, "X translation (meters)")
	solveCmd.Flags().Float64Var(&solveOffsetY, "offset-y", 0, "Y translation (meters)")
	solveCmd.Flags().Float64Var(&solveOffsetZ, "offset-z", 0, "Z translation (meters)")
	solveCmd.Flags().BoolVar(&solveZDown, "z-down", false, "Flip Z-axis (+Z up -> +Z down for NED)")

	solveCmd.Flags().StringVar(&surveyXFrom, "survey-x-from", "", "Node ID placed at the survey origin")
	solveCmd.Flags().StringVar(&surveyXTo, "survey-x-to", "", "Node ID placed on +X from the survey origin")
	solveCmd.Flags().StringVar(&surveyPlaneNode, "survey-plane-node", "", "Node ID that fixes the survey XY plane")
	solveCmd.Flags().StringVar(&surveyPosZNode, "survey-positive-z-node", "", "Node on the +Z side of that plane")
}

var solveCmd = &cobra.Command{
	Use:   "solve [input file]",
	Short: "Compute coordinates from CSV/TSV distances or JSONL graph",
	Long:  "Reads a classic CSV/TSV distance matrix or JSONL node/edge graph and outputs node coordinates (table, --json, or --crazyflie). Use --validate to show residuals.",
	Example: `  drone-acharya solve distances.csv --validate
  drone-acharya solve distances.csv --crazyflie --z-down
  drone-acharya solve graph.jsonl
  drone-acharya solve graph.jsonl -o coords.csv --crazyflie
  drone-acharya solve graph.jsonl --json --validate`,
	Args: cobra.ExactArgs(1),
	RunE: runSolve,
}

func SolveCmd() *cobra.Command { return solveCmd }

func runSolve(cmd *cobra.Command, args []string) error {
	ext := strings.ToLower(filepath.Ext(args[0]))
	if ext == ".csv" || ext == ".tsv" {
		return runSolveClassic(args[0], ext)
	}

	return runSolveGraph(args[0])
}

func runSolveGraph(path string) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()

	p, err := graph.ReadProblem(f)
	if err != nil {
		return err
	}

	// CLI survey flags override JSONL survey_frame
	if surveyXFrom != "" || surveyXTo != "" || surveyPlaneNode != "" || surveyPosZNode != "" {
		if surveyXFrom == "" || surveyXTo == "" || surveyPlaneNode == "" || surveyPosZNode == "" {
			return fmt.Errorf("all four survey flags required: --survey-x-from, --survey-x-to, --survey-plane-node, --survey-positive-z-node")
		}
		p.SurveyFrame = &graph.SurveyFrame{
			XFrom:         surveyXFrom,
			XTo:           surveyXTo,
			PlaneNode:     surveyPlaneNode,
			PositiveZNode: surveyPosZNode,
		}
	}

	basisA, basisB, basisC, err := graph.PickBasis(p)
	if err != nil {
		return err
	}

	initCoords, err := graph.InitCoords(p, basisA, basisB, basisC)
	if err != nil {
		return err
	}

	coords, err := graph.Solve(p, initCoords, basisA, basisB, basisC)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Warn:", err)
	}

	// Apply survey frame if defined
	if p.SurveyFrame != nil {
		coords, err = graph.ApplySurveyFrame(p, coords)
		if err != nil {
			return err
		}
	}

	// Validate (before transform, using survey-frame coords)
	var residuals []graph.EdgeResidual
	var rms float64
	var warnings []string
	if solveValidate {
		residuals, rms, warnings = graph.Validate(p, coords)
		printResidualTable(residuals, rms)
		for _, w := range warnings {
			fmt.Fprintln(os.Stderr, "Warn:", w)
		}
	}

	// Convert to io.Coord for transform and output
	ioCoords := make([]ioformat.Coord, len(coords))
	for i, c := range coords {
		ioCoords[i] = ioformat.Coord(c)
	}

	ioCoords = ioformat.Transform(ioCoords, solveRotateNed, solveOffsetX, solveOffsetY, solveOffsetZ, solveZDown)

	out := os.Stdout
	if solveOut != "" {
		of, err := os.Create(solveOut)
		if err != nil {
			return err
		}
		defer of.Close()
		out = of
	}

	if solveJSON {
		ioResiduals := make([]ioformat.ValidationRow, len(residuals))
		for i, r := range residuals {
			ioResiduals[i] = ioformat.ValidationRow{
				Pair: r.A + "-" + r.B, Measured: r.Measured,
				Computed: roundTo(r.Computed, solvePrecision),
				ErrorM: roundTo(r.ErrorM, solvePrecision),
				ErrorPct: roundTo(r.ErrorM/r.Measured*100, 1),
			}
		}
		return ioformat.WriteJSONNodes(out, p, ioCoords, ioResiduals, warnings, solvePrecision)
	}

	if solveCrazyflie {
		if !solveZDown {
			fmt.Fprintln(os.Stderr, "Note: for Crazyflie/LPS NED, use --z-down (see COORDINATES.md)")
		}
		ioformat.WriteCrazyflieAnchors(out, p, ioCoords, solvePrecision)
		return nil
	}

	ioformat.WriteTableGraph(out, p, ioCoords, solvePrecision)
	return nil
}

func runSolveClassic(path string, ext string) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()

	format := ioformat.FormatCSV
	if ext == ".tsv" {
		format = ioformat.FormatTSV
	}

	n, dist, err := ioformat.ReadDistances(f, format)
	if err != nil {
		return err
	}

	if surveyXFrom != "" || surveyXTo != "" || surveyPlaneNode != "" || surveyPosZNode != "" {
		return fmt.Errorf("survey frame flags are only supported for JSONL graph inputs")
	}

	result, err := legacy.Solve(n, dist)
	if err != nil {
		return err
	}

	var validation []legacy.ValidationRow
	warnings := append([]string(nil), result.Warnings...)
	if solveValidate {
		validation, warnings = legacy.Validate(result.Coords, dist, warnings)
		printLegacyValidationTable(validation)
		for _, w := range warnings {
			fmt.Fprintln(os.Stderr, "Warn:", w)
		}
	}

	ioCoords := make([]ioformat.Coord, len(result.Coords))
	for i, c := range result.Coords {
		ioCoords[i] = ioformat.Coord{c.X, c.Y, c.Z}
	}
	ioCoords = ioformat.Transform(ioCoords, solveRotateNed, solveOffsetX, solveOffsetY, solveOffsetZ, solveZDown)

	out := os.Stdout
	if solveOut != "" {
		of, err := os.Create(solveOut)
		if err != nil {
			return err
		}
		defer of.Close()
		out = of
	}

	provider := classicNodeProvider{n: n}

	if solveJSON {
		ioResiduals := make([]ioformat.ValidationRow, len(validation))
		for i, r := range validation {
			ioResiduals[i] = ioformat.ValidationRow{
				Pair:     r.Pair,
				Measured: r.Measured,
				Computed: roundTo(r.Computed, solvePrecision),
				ErrorM:   roundTo(r.ErrorM, solvePrecision),
				ErrorPct: roundTo(r.ErrorPct, 1),
			}
		}
		return ioformat.WriteJSONNodes(out, provider, ioCoords, ioResiduals, warnings, solvePrecision)
	}

	if solveCrazyflie {
		if !solveZDown {
			fmt.Fprintln(os.Stderr, "Note: for Crazyflie/LPS NED, use --z-down (see COORDINATES.md)")
		}
		ioformat.WriteCrazyflieAnchors(out, provider, ioCoords, solvePrecision)
		return nil
	}

	ioformat.WriteTableGraph(out, provider, ioCoords, solvePrecision)
	return nil
}

type classicNodeProvider struct {
	n int
}

func (p classicNodeProvider) NodeCount() int { return p.n }

func (p classicNodeProvider) NodeAt(i int) (name, kind string, anchorID int) {
	return fmt.Sprintf("N%d", i), "anchor", i
}

func printResidualTable(residuals []graph.EdgeResidual, rms float64) {
	fmt.Fprintf(os.Stderr, "Pair\tMeasured\tComputed\tError(m)\tResidual\n")
	for _, r := range residuals {
		fmt.Fprintf(os.Stderr, "%s-%s\t%.3f\t%.3f\t%.3f\t%.3f\n",
			r.A, r.B, r.Measured, r.Computed, r.ErrorM, r.Residual)
	}
	fmt.Fprintf(os.Stderr, "RMS (sigma-normalized): %f\n", rms)
}

func printLegacyValidationTable(rows []legacy.ValidationRow) {
	fmt.Fprintf(os.Stderr, "Pair\tMeasured\tComputed\tError(m)\tError(%%)\n")
	for _, r := range rows {
		fmt.Fprintf(os.Stderr, "%s\t%.3f\t%.3f\t%.3f\t%.1f\n",
			r.Pair, r.Measured, r.Computed, r.ErrorM, r.ErrorPct)
	}
}

func roundTo(v float64, precision int) float64 {
	scale := 1.0
	for i := 0; i < precision; i++ {
		scale *= 10
	}
	return float64(int(v*scale+0.5)) / scale
}
