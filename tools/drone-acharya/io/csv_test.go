package io

import (
	"bytes"
	"strings"
	"testing"
)

func TestReadDistances_ValidCSV(t *testing.T) {
	// Columns reverse order: from/to, N3, N2, N1; row i has distances to N3..N(i+1)
	csv := `from/to,N3,N2,N1
N0,3.000,5.000,4.000
N1,5.000,3.000
N2,4.000
N3
`
	n, dist, err := ReadDistances(strings.NewReader(csv), FormatCSV)
	if err != nil {
		t.Fatal(err)
	}
	if n != 4 {
		t.Errorf("n want 4 got %d", n)
	}
	if len(dist) != 6 {
		t.Errorf("want 6 pairs got %d", len(dist))
	}
	if dist[[2]int{0, 1}] != 4.0 || dist[[2]int{2, 3}] != 4.0 {
		t.Errorf("distances wrong: d01=%f d23=%f", dist[[2]int{0, 1}], dist[[2]int{2, 3}])
	}
}

func TestReadDistances_MissingCell(t *testing.T) {
	csv := `from/to,N3,N2,N1
N0,3.000,5.000,4.000
N1,,3.000
N2,4.000
N3
`
	_, _, err := ReadDistances(strings.NewReader(csv), FormatCSV)
	if err == nil {
		t.Fatal("expected missing distance error")
	}
	if !strings.Contains(err.Error(), "missing distance") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestReadDistances_TooFewNodes(t *testing.T) {
	csv := `from/to,N2,N1
N0,2,1
N1,3
N2
`
	_, _, err := ReadDistances(strings.NewReader(csv), FormatCSV)
	if err == nil {
		t.Fatal("expected error")
	}
	if !strings.Contains(err.Error(), "at least 4 nodes") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestWriteTemplate(t *testing.T) {
	var buf bytes.Buffer
	err := WriteTemplate(&buf, 4, FormatCSV)
	if err != nil {
		t.Fatal(err)
	}
	s := buf.String()
	if !strings.Contains(s, "from/to,N3,N2,N1") {
		t.Errorf("missing reverse header: %s", s)
	}
	if !strings.Contains(s, "N0,,,") {
		t.Errorf("missing N0 row: %s", s)
	}
	lines := strings.Split(strings.TrimSpace(s), "\n")
	if len(lines) != 5 {
		t.Errorf("want 5 lines (header+4 rows) got %d", len(lines))
	}
	// Round-trip: written template filled with values should parse
	filled := `from/to,N3,N2,N1
N0,1,2,3
N1,4,5
N2,6
N3
`
	n, dist, err := ReadDistances(strings.NewReader(filled), FormatCSV)
	if err != nil {
		t.Fatal(err)
	}
	if n != 4 || len(dist) != 6 {
		t.Errorf("round-trip n=4 len(dist)=6 got n=%d len=%d", n, len(dist))
	}
}

func TestWriteTemplate_InvalidN(t *testing.T) {
	var buf bytes.Buffer
	err := WriteTemplate(&buf, 3, FormatCSV)
	if err == nil {
		t.Fatal("expected error for n=3")
	}
}
