# Codebase Concerns

**Analysis Date:** 2026-02-27

## Tech Debt

**Python Script Hardcoded Values:**
- Issue: URI `radio://0/80/2M` is hardcoded in `test-hover.py` line 9
- Files: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/test-hover.py`
- Impact: Changing radio channel/bandwidth requires code modification
- Fix approach: Accept URI as command-line argument or environment variable

**Relative Cache Path:**
- Issue: Cache path `./cache` is relative, may cause file conflicts or permission issues
- Files: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/test-hover.py` (line 52)
- Impact: Cache file created in current working directory, unpredictable location
- Fix approach: Use absolute path or platform-appropriate cache directory (e.g., `~/.cache/crazyflie`)

**Missing Input Validation:**
- Issue: No validation for negative or zero distances in Go trilateration
- Files: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/trilat/trilat.go`
- Impact: Invalid distance measurements may produce unexpected results or silent failures
- Fix approach: Add explicit validation in `Solve()` function

## Known Bugs

**Trilateration Collinearity Check:**
- Symptoms: Returns error only for nodes 0,1,2 collinear, but other collinear combinations not detected
- Files: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/trilat/trilat.go` (lines 60-62)
- Trigger: When any set of 3 nodes becomes collinear
- Workaround: Ensure anchors are placed in non-collinear 3D arrangement

**Negative Squared Distance Clamping:**
- Symptoms: Algorithm clamps negative values under square root to 0, producing warning but continuing
- Files: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/trilat/trilat.go` (lines 55-58, 71-74)
- Trigger: Inconsistent distance measurements
- Workaround: Re-measure distances when warnings appear; use `--validate` flag

## Security Considerations

**No Authentication on Drone Radio:**
- Risk: Radio communication (2.4GHz) is unencrypted by default
- Files: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/test-hover.py`
- Current mitigation: None documented
- Recommendations: Consider implementing CRTP authentication if supported; fly in controlled environments

**USB Device Permissions:**
- Risk: udev rules grant group permissions to USB devices
- Files: Documented in `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/README.md` (lines 28-40)
- Current mitigation: Uses `plugdev` group
- Recommendations: Ensure only trusted users are in plugdev group

## Performance Bottlenecks

**Python Serial Communication:**
- Problem: Uses blocking I/O for logging (500ms period)
- Files: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/test-hover.py` (lines 14, 44-45)
- Cause: Synchronous sleep-based polling loop
- Improvement path: Use async callbacks with non-blocking I/O if available

**Go Trilateration Algorithm:**
- Problem: O(n^2) validation for n nodes
- Files: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/trilat/trilat.go` (lines 83-117)
- Cause: Nested loops recompute all pairwise distances
- Improvement path: Not critical for small n (4-8 anchors); optimize only if scaling beyond

## Fragile Areas

**Python Dependency Chain:**
- Why fragile: Depends on cfclient/cflib which may have compatibility issues
- Files: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/test-hover.py`, `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/requirements.txt`
- Safe modification: Pin specific versions in requirements.txt
- Test coverage: None; script tested manually only

**Trilateration Input Format:**
- Why fragile: CSV/TSV parsing is strict about format; missing cells cause errors
- Files: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/io/csv.go`
- Safe modification: Test any format changes against the template generator
- Test coverage: Partial; integration test exists but not exhaustive

## Scaling Limits

**Radio Range:**
- Current capacity: ~30m line-of-sight for Crazyradio 2.0
- Limit: Indoor use only; UWB anchors limited to ~30m
- Scaling path: Add more anchors for larger spaces; use TDoA mode for multi-drone

**Python Script Single-Drone:**
- Current capacity: Single drone per radio connection
- Limit: Only one URI can be connected at a time
- Scaling path: Use multiple radios (different channels) or implement multi-drone orchestration

## Dependencies at Risk

**cfclient/cflib:**
- Risk: Python package may not support latest Python versions
- Impact: Script may fail on newer Python installations
- Migration plan: Check Bitcraze GitHub for Python 3.11+ compatibility; consider using cflib directly without GUI

**Go Dependencies:**
- Risk: Minimal dependencies (cobra only), should be stable
- Impact: Low
- Migration plan: None needed currently

## Missing Critical Features

**Automated Testing:**
- Problem: No CI/CD or automated test suite for Python flight scripts
- Blocks: Safe refactoring, regression detection

**Error Recovery:**
- Problem: No reconnection logic if radio drops
- Blocks: Reliable autonomous flight

**Configuration Management:**
- Problem: All settings hardcoded or command-line only
- Blocks: Multi-environment deployments

## Test Coverage Gaps

**Python test-hover.py:**
- What's not tested: Connection failure, position estimator instability, motor kill safety
- Files: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/test-hover.py`
- Risk: Untested error paths could cause unexpected drone behavior
- Priority: High (safety-critical)

**Go drone-acharya:**
- What's not tested: Invalid input files, malformed CSV, edge cases in trilateration
- Files: `/Users/cgadgil/dev/src/metrum-ai/resistance-is-futile/tools/drone-acharya/`
- Risk: User-facing errors not gracefully handled
- Priority: Medium

---

*Concerns audit: 2026-02-27*
