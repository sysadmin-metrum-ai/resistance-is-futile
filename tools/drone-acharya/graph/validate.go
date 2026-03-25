package graph

import (
	"fmt"
	"math"
)

// Validate computes per-edge residuals and checks triangle inequality.
func Validate(p *Problem, coords []Coord) ([]EdgeResidual, float64, []string) {
	var residuals []EdgeResidual
	var warnings []string
	sumSq := 0.0

	for _, e := range p.Edges {
		iA := p.nodeIndex[e.A]
		iB := p.nodeIndex[e.B]
		computed := coords[iA].Dist(coords[iB])
		errM := math.Abs(e.Distance - computed)
		normalized := (e.Distance - computed) / e.Sigma
		sumSq += normalized * normalized

		residuals = append(residuals, EdgeResidual{
			A:        e.A,
			B:        e.B,
			Measured: e.Distance,
			Computed: computed,
			ErrorM:   errM,
			Residual: normalized,
		})

		if math.Abs(normalized) > 3.0 {
			warnings = append(warnings, fmt.Sprintf("large normalized residual on %s-%s: %.2f sigma", e.A, e.B, normalized))
		}
	}

	rms := 0.0
	if len(p.Edges) > 0 {
		rms = math.Sqrt(sumSq / float64(len(p.Edges)))
	}

	// Triangle inequality checks
	for _, w := range checkTriangleInequality(p) {
		warnings = append(warnings, w)
	}

	return residuals, rms, warnings
}

func checkTriangleInequality(p *Problem) []string {
	var warnings []string
	type pair struct{ a, b string }
	distMap := make(map[pair]float64, len(p.Edges))
	for _, e := range p.Edges {
		k1 := pair{e.A, e.B}
		k2 := pair{e.B, e.A}
		distMap[k1] = e.Distance
		distMap[k2] = e.Distance
	}

	for i := 0; i < len(p.Nodes); i++ {
		for j := i + 1; j < len(p.Nodes); j++ {
			dij, ok1 := distMap[pair{p.Nodes[i].ID, p.Nodes[j].ID}]
			if !ok1 {
				continue
			}
			for k := j + 1; k < len(p.Nodes); k++ {
				dik, ok2 := distMap[pair{p.Nodes[i].ID, p.Nodes[k].ID}]
				djk, ok3 := distMap[pair{p.Nodes[j].ID, p.Nodes[k].ID}]
				if !ok2 || !ok3 {
					continue
				}
				if violatesTriangleInequality(dij, dik, djk) {
					warnings = append(warnings, fmt.Sprintf(
						"triangle inconsistency on (%q,%q,%q): distances %.3f, %.3f, %.3f violate triangle inequality",
						p.Nodes[i].ID, p.Nodes[j].ID, p.Nodes[k].ID, dij, dik, djk))
				}
			}
		}
	}
	return warnings
}

func violatesTriangleInequality(a, b, c float64) bool {
	return a > b+c || b > a+c || c > a+b
}
