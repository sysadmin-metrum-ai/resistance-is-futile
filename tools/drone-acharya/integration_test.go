package main

import (
	"bytes"
	"strings"
	"testing"

	"github.com/sysadmin-metrum-ai/resistance-is-futile/tools/drone-acharya/io"
	"github.com/sysadmin-metrum-ai/resistance-is-futile/tools/drone-acharya/trilat"
)

// Integration: template output is valid; filled CSV round-trips through solve.
func TestTemplateSolveRoundTrip(t *testing.T) {
	var buf bytes.Buffer
	if err := io.WriteTemplate(&buf, 4, io.FormatCSV); err != nil {
		t.Fatal(err)
	}
	// Fill with spec example distances (columns reverse: N3,N2,N1)
	filled := `from/to,N3,N2,N1
N0,3.000,5.000,4.000
N1,5.000,3.000
N2,4.000
N3
`
	n, dist, err := io.ReadDistances(strings.NewReader(filled), io.FormatCSV)
	if err != nil {
		t.Fatal(err)
	}
	if n != 4 || len(dist) != 6 {
		t.Fatalf("n=%d len(dist)=%d", n, len(dist))
	}
	res, err := trilat.Solve(n, dist)
	if err != nil {
		t.Fatal(err)
	}
	if len(res.Coords) != 4 {
		t.Fatalf("want 4 coords got %d", len(res.Coords))
	}
	// Expected: N0=(0,0,0), N1=(4,0,0), N2=(4,3,0), N3=(0,3,0)
	c := res.Coords[2]
	if c.X < 3.9 || c.X > 4.1 || c.Y < 2.9 || c.Y > 3.1 {
		t.Errorf("N2 coords: (%f,%f,%f)", c.X, c.Y, c.Z)
	}
	rows, _ := trilat.Validate(res.Coords, dist, nil)
	if len(rows) != 6 {
		t.Errorf("validation rows: %d", len(rows))
	}
	for _, r := range rows {
		if r.ErrorPct > 1e-6 {
			t.Errorf("pair %s error_pct %f", r.Pair, r.ErrorPct)
		}
	}
}

// Test 6-node configuration (recommended setup for LPS)
func TestSolve_6Nodes(t *testing.T) {
	// 6 nodes in a larger square (N0,N1,N2,N3 at corners, N4,N5 in middle)
	// Use distances that form a valid configuration
	// N0=(0,0,0), N1=(5,0,0), N2=(5,5,0), N3=(0,5,0), N4=(2.5,2.5,0), N5=(2.5,2.5,0)
	// Essentially a 5x5 square with center points - all at z=0
	dist := map[[2]int]float64{
		{0, 1}: 5.0, {0, 2}: 7.071, {0, 3}: 5.0, {0, 4}: 3.536, {0, 5}: 3.536,
		{1, 2}: 5.0, {1, 3}: 7.071, {1, 4}: 3.536, {1, 5}: 3.536,
		{2, 3}: 5.0, {2, 4}: 3.536, {2, 5}: 3.536,
		{3, 4}: 3.536, {3, 5}: 3.536,
		{4, 5}: 0.0, // Same position - should be handled gracefully
	}
	n, parsedDist, err := io.ReadDistances(strings.NewReader(`from/to,N5,N4,N3,N2,N1
N0,3.536,3.536,5.000,7.071,5.000
N1,3.536,3.536,7.071,5.000
N2,3.536,3.536,5.000
N3,3.536,3.536
N4,0.000
N5
`), io.FormatCSV)
	if err != nil {
		t.Fatal(err)
	}
	if n != 6 {
		t.Fatalf("want 6 nodes, got %d", n)
	}

	// Verify parsed distances match expected
	if len(parsedDist) != 15 {
		t.Fatalf("want 15 distance pairs, got %d", len(parsedDist))
	}

	// Solve and check we get 6 coordinates - don't crash
	res, err := trilat.Solve(n, dist)
	if err != nil {
		// Error is expected when N4 and N5 have distance 0
		t.Logf("Expected error for zero-distance nodes: %v", err)
		return
	}

	if len(res.Coords) != 6 {
		t.Fatalf("want 6 coords got %d", len(res.Coords))
	}

	// Validate distances
	rows, _ := trilat.Validate(res.Coords, dist, nil)
	if len(rows) != 15 {
		t.Errorf("want 15 validation rows, got %d", len(rows))
	}

	t.Logf("6-node solve completed with %d validation rows", len(rows))
}

// Test template generation for 6 nodes
func TestTemplate_6Nodes(t *testing.T) {
	var buf bytes.Buffer
	err := io.WriteTemplate(&buf, 6, io.FormatCSV)
	if err != nil {
		t.Fatal(err)
	}

	s := buf.String()
	// Should have header: from/to,N5,N4,N3,N2,N1
	if !strings.Contains(s, "from/to,N5,N4,N3,N2,N1") {
		t.Errorf("unexpected header: %s", s)
	}

	lines := strings.Split(strings.TrimSpace(s), "\n")
	if len(lines) != 7 { // header + 6 rows
		t.Errorf("want 7 lines (header+6 rows), got %d", len(lines))
	}
}
