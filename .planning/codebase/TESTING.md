# Testing Patterns

**Analysis Date:** 2026-02-27

## Test Framework

### Go Testing

**Runner:**
- Go standard library: `testing` package
- Version: Go 1.25

**Run Commands:**
```bash
go test ./...                    # Run all tests
go test -v ./trilat/             # Verbose for specific package
go test -cover ./io/             # With coverage
```

**Test Files:**
- Located in same package as implementation
- Named: `*_test.go`
- Package declaration matches: `package trilat` (not `package trilat_test`)

### Python Testing

**Framework:** Not detected
- No pytest, unittest, or test runner config
- `test-hover.py` is a script, not a test suite
- Uses manual execution with `time.sleep()` for timing

---

## Go Test File Organization

### Location Pattern
```
tools/drone-acharya/
├── trilat/
│   ├── trilat.go
│   └── trilat_test.go       # Co-located with implementation
├── io/
│   ├── csv.go
│   ├── csv_test.go
│   └── format.go
└── integration_test.go      # Root-level integration test
```

### Naming
- Unit tests: `[module]_test.go`
- Integration tests: `integration_test.go`

---

## Go Test Structure

### Suite Organization

**Test Function Pattern:**
```go
func TestSolve_4NodesSquare(t *testing.T) {
    // Arrange
    dist := map[[2]int]float64{
        {0, 1}: 4, {0, 2}: 5, {0, 3}: 3,
        {1, 2}: 3, {1, 3}: 5,
        {2, 3}: 4,
    }

    // Act
    res, err := Solve(4, dist)

    // Assert
    if err != nil {
        t.Fatal(err)
    }
    coords := res.Coords
    eps := 1e-6
    if math.Abs(coords[0].X) > eps || math.Abs(coords[0].Y) > eps {
        t.Errorf("N0 want (0,0,0) got (%f,%f,%f)", coords[0].X, coords[0].Y, coords[0].Z)
    }
}
```

**Naming Convention:**
- `Test[Function]_[Scenario]` - describes what's being tested
- Examples: `TestSolve_4NodesSquare`, `TestSolve_NLessThan4`, `TestValidate`

### Assertions

**Error Testing:**
```go
// Check error returned
if err == nil {
    t.Fatal("expected error for N<4")
}

// Check error message
if err.Error() != "need at least 4 nodes for 3D trilateration" {
    t.Errorf("unexpected error: %v", err)
}
```

**Value Testing:**
```go
// Numeric comparison with epsilon
eps := 1e-6
if math.Abs(coords[0].X) > eps {
    t.Errorf("N0 want (0,0,0) got (%f,%f,%f)", coords[0].X, coords[0].Y, coords[0].Z)
}
```

**Slice/Collection Testing:**
```go
if len(rows) != 6 {
    t.Errorf("want 6 validation rows, got %d", len(rows))
}
for _, r := range rows {
    if r.ErrorM > 1e-6 {
        t.Errorf("pair %s: unexpected error %f", r.Pair, r.ErrorM)
    }
}
```

---

## Mocking

### Go Mocking Approach

**No Mock Framework Detected:**
- Tests use real implementations
- Simple data structures passed directly

**Test Data Creation:**
```go
dist := map[[2]int]float64{
    {0, 1}: 4, {0, 2}: 5, {0, 3}: 3,
    {1, 2}: 3, {1, 3}: 5,
    {2, 3}: 4,
}
```

**Reader Mocks:**
```go
// Use strings.NewReader for CSV input
n, dist, err := ReadDistances(strings.NewReader(csv), FormatCSV)
```

---

## Fixtures and Test Data

### Inline Test Data

**Hardcoded Fixtures:**
```go
csv := `from/to,N3,N2,N1
N0,3.000,5.000,4.000
N1,5.000,3.000
N2,4.000
N3
`
```

**Location:** Embedded directly in test functions

---

## Coverage

**View Coverage:**
```bash
go test -cover ./...
go test -coverprofile=coverage.out ./...
go tool cover -html=coverage.out
```

**Coverage Target:** Not enforced - no CI gate

---

## Test Types

### Unit Tests

**Scope:** Individual functions
- `trilat/trilat_test.go` - tests `Solve()` and `Validate()`
- `io/csv_test.go` - tests `ReadDistances()` and `WriteTemplate()`

**Characteristics:**
- Fast execution
- No external dependencies
- Deterministic data

### Integration Tests

**Location:** `tools/drone-acharya/integration_test.go`

**Pattern:**
```go
// Integration: template output is valid; filled CSV round-trips through solve.
func TestTemplateSolveRoundTrip(t *testing.T) {
    // Test full workflow: template -> fill -> solve -> validate
}
```

**Characteristics:**
- Tests across package boundaries
- Uses io and trilat packages together
- End-to-end validation

---

## Error Testing Patterns

### Error Message Validation
```go
if err.Error() != "expected error message" {
    t.Errorf("unexpected error: %v", err)
}
```

### Error Type Checking
```go
if !strings.Contains(err.Error(), "at least 4 nodes") {
    t.Errorf("unexpected error: %v", err)
}
```

---

## Async/IO Testing

### Go - Reader/Writer
```go
// Test WriteTemplate
var buf bytes.Buffer
err := WriteTemplate(&buf, 4, FormatCSV)
if err != nil {
    t.Fatal(err)
}
s := buf.String()
```

### Python - Timing
```python
# Manual sleep-based timing
time.sleep(0.5)
time.sleep(3)
time.sleep(5)
```

---

## Test Execution Notes

**Run All Tests:**
```bash
cd tools/drone-acharya
go test ./...
```

**Run Specific Package:**
```bash
go test ./trilat -v
go test ./io -v
```

**Integration Only:**
```bash
go test -v -run TestTemplateSolveRoundTrip .
```

---

*Testing analysis: 2026-02-27*
