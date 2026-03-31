# Coordinate Systems and Transformations

This document describes how coordinates are calculated in drone-acharya and how they relate to Crazyflie's coordinate system.

## Current Coordinate Calculation

### Trilateration Algorithm

drone-acharya computes 3D coordinates from pairwise distance measurements using **multilateration** (specifically, sequential trilateration):

```
Algorithm: Solve(n, dist) -> Coord[]

1. Anchor N0 at origin:           N0 = (0, 0, 0)
2. Place N1 on x-axis:            N1 = (d01, 0, 0)
3. Place N2 in xy-plane:
   - x2 = (d01² + d02² - d12²) / (2·d01)
   - y2 = √(d02² - x2²)          (positive root: assumes N2 "above" the N0-N1 line)
   - N2 = (x2, y2, 0)
4. For each subsequent node i (i ≥ 3):
   - Solve intersection of 3 spheres centered at N0, N1, N2
   - xi = (di0² + d01² - di1²) / (2·d01)
   - yi = (di0² - di2² - 2·xi·x2 + x2² + y2²) / (2·y2)
   - zi = √(di0² - xi² - yi²)   (positive root: assumes nodes above ground)
   - Ni = (xi, yi, zi)
```

### Coordinate System (as computed)

The algorithm produces coordinates in a **right-handed Cartesian frame** where:
- **+X**: Along the N0→N1 axis
- **+Y**: Perpendicular to X, in the plane of the first three nodes
- **+Z**: Upward (positive = above ground)

This is an **arbitrary reference frame** — whatever you measure defines the orientation. The algorithm does not know "north", "ground", or "altitude" unless you also provide constraints that define those physically.

---

## Crazyflie's Coordinate System

### NED Frame (North-East-Down)

Crazyflie uses the **NED** coordinate convention, which is standard in aviation and robotics:

| Axis | Direction |
|------|-----------|
| **+X** | North (forward) |
| **+Y** | East (right) |
| **+Z** | Down (negative = up, altitude) |

This is a **right-handed** system (X × Y = Z).

### Body Frame vs World Frame

- **World (NED)**: Fixed to the venue/environment. N is geographic north (magnetic or true).
- **Body**: Fixed to the drone. X points forward (nose), Y points right, Z points down.

When Crazyflie reports position, it's in **world NED** coordinates. When you send setpoints, you can specify in either world or body frame.

### The +Z Problem

In NED:
- **+Z = down** (toward ground)
- Ground = positive Z
- Ceiling = negative Z

In the drone-acharya output:
- **+Z = up** (positive = above your measurement plane)
- This is **ENU** convention (East-North-Up) flipped, not NED!

---

## Frame Transformation: acharya → Crazyflie

To use drone-acharya coordinates with Crazyflie, you need a transformation.

### What Distances Cannot Tell You

Pure pairwise distances recover the anchor geometry, but not the venue's real-world orientation:

- They do not reveal which axis is gravity/up.
- They do not reveal which horizontal direction is north.
- They do not distinguish mirrored layouts unless you add an extra convention.

So if drift matters, the key is not just "measure carefully", but also "define the frame physically".

### Option 1: Survey-Frame Alignment (Recommended for deployment)

Use the graph solver with a `survey_frame` so the solution is tied to real space:

- `x_from` is the survey origin
- `x_to` defines the +X axis
- `plane_node` defines the physical ground/reference plane with `x_from` and `x_to`
- `positive_z_node` selects the physically upward side of that plane

This is the safest way to ensure the solved Z axis corresponds to actual vertical.

### Option 2: Coordinate Transformation

If you measured arbitrarily but know the transformation, apply a rotation/translation:

```
Crazyflie = R · acharya + T
```

Where:
- **R** = 3×3 rotation matrix (NED ← ENU-ish flip)
- **T** = translation vector (origin offset)

#### Simple Z-flip (if you used "Z up" convention)

```python
def to_crazyflie(coord):
    x_cf = coord.x
    y_cf = coord.y
    z_cf = -coord.z  # Flip: +Z up → +Z down
    return (x_cf, y_cf, z_cf)
```

#### Full NED Transform

```python
import numpy as np

def transform_to_ned(coords, rotation_deg=0, offset=(0, 0, 0)):
    """
    Transform acharya coords to Crazyflie NED.

    Args:
        coords: list of (x, y, z) tuples from acharya
        rotation_deg: clockwise rotation from acharya X-axis to North (degrees)
        offset: (dx, dy, dz) translation in meters
    """
    # Build rotation matrix (rotation around Z-axis, then flip Z)
    theta = np.radians(rotation_deg)
    R = np.array([
        [np.cos(theta), -np.sin(theta), 0],
        [np.sin(theta),  np.cos(theta), 0],
        [0,              0,             -1],  # Z flip: +Z up → +Z down
    ])

    result = []
    for x, y, z in coords:
        v = np.array([x, y, z])
        ned = R @ v + np.array(offset)
        result.append(tuple(ned))

    return result

# Example: rotate 45° clockwise (NE direction as X-axis), no offset
transformed = transform_to_ned(
    [(0, 0, 0), (4, 0, 0), (4, 3, 0), (0, 3, 0)],
    rotation_deg=45,
    offset=(0, 0, 0)
)
```

---

## Implemented: Built-in Frame Transformation

Transformation flags are now available:

```bash
# Output in Crazyflie NED, assuming acharya X-axis = North
drone-acharya solve distances.csv --crazyflie --rotate-ned 45

# Apply translation offset (e.g., if origin of survey != venue origin)
drone-acharya solve distances.csv --crazyflie --offset-x 10 --offset-y 5 --offset-z -2

# Flip Z-axis (+Z up → +Z down for NED)
drone-acharya solve distances.csv --crazyflie --z-down

# Combined: rotate to NED orientation, flip Z, apply offset
drone-acharya solve distances.csv --crazyflie --rotate-ned 45 --z-down --offset-z 1.5
```

### Available Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--rotate-ned degrees` | Clockwise rotation from X-axis to North | 0 |
| `--offset-x meters` | X translation | 0 |
| `--offset-y meters` | Y translation | 0 |
| `--offset-z meters` | Z translation | 0 |
| `--z-down` | Flip Z-axis (+Z up → +Z down for NED) | false (keep +Z up) |

---

## Summary

| Aspect | drone-acharya | Crazyflie |
|--------|---------------|-----------|
| Frame | Arbitrary Cartesian | NED (North-East-Down) |
| Z convention | +Z = up | +Z = down |
| Origin | First node (N0) | Configurable |
| Orientation | From measurement | Geographic (magnetic north) |

**Key insight**: Distance measurements determine shape, not gravity. To use with Crazyflie:
1. Prefer a survey-framed solve that explicitly defines the physical plane and upward side.
2. Then apply any remaining NED rotation/translation with `--rotate-ned`, `--offset-*`, and `--z-down`.

The current `--crazyflie` flag outputs raw coordinates with no transformation — it's your responsibility to ensure the solve is aligned to the venue frame or to apply the transform afterward.

**Recommendation:** When using the output with Crazyflie/LPS, always pass **`--z-down`** and prefer a solve whose plane/up orientation was explicitly defined rather than inferred from an arbitrary basis choice.
