# Architecture

**Analysis Date:** 2026-02-27

## Pattern Overview

**Overall:** CLI Tool with Layered Architecture

This is a focused CLI application that computes 3D coordinates for Crazyflie Loco Positioning System (LPS) anchor nodes from pairwise distance measurements.

**Key Characteristics:**
- Command-line interface using Cobra framework
- Clear separation between CLI (cmd/), business logic (trilat/), and I/O (io/)
- Stateless computation: input distances -> trilateration -> output coordinates
- Multiple output formats (table, JSON, Python dict)

## Layers

**CLI Layer:**
- Purpose: Parse command-line arguments and orchestrate execution
- Location: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/main.go`, `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/cmd/`
- Contains: Root command, template subcommand, solve subcommand
- Depends on: cmd, io, trilat packages
- Used by: End users via CLI

**I/O Layer:**
- Purpose: Handle all input/output operations
- Location: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/io/`
- Contains: CSV/TSV parsing, output formatters (table, JSON, crazyflie)
- Depends on: Standard library only
- Used by: cmd layer

**Core Algorithm Layer:**
- Purpose: Trilateration mathematics
- Location: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/trilat/trilat.go`
- Contains: Solve() function, Validate() function, Coord type
- Depends on: math package (stdlib)
- Used by: cmd layer

## Data Flow

**Main Flow (solve command):**

1. CLI parses arguments (input file, output flags)
2. I/O layer reads CSV/TSV distance matrix
3. Core layer computes 3D coordinates via closed-form trilateration
4. Optional: Core layer validates results against input distances
5. I/O layer formats and outputs results

**Template Generation Flow:**

1. CLI parses arguments (node count, format, output)
2. I/O layer generates empty upper-triangle template
3. Output written to file or stdout

## Key Abstractions

**Distance Matrix:**
- Purpose: Represent pairwise distances between anchor nodes
- Type: `map[[2]int]float64` (key is {i,j} with i<j)
- Pattern: Dictionary keyed by node pairs

**Coord:**
- Purpose: Represent 3D position in meters
- Type: `struct { X, Y, Z float64 }`
- Pattern: Simple struct

**Result:**
- Purpose: Return computed coordinates along with warnings
- Type: `struct { Coords []Coord; Warnings []string }`
- Pattern: Result object with data + metadata

## Entry Points

**Go CLI:**
- Location: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/main.go`
- Triggers: User runs `drone-acharya` command
- Responsibilities: Register subcommands, execute root command

**Python Flight Script:**
- Location: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/test-hover.py`
- Triggers: User runs `python test-hover.py`
- Responsibilities: Connect to Crazyflie via radio, wait for position estimate, execute hover maneuver

## Error Handling

**Strategy:** Fail fast with descriptive error messages

**Patterns:**
- Validation at input boundaries (node count 4-8, valid CSV format)
- Mathematical error detection (collinear nodes, negative square root)
- Warnings for degraded results (inconsistent measurements clamped)
- Error propagation via Go's error return values

## Cross-Cutting Concerns

**Validation:** Implemented in trilat package, validates computed coordinates against input distances

**Error Messages:** Descriptive, include node indices and actual values

---

*Architecture analysis: 2026-02-27*
