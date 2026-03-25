package legacy

import (
	"fmt"
	"math"
)

const (
	epsilon   = 1e-9
	largePct  = 5.0
)

// Coord is (x, y, z) in meters.
type Coord struct {
	X, Y, Z float64
}

// Result holds solved coords and any warnings from Solve.
type Result struct {
	Coords   []Coord
	Warnings []string
}

// ValidationRow is one pair's validation (measured vs computed).
type ValidationRow struct {
	Pair     string
	Measured float64
	Computed float64
	ErrorM   float64
	ErrorPct float64
}

// Solve computes 3D coordinates from pairwise distances. Distances keyed by (i,j) with i < j.
// Returns coords and warnings (e.g. negative sqrt clamped, large validation error).
func Solve(n int, dist map[[2]int]float64) (*Result, error) {
	if n < 4 {
		return nil, fmt.Errorf("need at least 4 nodes for 3D trilateration")
	}
	d := func(i, j int) float64 {
		if i > j {
			i, j = j, i
		}
		return dist[[2]int{i, j}]
	}
	coords := make([]Coord, n)
	coords[0] = Coord{0, 0, 0}
	d01 := d(0, 1)
	if d01 <= epsilon {
		return nil, fmt.Errorf("distance N0–N1 too small or zero (%g); need distinct anchors", d01)
	}
	coords[1] = Coord{d01, 0, 0}
	x2 := (d01*d01 + d(0, 2)*d(0, 2) - d(1, 2)*d(1, 2)) / (2 * d01)
	y2Sq := d(0, 2)*d(0, 2) - x2*x2
	var warnings []string
	if y2Sq < 0 {
		warnings = append(warnings, "inconsistent measurements (negative value under sqrt for N2); clamped to 0")
		y2Sq = 0
	}
	y2 := math.Sqrt(y2Sq)
	if math.Abs(y2) < epsilon {
		return nil, fmt.Errorf("nodes 0, 1, 2 are collinear — pick non-collinear N2")
	}
	coords[2] = Coord{x2, y2, 0}
	for i := 3; i < n; i++ {
		di0 := d(i, 0)
		di1 := d(i, 1)
		di2 := d(i, 2)
		xi := (di0*di0 + d01*d01 - di1*di1) / (2 * d01)
		yi := (di0*di0 - di2*di2 - 2*xi*x2 + x2*x2 + y2*y2) / (2 * y2)
		ziSq := di0*di0 - xi*xi - yi*yi
		if ziSq < 0 {
			warnings = append(warnings, fmt.Sprintf("inconsistent measurements (negative value under sqrt for N%d); clamped to 0", i))
			ziSq = 0
		}
		zi := math.Sqrt(ziSq)
		coords[i] = Coord{xi, yi, zi}
	}
	return &Result{Coords: coords, Warnings: warnings}, nil
}

// Validate recomputes pairwise distances from coords and returns per-pair errors.
// Appends to warnings for any pair with relative error > 5%.
func Validate(coords []Coord, dist map[[2]int]float64, warnings []string) (rows []ValidationRow, outWarnings []string) {
	outWarnings = append([]string(nil), warnings...)
	var maxErrM, maxErrPct float64
	var maxPair string
	for i := 0; i < len(coords); i++ {
		for j := i + 1; j < len(coords); j++ {
			measured := dist[[2]int{i, j}]
			computed := euclidean(coords[i], coords[j])
			errM := math.Abs(measured - computed)
			errPct := 0.0
			if measured > 0 {
				errPct = errM / measured * 100
			}
			rows = append(rows, ValidationRow{
				Pair:     fmt.Sprintf("N%d-N%d", i, j),
				Measured: measured,
				Computed: computed,
				ErrorM:   errM,
				ErrorPct: errPct,
			})
			if errPct > largePct {
				outWarnings = append(outWarnings, fmt.Sprintf("large error on pair N%d-N%d — re-measure?", i, j))
			}
			if errM >= maxErrM {
				maxErrM = errM
				maxErrPct = errPct
				maxPair = fmt.Sprintf("N%d-N%d", i, j)
			}
		}
	}
	if maxPair != "" {
		outWarnings = append(outWarnings, fmt.Sprintf("max error: %.3fm (%.1f%%) on %s", maxErrM, maxErrPct, maxPair))
	}
	return rows, outWarnings
}

func euclidean(a, b Coord) float64 {
	dx := a.X - b.X
	dy := a.Y - b.Y
	dz := a.Z - b.Z
	return math.Sqrt(dx*dx + dy*dy + dz*dz)
}
