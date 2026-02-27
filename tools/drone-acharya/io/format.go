package io

import (
	"encoding/json"
	"fmt"
	"io"
	"math"
)

// Coord is (x, y, z) in meters.
type Coord [3]float64

// ValidationRow is one pair's validation.
type ValidationRow struct {
	Pair      string  `json:"pair"`
	Measured  float64 `json:"measured"`
	Computed  float64 `json:"computed"`
	ErrorM    float64 `json:"error_m"`
	ErrorPct  float64 `json:"error_pct"`
}

// JSONOutput is the --json structure.
type JSONOutput struct {
	Nodes      []NodeOutput   `json:"nodes"`
	Validation []ValidationRow `json:"validation,omitempty"`
	Warnings   []string       `json:"warnings,omitempty"`
}

// NodeOutput is one node for JSON.
type NodeOutput struct {
	ID int       `json:"id"`
	X  float64   `json:"x"`
	Y  float64   `json:"y"`
	Z  float64   `json:"z"`
}

// WriteTable writes coords as "Node\tX\tY\tZ" with given decimal precision.
func WriteTable(w io.Writer, coords []Coord, precision int) {
	fmt.Fprintf(w, "Node\tX\tY\tZ\n")
	for i, c := range coords {
		fmt.Fprintf(w, "N%d\t%s\t%s\t%s\n", i, formatFloat(c[0], precision), formatFloat(c[1], precision), formatFloat(c[2], precision))
	}
}

// WriteCrazyflie writes Python anchor_positions dict.
func WriteCrazyflie(w io.Writer, coords []Coord, precision int) {
	fmt.Fprintf(w, "anchor_positions = {\n")
	for i, c := range coords {
		fmt.Fprintf(w, "    %d: (%s, %s, %s),\n", i, formatFloat(c[0], precision), formatFloat(c[1], precision), formatFloat(c[2], precision))
	}
	fmt.Fprintf(w, "}\n")
}

// WriteJSON writes JSONOutput.
func WriteJSON(w io.Writer, coords []Coord, validation []ValidationRow, warnings []string, precision int) error {
	out := JSONOutput{
		Nodes: make([]NodeOutput, len(coords)),
	}
	for i, c := range coords {
		out.Nodes[i] = NodeOutput{ID: i, X: roundTo(c[0], precision), Y: roundTo(c[1], precision), Z: roundTo(c[2], precision)}
	}
	if len(validation) > 0 {
		out.Validation = validation
	}
	if len(warnings) > 0 {
		out.Warnings = warnings
	}
	enc := json.NewEncoder(w)
	enc.SetIndent("", "  ")
	return enc.Encode(out)
}

func formatFloat(v float64, precision int) string {
	return fmt.Sprintf("%.*f", precision, v)
}

func roundTo(v float64, precision int) float64 {
	scale := math.Pow(10, float64(precision))
	return math.Round(v*scale) / scale
}
