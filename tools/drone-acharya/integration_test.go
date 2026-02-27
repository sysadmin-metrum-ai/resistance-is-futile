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
