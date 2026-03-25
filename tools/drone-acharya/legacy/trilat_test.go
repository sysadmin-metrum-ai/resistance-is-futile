package legacy

import (
	"math"
	"testing"
)

func TestSolve_4NodesSquare(t *testing.T) {
	// Unit square in xy-plane: N0=(0,0,0), N1=(4,0,0), N2=(4,3,0), N3=(0,3,0)
	// Distances: d01=4, d02=5, d03=3, d12=3, d13=5, d23=4
	dist := map[[2]int]float64{
		{0, 1}: 4, {0, 2}: 5, {0, 3}: 3,
		{1, 2}: 3, {1, 3}: 5,
		{2, 3}: 4,
	}
	res, err := Solve(4, dist)
	if err != nil {
		t.Fatal(err)
	}
	coords := res.Coords
	eps := 1e-6
	if math.Abs(coords[0].X) > eps || math.Abs(coords[0].Y) > eps || math.Abs(coords[0].Z) > eps {
		t.Errorf("N0 want (0,0,0) got (%f,%f,%f)", coords[0].X, coords[0].Y, coords[0].Z)
	}
	if math.Abs(coords[1].X-4) > eps || math.Abs(coords[1].Y) > eps || math.Abs(coords[1].Z) > eps {
		t.Errorf("N1 want (4,0,0) got (%f,%f,%f)", coords[1].X, coords[1].Y, coords[1].Z)
	}
	if math.Abs(coords[2].X-4) > eps || math.Abs(coords[2].Y-3) > eps || math.Abs(coords[2].Z) > eps {
		t.Errorf("N2 want (4,3,0) got (%f,%f,%f)", coords[2].X, coords[2].Y, coords[2].Z)
	}
	if math.Abs(coords[3].X) > eps || math.Abs(coords[3].Y-3) > eps || math.Abs(coords[3].Z) > eps {
		t.Errorf("N3 want (0,3,0) got (%f,%f,%f)", coords[3].X, coords[3].Y, coords[3].Z)
	}
}

func TestSolve_NLessThan4(t *testing.T) {
	_, err := Solve(3, map[[2]int]float64{})
	if err == nil {
		t.Fatal("expected error for N<4")
	}
	if err.Error() != "need at least 4 nodes for 3D trilateration" {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestSolve_Collinear(t *testing.T) {
	// N0=(0,0), N1=(4,0), N2=(8,0) collinear
	dist := map[[2]int]float64{
		{0, 1}: 4, {0, 2}: 8, {0, 3}: 5,
		{1, 2}: 4, {1, 3}: 3,
		{2, 3}: 3,
	}
	// Make N0,N1,N2 collinear: d01=4, d02=8, d12=4 => N2 on x-axis at 8
	_, err := Solve(4, dist)
	if err == nil {
		t.Fatal("expected collinear error")
	}
	if err.Error() != "nodes 0, 1, 2 are collinear — pick non-collinear N2" {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestSolve_D01TooSmall(t *testing.T) {
	dist := map[[2]int]float64{
		{0, 1}: 0, {0, 2}: 5, {0, 3}: 3,
		{1, 2}: 3, {1, 3}: 5,
		{2, 3}: 4,
	}
	_, err := Solve(4, dist)
	if err == nil {
		t.Fatal("expected error for d01=0")
	}
	if err.Error() != "distance N0–N1 too small or zero (0); need distinct anchors" {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestValidate(t *testing.T) {
	dist := map[[2]int]float64{
		{0, 1}: 4, {0, 2}: 5, {0, 3}: 3,
		{1, 2}: 3, {1, 3}: 5,
		{2, 3}: 4,
	}
	coords := []Coord{
		{0, 0, 0}, {4, 0, 0}, {4, 3, 0}, {0, 3, 0},
	}
	rows, warnings := Validate(coords, dist, nil)
	if len(rows) != 6 {
		t.Errorf("want 6 validation rows, got %d", len(rows))
	}
	for _, r := range rows {
		if r.ErrorM > 1e-6 {
			t.Errorf("pair %s: unexpected error %f", r.Pair, r.ErrorM)
		}
	}
	if len(warnings) == 0 {
		t.Error("expected max error warning line when validation runs")
	}
}
