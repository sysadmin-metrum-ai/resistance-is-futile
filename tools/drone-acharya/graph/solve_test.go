package graph

import (
	"math"
	"strings"
	"testing"
)

func TestReadProblem_Graph4(t *testing.T) {
	input := `{"type":"node","id":"A0","kind":"anchor","anchor_id":0}
{"type":"node","id":"A1","kind":"anchor","anchor_id":1}
{"type":"node","id":"L0","kind":"latent"}
{"type":"node","id":"L1","kind":"latent"}
{"type":"survey_frame","x_from":"A0","x_to":"A1","plane_node":"L0","positive_z_node":"L1"}
{"type":"edge","a":"A0","b":"A1","distance":4}
{"type":"edge","a":"A0","b":"L0","distance":3}
{"type":"edge","a":"A1","b":"L0","distance":5}
{"type":"edge","a":"A0","b":"L1","distance":3}
{"type":"edge","a":"L1","b":"L0","distance":4}
{"type":"edge","a":"A1","b":"L1","distance":5}
`
	p, err := ReadProblem(strings.NewReader(input))
	if err != nil {
		t.Fatal(err)
	}
	if len(p.Nodes) != 4 {
		t.Fatalf("want 4 nodes, got %d", len(p.Nodes))
	}
	if len(p.Edges) != 6 {
		t.Fatalf("want 6 edges, got %d", len(p.Edges))
	}
	if p.SurveyFrame == nil {
		t.Fatal("expected survey_frame to be parsed")
	}
	if p.SurveyFrame.XFrom != "A0" || p.SurveyFrame.PositiveZNode != "L1" {
		t.Errorf("unexpected survey_frame: %+v", p.SurveyFrame)
	}
}

func TestSolve_Graph4_Exact(t *testing.T) {
	input := `{"type":"node","id":"A0","kind":"anchor","anchor_id":0}
{"type":"node","id":"A1","kind":"anchor","anchor_id":1}
{"type":"node","id":"L0","kind":"latent"}
{"type":"node","id":"L1","kind":"latent"}
{"type":"edge","a":"A0","b":"A1","distance":4}
{"type":"edge","a":"A0","b":"L0","distance":3}
{"type":"edge","a":"A1","b":"L0","distance":5}
{"type":"edge","a":"A0","b":"L1","distance":3}
{"type":"edge","a":"L1","b":"L0","distance":4}
{"type":"edge","a":"A1","b":"L1","distance":5}
`
	p, err := ReadProblem(strings.NewReader(input))
	if err != nil {
		t.Fatal(err)
	}

	bA, bB, bC, err := PickBasis(p)
	if err != nil {
		t.Fatal(err)
	}
	init, err := InitCoords(p, bA, bB, bC)
	if err != nil {
		t.Fatal(err)
	}
	coords, err := Solve(p, init, bA, bB, bC)
	if err != nil {
		t.Fatal(err)
	}

	_, rms, _ := Validate(p, coords)
	if rms > 0.001 {
		t.Errorf("RMS too high for exact distances: %f", rms)
	}
}

func TestSolve_Graph4_WithSurveyFrame(t *testing.T) {
	input := `{"type":"node","id":"A0","kind":"anchor","anchor_id":0}
{"type":"node","id":"A1","kind":"anchor","anchor_id":1}
{"type":"node","id":"L0","kind":"latent"}
{"type":"node","id":"L1","kind":"latent"}
{"type":"survey_frame","x_from":"A0","x_to":"A1","plane_node":"L0","positive_z_node":"L1"}
{"type":"edge","a":"A0","b":"A1","distance":4}
{"type":"edge","a":"A0","b":"L0","distance":3}
{"type":"edge","a":"A1","b":"L0","distance":5}
{"type":"edge","a":"A0","b":"L1","distance":3}
{"type":"edge","a":"L1","b":"L0","distance":4}
{"type":"edge","a":"A1","b":"L1","distance":5}
`
	p, err := ReadProblem(strings.NewReader(input))
	if err != nil {
		t.Fatal(err)
	}

	bA, bB, bC, err := PickBasis(p)
	if err != nil {
		t.Fatal(err)
	}
	init, err := InitCoords(p, bA, bB, bC)
	if err != nil {
		t.Fatal(err)
	}
	coords, err := Solve(p, init, bA, bB, bC)
	if err != nil {
		t.Fatal(err)
	}
	coords, err = ApplySurveyFrame(p, coords)
	if err != nil {
		t.Fatal(err)
	}

	// A0 should be at origin
	a0 := coords[p.nodeIndex["A0"]]
	if math.Abs(a0[0])+math.Abs(a0[1])+math.Abs(a0[2]) > 1e-6 {
		t.Errorf("A0 not at origin: %v", a0)
	}

	// A1 should be on +X axis
	a1 := coords[p.nodeIndex["A1"]]
	if math.Abs(a1[1]) > 1e-6 || math.Abs(a1[2]) > 1e-6 {
		t.Errorf("A1 not on +X axis: %v", a1)
	}
	if a1[0] < 3.9 {
		t.Errorf("A1 X too small: %v", a1)
	}

	// L0 should be in XY plane (Z ≈ 0)
	l0 := coords[p.nodeIndex["L0"]]
	if math.Abs(l0[2]) > 1e-6 {
		t.Errorf("L0 not in XY plane: %v", l0)
	}

	// L1 should have positive Z (positive_z_node)
	l1 := coords[p.nodeIndex["L1"]]
	if l1[2] < -1e-6 {
		t.Errorf("L1 should be on +Z side: %v", l1)
	}
}

func TestSolve_DuplicateNode(t *testing.T) {
	input := `{"type":"node","id":"A0","kind":"anchor","anchor_id":0}
{"type":"node","id":"A0","kind":"anchor","anchor_id":1}
{"type":"node","id":"L0","kind":"latent"}
{"type":"node","id":"L1","kind":"latent"}
{"type":"edge","a":"A0","b":"L0","distance":3}
{"type":"edge","a":"A0","b":"L1","distance":3}
{"type":"edge","a":"L0","b":"L1","distance":4}
`
	_, err := ReadProblem(strings.NewReader(input))
	if err == nil {
		t.Fatal("expected duplicate node error")
	}
	if !strings.Contains(err.Error(), "duplicate node") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestSolve_UnknownType(t *testing.T) {
	input := `{"type":"node","id":"A0","kind":"anchor","anchor_id":0}
{"type":"node","id":"A1","kind":"anchor","anchor_id":1}
{"type":"node","id":"L0","kind":"latent"}
{"type":"node","id":"L1","kind":"latent"}
{"type":"bogus","foo":"bar"}
{"type":"edge","a":"A0","b":"A1","distance":4}
`
	_, err := ReadProblem(strings.NewReader(input))
	if err == nil {
		t.Fatal("expected unknown type error")
	}
	if !strings.Contains(err.Error(), "unknown record type") {
		t.Errorf("unexpected error: %v", err)
	}
}
