# Venue Survey Procedure

This document describes the step-by-step procedure for measuring and configuring Loco Positioning (LPS) anchor nodes for the Crazyflie drone swarm positioning system.

## Overview

When deploying the drone swarm at a new venue (e.g., moving from Austin to Las Vegas to a convention center), the Loco Positioning nodes must be recalibrated. This procedure provides a systematic approach to:

1. Measure pairwise distances between anchor nodes
2. Generate coordinates using drone-acharya
3. Program anchors with their positions
4. Verify positioning accuracy

## Equipment Needed

| Item | Purpose | Notes |
|------|---------|-------|
| Laser distance meter | Measure distances between anchors | Accuracy: +/- 2mm preferred |
| Crazyradio (USB dongle) | Radio communication with anchors | 2.4 GHz, ~100m range |
| Loco Positioning nodes (4-8) | UWB anchors for positioning | Recommend 6+ for redundancy |
| Laptop/Workstation | Running drone-acharya and scripts | USB port for Crazyradio |
| Measuring tape (backup) | Verify laser measurements | Backup for validation |

## Anchor Placement Guidelines

### Minimum Requirements

- **Minimum anchors:** 4 nodes (theoretical minimum for 3D positioning)
- **Recommended anchors:** 6+ nodes (provides redundancy and better coverage)

### Spatial Configuration

1. **Avoid collinearity:** Do not place anchors in a straight line. The first three anchors (N0, N1, N2) must form a triangle in 3D space.

2. **3D Volume:** Distribute anchors in 3D space, not just on a single plane:
   - Place some anchors at different heights (e.g., on tables, shelves, or mounted at varying heights)
   - This improves Z-axis accuracy significantly

3. **Coverage Area:** Anchors should encompass the entire flight volume with margin:
   - For a 5m x 5m x 3m flight area, place anchors at corners extending beyond the volume
   - Larger areas need more anchors for reliable coverage

4. **Recommended Layout (6 anchors):**
   ```
   Top View (bird's eye):

       N3 -------- N2
      /|          /|
     / |         / |
    N0 -------- N1 |
    |  |        |  |
    |  N4 -------|--N5
    | /         | /
    |/          |/
    N0 -------- N1

   Side View (elevation):
   N2,N3 at height ~2.5m (top corners)
   N0,N1,N4,N5 at height ~0.5m (floor/low)
   ```

5. **Avoid Interference Sources:**
   - Keep anchors away from large metal objects (>50cm)
   - Avoid concrete with rebar reinforcement directly between anchors
   - Minimize people walking between anchors during measurement

## Step-by-Step Measurement Workflow

### Step 1: Position Anchors

1. Place all anchors in their intended positions
2. Ensure each anchor has a clear line of sight to at least 3-4 other anchors
3. Record the anchor IDs (usually printed on the device)

### Step 2: Generate Measurement Template

Use drone-acharya to generate a measurement template:

```bash
# For 6 anchors
drone-acharya template --nodes 6 --format csv -o distances.csv

# For 8 anchors
drone-acharya template --nodes 8 --format tsv -o distances.tsv
```

The template will look like this (example for 4 nodes):
```csv
from/to,N3,N2,N1
N0,,,
N1,,
N2,
N3
```

### Step 3: Measure Distances

For each empty cell in the template, measure the distance between the corresponding anchor pair:

1. Hold the laser distance meter against one anchor
2. Aim at the other anchor's center
3. Record the distance in meters (drone-acharya expects meters)

**Important:** Measure all pairwise distances. For N nodes, you need N*(N-1)/2 measurements.

Example filled template (4 nodes):
```csv
from/to,N3,N2,N1
N0,3.000,5.000,4.000
N1,5.000,3.000
N2,4.000
N3
```

### Step 4: Compute Anchor Coordinates

Run drone-acharya solve to compute 3D coordinates. For Crazyflie/LPS, coordinates must be in **NED** (North-East-Down):

