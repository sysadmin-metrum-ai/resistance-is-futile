package io

import (
	"encoding/json"
	"fmt"
	"io"
	"math"
)

type Coord [3]float64

type ValidationRow struct {
	Pair     string  `json:"pair"`
	Measured float64 `json:"measured"`
	Computed float64 `json:"computed"`
	ErrorM   float64 `json:"error_m"`
	ErrorPct float64 `json:"error_pct"`
}

type GraphNodeRow struct {
	Name     string  `json:"name"`
	Kind     string  `json:"kind"`
	AnchorID int     `json:"anchor_id,omitempty"`
	X        float64 `json:"x"`
	Y        float64 `json:"y"`
	Z        float64 `json:"z"`
}

type JSONOutput struct {
	Nodes      []GraphNodeRow  `json:"nodes"`
	Validation []ValidationRow `json:"validation,omitempty"`
	Warnings   []string        `json:"warnings,omitempty"`
}

// NodeProvider is satisfied by *graph.Problem (avoids import cycle).
type NodeProvider interface {
	AnchorNodes() []struct {
		ID       string
		Kind     string
		AnchorID int
		Index    int
	}
}

// WriteTableGraph writes coords as "Node\tKind\tX\tY\tZ".
func WriteTableGraph(w io.Writer, p interface{ NodeCount() int; NodeAt(int) (string, string, int) }, coords []Coord, precision int) {
	fmt.Fprintf(w, "Node\tKind\tX\tY\tZ\n")
	for i := 0; i < p.NodeCount(); i++ {
		name, kind, _ := p.NodeAt(i)
		c := coords[i]
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\n", name, kind,
			formatFloat(c[0], precision), formatFloat(c[1], precision), formatFloat(c[2], precision))
	}
}

// WriteCrazyflieAnchors writes Python anchor_positions dict (anchors only, keyed by anchor_id).
func WriteCrazyflieAnchors(w io.Writer, p interface{ NodeCount() int; NodeAt(int) (string, string, int) }, coords []Coord, precision int) {
	fmt.Fprintf(w, "anchor_positions = {\n")
	for i := 0; i < p.NodeCount(); i++ {
		_, kind, anchorID := p.NodeAt(i)
		if kind != "anchor" || anchorID < 0 {
			continue
		}
		c := coords[i]
		fmt.Fprintf(w, "    %d: (%s, %s, %s),\n", anchorID,
			formatFloat(c[0], precision), formatFloat(c[1], precision), formatFloat(c[2], precision))
	}
	fmt.Fprintf(w, "}\n")
}

// WriteJSONNodes writes full JSON output with node info.
func WriteJSONNodes(w io.Writer, p interface{ NodeCount() int; NodeAt(int) (string, string, int) }, coords []Coord, validation []ValidationRow, warnings []string, precision int) error {
	out := JSONOutput{}
	for i := 0; i < p.NodeCount(); i++ {
		name, kind, anchorID := p.NodeAt(i)
		c := coords[i]
		row := GraphNodeRow{
			Name:     name,
			Kind:     kind,
			AnchorID: anchorID,
			X:        roundTo(c[0], precision),
			Y:        roundTo(c[1], precision),
			Z:        roundTo(c[2], precision),
		}
		out.Nodes = append(out.Nodes, row)
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
