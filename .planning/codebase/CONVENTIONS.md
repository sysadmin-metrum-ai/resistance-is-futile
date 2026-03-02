# Coding Conventions

**Analysis Date:** 2026-02-27

## Language Overview

This codebase contains two primary language ecosystems:

- **Go 1.25** - Main application code in `tools/drone-acharya/`
- **Python** - Drone control script at root: `test-hover.py`

---

## Go Conventions

### Naming Patterns

**Files:**
- lowercase with underscores: `trilat.go`, `csv_test.go`, `solve.go`
- Test files: `*_test.go` suffix in same package

**Types:**
- PascalCase: `Coord`, `Result`, `Distances`, `ValidationRow`
- Struct tags use JSON: `json:"pair"`, `json:"x"`

**Functions/Variables:**
- camelCase: `solve`, `readDistances`, `writeTemplate`
- Constants: camelCase or PascalCase with grouping in `const` block
  ```go
  const (
      epsilon   = 1e-9
      largePct  = 5.0
  )
  ```

**Map Keys:**
- Composite keys use array syntax: `map[[2]int]float64`
- Key pairs stored as `{i, j}` with i < j convention

---

### Code Style

**Formatting:**
- No `.gofmt` or `gofumpt` config detected - using default Go formatting
- Indentation: tabs
- Line length: standard Go (no enforced max)

**Import Organization:**
1. Standard library packages first
2. External packages last
3. Grouped with blank line between
```go
import (
    "encoding/csv"
    "fmt"
    "os"
    "strings"

    "github.com/spf13/cobra"
    "github.com/sysadmin-metrum-ai/resistance-is-futile/tools/drone-acharya/io"
)
```

**Package Structure:**
- Each directory is a package: `trilat/`, `io/`, `cmd/`
- Package name matches directory: `package trilat`, `package io`, `package cmd`
- No internal/vendor directories

---

### Error Handling

**Pattern:**
- Return `error` as last return value
- Use `fmt.Errorf` with descriptive messages
- Early returns on error
```go
func Solve(n int, dist map[[2]int]float64) (*Result, error) {
    if n < 4 {
        return nil, fmt.Errorf("need at least 4 nodes for 3D trilateration")
    }
    // ... proceed
}
```

**Error Messages:**
- Specific and actionable: "distance N0–N1 too small or zero"
- Include context: "nodes 0, 1, 2 are collinear — pick non-collinear N2"

---

### Function Design

**Parameters:**
- Group related parameters into structs when > 3
- Use named return values for documentation: `func Validate(...) (rows []ValidationRow, outWarnings []string)`
- Pass maps by reference (built-in)

**Return Values:**
- Return pointer for structs that may be nil: `(*Result, error)`
- Multiple returns for errors: `(value, error)`

**Size:**
- Functions typically 30-80 lines
- Complex logic separated: `Solve()` computes, `Validate()` checks

---

### Documentation

**Comments:**
- Exported functions have doc comments: `// Solve computes 3D coordinates...`
- Unexported functions often lack comments
- Inline comments for non-obvious logic:
```go
// Columns reverse order: from/to, N3, N2, N1; row i has distances to N3..N(i+1)
```

---

## Python Conventions

### Naming Patterns

**Files:**
- lowercase with underscores: `test-hover.py`

**Functions:**
- snake_case: `wait_for_position_estimator`, `log_callback`

**Variables:**
- snake_case: `var_history`, `stable`, `var_x`

---

### Code Style

**Formatting:**
- 4-space indentation (PEP 8 default)
- No formatter config detected

**Imports:**
- Standard library first, then external
```python
import time
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie
```

---

### Error Handling

**Pattern:**
- Try/except blocks for runtime errors
- KeyboardInterrupt handling for user cancellation

---

## Cross-Cutting Concerns

### Logging

**Go:**
- Uses `fmt.Fprintln(os.Stderr, "Warn:", w)` for warnings
- No structured logging library

**Python:**
- Uses `print()` for status output

---

### Validation

**Go:**
- Input validation at function entry
- Returns descriptive errors
- ValidationRow struct for structured results

---

## Where to Add New Code

**Go - New Feature:**
- Implementation: `tools/drone-acharya/[module]/`
- Tests: `tools/drone-acharya/[module]/*_test.go`
- CLI command: `tools/drone-acharya/cmd/`

**Python - New Script:**
- Location: Root or `tools/` subdirectory
- Follow snake_case naming

---

*Convention analysis: 2026-02-27*
