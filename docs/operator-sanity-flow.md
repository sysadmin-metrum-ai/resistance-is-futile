# Operator Sanity Flow

This is the intended human verification order before live manual testing or a demo run:

1. `scripts/check-anchor-geometry.py`
   - Static check that the anchor layout has enough 3D spread.
2. `test-health.py`
   - Fleet hardware check: self-test, battery, optional motor spin.
3. `scripts/lps-preflight.py`
   - LPS go/no-go: expected anchors, deck detection, estimator mode, stationary spread/drift.
4. `test-hover.py`
   - Single-drone litmus test before any higher-risk mission work.
5. `test-hover-multidrone.py`
   - Optional multidrone smoke test after single-drone hover is stable.

The preferred wrapper is:

```bash
scripts/sanity-check.sh --anchors scripts/anchors.py --uri radio://0/80/2M
```

Useful flags:

```bash
# Include motor spin and multidrone smoke test
scripts/sanity-check.sh --motors --multi

# Skip hover if you only want infrastructure checks
scripts/sanity-check.sh --skip-hover

# Override the health-stage URI when checking a specific drone
scripts/sanity-check.sh --health-uri radio://0/90/2M
```

Interpretation:

- Any stage returning nonzero is a `NO-GO`.
- `test-hover.py` is the final single-drone approval gate.
- `test-hover-multidrone.py` should only be run after a clean single-drone hover.
- The same thresholds should eventually be consumed by the API mission gate so human testing and backend launches do not drift apart.
