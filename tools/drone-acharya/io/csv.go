package io

import (
	"encoding/csv"
	"fmt"
	"io"
	"strconv"
	"strings"
)

// Format is CSV or TSV.
type Format string

const (
	FormatCSV Format = "csv"
	FormatTSV Format = "tsv"
)

// Distances holds upper-triangle pairwise distances: key (i,j) with i < j, value in meters.
type Distances map[[2]int]float64

// ReadDistances parses a CSV or TSV file. Returns N and distance map.
// Expects header ",N(n-1),...,N1" (columns reverse order) and data rows with variable length:
// row i has label Ni then distances to N(n-1), N(n-2), ..., N(i+1). Missing cell returns error.
func ReadDistances(r io.Reader, format Format) (n int, dist Distances, err error) {
	dist = make(Distances)
	var sep rune
	if format == FormatTSV {
		sep = '\t'
	} else {
		sep = ','
	}
	cr := csv.NewReader(r)
	cr.Comma = sep
	cr.FieldsPerRecord = -1
	rows, err := cr.ReadAll()
	if err != nil {
		return 0, nil, err
	}
	if len(rows) < 2 {
		return 0, nil, fmt.Errorf("need header and at least one data row")
	}
	header := rows[0]
	n = len(header)
	if n < 4 {
		return 0, nil, fmt.Errorf("need at least 4 nodes for 3D trilateration")
	}
	if len(rows) < n+1 {
		return 0, nil, fmt.Errorf("need %d data rows (one per node), got %d", n, len(rows)-1)
	}
	for rowIdx := 1; rowIdx <= n; rowIdx++ {
		row := rows[rowIdx]
		i := rowIdx - 1
		expectedCols := n - i // label + (n-1-i) data columns
		if len(row) < expectedCols {
			return 0, nil, fmt.Errorf("row %d: missing columns (expected %d)", rowIdx+1, expectedCols)
		}
		for k := 1; k <= n-1-i; k++ {
			j := n - k // column k is for node j
			cell := strings.TrimSpace(row[k])
			if cell == "" {
				return 0, nil, fmt.Errorf("missing distance for pair N%d-N%d", i, j)
			}
			v, err := strconv.ParseFloat(cell, 64)
			if err != nil {
				return 0, nil, fmt.Errorf("invalid distance for pair N%d-N%d: %w", i, j, err)
			}
			dist[[2]int{i, j}] = v
		}
	}
	expectedPairs := n * (n - 1) / 2
	if len(dist) != expectedPairs {
		for i := 0; i < n; i++ {
			for j := i + 1; j < n; j++ {
				if _, ok := dist[[2]int{i, j}]; !ok {
					return 0, nil, fmt.Errorf("missing distance for pair N%d-N%d", i, j)
				}
			}
		}
	}
	return n, dist, nil
}

// WriteTemplate writes the measurement template (upper triangle, columns reverse N(n-1)..N1).
// Row i has label Ni then empty cells for distances to N(n-1), N(n-2), ..., N(i+1) — easier to enter.
func WriteTemplate(w io.Writer, n int, format Format) error {
	if n < 4 || n > 8 {
		return fmt.Errorf("nodes must be 4-8, got %d", n)
	}
	var sep rune
	if format == FormatTSV {
		sep = '\t'
	} else {
		sep = ','
	}
	cw := csv.NewWriter(w)
	cw.Comma = sep
	header := make([]string, n)
	header[0] = "from/to"
	for k := 1; k < n; k++ {
		header[k] = fmt.Sprintf("N%d", n-k) // N(n-1), N(n-2), ..., N1
	}
	if err := cw.Write(header); err != nil {
		return err
	}
	for i := 0; i < n; i++ {
		numDataCols := n - 1 - i
		row := make([]string, 1+numDataCols)
		row[0] = fmt.Sprintf("N%d", i)
		for k := 1; k <= numDataCols; k++ {
			row[k] = ""
		}
		if err := cw.Write(row); err != nil {
			return err
		}
	}
	cw.Flush()
	return cw.Error()
}