```bash
# Basic output
drone-acharya solve distances.csv

# With validation (recommended)
drone-acharya solve distances.csv --validate

# Output for Crazyflie/LPS (NED; recommended for push-anchors)
drone-acharya solve distances.csv --crazyflie --z-down --validate

# If the venue is not aligned with the survey frame, add --rotate-ned and/or --offset-x/y/z
# See tools/drone-acharya/COORDINATES.md for frame and transformation options.

# JSON output (for programmatic use)
drone-acharya solve distances.csv --json
```

Example output:
```
Node    X       Y       Z
N0      0.000   0.000   0.000
N1      4.000   0.000   0.000
N2      4.000   3.000   0.000
N3      0.000   3.000   0.000
```

### Step 5: Validate Measurements

Always run with `--validate` to check measurement accuracy:

```
Pair    Measured  Computed  Error(m)  Error(%)
N0-N1   4.000     4.000     0.000     0.0
N0-N2   5.000     5.001     0.001     0.02
...
Max error: 0.015m (0.5%) on N2-N5
```

**Acceptable error:** < 5% error is acceptable. If any pair shows >5% error:
- Re-measure that specific distance
- Check for measurement errors (wrong anchor, obstacles)
- Verify the anchors are in the expected positions

### Step 6: Push Coordinates to Anchors

Use the push-anchors.py script to program the anchors:

```bash
python scripts/push-anchors.py --anchors anchors.py --radio 0/80/2M
```

See `scripts/push-anchors.py --help` for full usage options.

### Step 7: Verify Positioning

Run a test flight to verify positioning accuracy:

```bash
python scripts/verify-position.py --pattern square --size 1.0 --threshold 0.2
```

This will report RMS error. Default threshold is 20cm (0.2m).

## Tips for Accurate Measurements

1. **Use meters:** All measurements must be in meters. Convert from feet if necessary (1 ft = 0.3048 m).

2. **Measure twice:** For critical measurements, measure each distance twice. If they differ by >2cm, measure a third time.

3. **Measure center-to-center:** Measure from the center of one anchor to the center of another, not the edge.

4. **Stable positions:** Ensure anchors are in their final positions before measuring. Moving an anchor requires re-measurement.

5. **Height matters:** Record the Z-coordinate (height) accurately. Use a measuring tape for vertical distances.

6. **Keep records:** Save the original measurement files (distances.csv) for future reference.

## Troubleshooting

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "nodes 0, 1, 2 are collinear" | First three anchors in a straight line | Reposition N2 to form a triangle with N0 and N1 |
| "distance N0-N1 too small" | Anchors N0 and N1 are too close | Move anchors apart (>50cm apart recommended) |
| "inconsistent measurements" | Triangle inequality violated | Re-check measurements; ensure distances are physically possible |
| Large validation error (>5%) | Measurement error | Re-measure the problematic pairs |

### Positioning Accuracy Issues

If post-deployment positioning is inaccurate:

1. **Check anchor coverage:** Ensure the drone can see at least 3-4 anchors at any point in the flight volume
2. **Verify anchor positions:** Re-run verification script; anchors may have moved
3. **Check for interference:** Metal objects or people may be blocking UWB signals
4. **Add more anchors:** Additional anchors improve geometry and redundancy

### Radio Connection Issues

If push-anchors.py fails to connect:

1. Verify Crazyradio is recognized: `lsusb` should show Crazyradio
2. Check radio address matches anchor configuration
3. Ensure anchors are powered on
4. Try reducing distance between Crazyradio and anchors

## References

- drone-acharya: `tools/drone-acharya/README.md`
- push-anchors.py: `scripts/push-anchors.py --help`
- verify-position.py: `scripts/verify-position.py --help`
- Loco Positioning documentation: https://www.bitcraze.io/documentation/system/positioning/

---

*Last updated: 2026-02-28*
