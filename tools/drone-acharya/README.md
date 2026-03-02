# drone-acharya — Crazyflie Loco Positioning Node Coordinate Calculator

## Overview
CLI tool that computes 3D coordinates for Loco positioning nodes from pairwise distance measurements using trilateration.

**What it does:** Given pairwise distance measurements between your LPS anchor nodes, it computes 3D coordinates using trilateration — no more manual geometry calculations.

**Why this matters:** When we move from Austin → Las Vegas → convention center, we need a dead simple way to recalibrate our positioning nodes. Measure distances between nodes, plug in, get coordinates. Done.

## How to use
1. **Enter data** — Use the template (CSV/TSV) in Google Sheets or Excel: fill in measured distances (meters) in the cells.
2. **Paste into input** — Save or copy the filled table into a file (e.g. `distances.csv`) and run `drone-acharya solve distances.csv`.
3. **Note the coordinates** — Output is a table (or `--crazyflie` / `--json`). Use these coordinates to configure your Loco Positioning System anchors.

## Installation
```bash
go install github.com/sysadmin-metrum-ai/resistance-is-futile/tools/drone-acharya@latest
```

Or build from source:
```bash
cd tools/drone-acharya
go install .
```

## Usage

### Step 1: Generate measurement template
```bash
drone-acharya template --nodes 6 --format csv -o distances.csv
drone-acharya template -n 8 -f tsv -o distances.tsv
```

Output (`distances.csv` for N=4). Top-left header "from/to"; columns in reverse order (N3, N2, N1) so each row has only the cells you need — easier to enter:
```csv
from/to,N3,N2,N1
N0,,,
N1,,
N2,
N3
```

Row i = node Ni; columns = distances to N(n-1), …, N(i+1). Fill in measured distances (meters):
```csv
from/to,N3,N2,N1
N0,3.000,5.000,4.000
N1,5.000,3.000
N2,4.000
N3
```

### Step 2: Compute coordinates
```bash
drone-acharya solve distances.csv
drone-acharya solve distances.csv -o coords.csv
drone-acharya solve distances.csv --crazyflie    # output crazyflie-lib-python config
drone-acharya solve distances.csv --json         # structured output
```

## Flags

| Flag | Short | Default | Description |
|---|---|---|---|
| `--nodes` | `-n` | 4 | Number of nodes (4-8) for `template` |
| `--format` | `-f` | `csv` | `csv` or `tsv` |
| `--output` | `-o` | stdout | Output file path |
| `--crazyflie` | `-c` | false | Emit Python anchor dict |
| `--json` | `-j` | false | JSON output |
| `--validate` | `-v` | false | Show validation (recomputed vs measured distances + error) |
| `--precision` | `-p` | 3 | Decimal places |
| `--rotate-ned` | | 0 | Clockwise rotation (degrees) from X-axis to North |
| `--offset-x` | | 0 | X translation (meters) |
| `--offset-y` | | 0 | Y translation (meters) |
| `--offset-z` | | 0 | Z translation (meters) |
| `--z-down` | | false | Flip Z-axis (+Z up → +Z down for NED) |

## Algorithm

### Coordinate Assignment (closed-form trilateration)

```
N0 = (0, 0, 0)                                          # origin
N1 = (d01, 0, 0)                                        # x-axis
N2:
  x2 = (d01² + d02² - d12²) / (2·d01)                  # xy-plane
  y2 = √(d02² - x2²)
  z2 = 0

N3..N7:
  xi = (di0² + d01² - di1²) / (2·d01)
  yi = (di0² - di2² - 2·xi·x2 + x2² + y2²) / (2·y2)
  zi = √(di0² - xi² - yi²)                             # positive root assumed (nodes above ground)
```

### Validation
For every pair (i,j), recompute euclidean distance from solved coords and report:
- absolute error: |measured - computed|
- relative error: |measured - computed| / measured × 100%

### Error Handling

| Condition | Behavior |
|---|---|
| Negative value under √ | Warn: inconsistent measurements. Clamp to 0, flag pair. |
| y2 ≈ 0 (N0, N1, N2 collinear) | Fatal: "Nodes 0,1,2 are collinear — pick non-collinear N2" |
| Missing cell in CSV | Fatal: "Missing distance for pair Ni-Nj" |
| N < 4 | Fatal: "Need at least 4 nodes for 3D trilateration" |
| Validation error > 5% | Warn: "Large error on pair Ni-Nj — re-measure?" |

### When measurements are inaccurate

The solver can **fail** or **degrade** in these cases:

| Cause | What happens |
|-------|----------------|
| **N0–N1 distance zero or tiny** | Division by (2·d01); solver can blow up or divide-by-zero. Ensure N0 and N1 are distinct and well separated. |
| **N0, N1, N2 nearly collinear** | y2 = √(d02² − x2²) becomes ≈ 0; **fatal** "nodes 0, 1, 2 are collinear". Pick N2 so the first three nodes form a real triangle. |
| **Negative under √ (N2)** | y2² &lt; 0 from d01, d02, d12 inconsistent (e.g. triangle inequality violated). Solver **warns** and clamps to 0 → N2 forced onto x-axis (degenerate). |
| **Negative under √ (N3..N7)** | z² &lt; 0 for that node; **warn** and clamp → node forced into xy-plane. Geometry is wrong. |
| **Errors in d01, d02, d12** | All later nodes (N3…) are computed from distances to 0,1,2; errors **propagate**. Prioritise accurate N0–N1–N2 measurements. |

Always run with `--validate` and check warnings; re-measure pairs with large error before trusting coordinates.

## Output Formats

### Default (table)
```
Node    X       Y       Z
N0      0.000   0.000   0.000
N1      4.000   0.000   0.000
N2      4.000   3.000   0.000
N3      0.000   3.000   0.000
```

### `--crazyflie`
```python
anchor_positions = {
    0: (0.00, 0.00, 0.00),
    1: (4.00, 0.00, 0.00),
    2: (4.00, 3.00, 0.00),
    3: (0.00, 3.00, 0.00),
}
```

### `--json`
```json
{
  "nodes": [
    {"id": 0, "x": 0.000, "y": 0.000, "z": 0.000},
    {"id": 1, "x": 4.000, "y": 0.000, "z": 0.000}
  ],
  "validation": [
    {"pair": "N0-N1", "measured": 4.000, "computed": 4.000, "error_m": 0.000, "error_pct": 0.0}
  ],
  "warnings": []
}
```

### `--validate`
```
Pair    Measured  Computed  Error(m)  Error(%)
N0-N1   4.000     4.000     0.000     0.0
N0-N2   5.000     5.000     0.000     0.0
...
Max error: 0.012m (0.3%) on N2-N5
```

## Project Structure
```
drone-acharya/
├── main.go
├── cmd/
│   ├── template.go       # template subcommand
│   └── solve.go          # solve subcommand
├── trilat/
│   └── trilat.go         # trilateration math
├── io/
│   ├── csv.go            # CSV/TSV parse + write
│   ├── format.go         # output formatters (table, json, crazyflie)
│   └── transform.go      # coordinate transformations (rotation, translation, Z-flip)
├── COORDINATES.md        # coordinate system documentation
└── go.mod
```

## Dependencies
- `github.com/spf13/cobra` — CLI framework
- stdlib only for math/IO
