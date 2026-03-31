# Drone Commissioning Flow

This is the explicit bring-up path for a new Crazyflie entering the demo fleet.

## Goals

- Keep human testing easy and checklist-driven.
- Make the required runtime profile explicit after flashing.
- Gate single-drone and swarm use on the same verification flow.
- Keep CI focused on repeatable software checks while leaving hardware checks explicit.

## Operator Checklist

1. Props off for firmware flash, parameter provisioning, and any motor-direction check.
2. Verify radio dongle is visible and the drone can be reached on the expected URI.
3. Flash the target firmware.
4. Apply the required runtime profile.
5. Run hardware health verification.
6. Run LPS preflight.
7. Run hover litmus test.
8. Only then mark the drone ready for the fleet.

## Required Runtime Profile

### TDoA3 demo profile

Use this for the DTW booth and the 8-anchor acrylic-box demo:

- `loco.mode=3`
- `stabilizer.estimator=2`
- `tdoa3.stddev=0.15`
- `kalman.robustTdoa=0`
- `commander.enHighLevel=1`

### TWR bench profile

Use this for 4-anchor single-drone benches:

- `loco.mode=1`
- `stabilizer.estimator=2`
- `tdoa3.stddev=0.15`
- `kalman.robustTdoa=0`
- `commander.enHighLevel=1`

## One-Command Bring-up

```bash
scripts/commission-drone.sh \
  --uri radio://0/90/2M \
  --profile tdoa3 \
  --firmware firmware/brushless/cf21bl-2025.09.bin \
  --anchors scripts/anchors.py
```

Optional stages:

- `--motors` adds the motor spin test to hardware verification
- `--skip-lps` skips LPS preflight
- `--skip-hover` skips the hover litmus test

## Manual Stage Notes

### Firmware flash

```bash
uv run python -m cfloader flash firmware/brushless/cf21bl-2025.09.bin stm32-fw -w radio://0/0/2M
```

### Apply runtime profile

```bash
uv run python scripts/provision-drone.py --uri radio://0/90/2M --profile tdoa3
```

### Health verification

```bash
uv run python test-health.py --uri radio://0/90/2M
uv run python test-health.py --uri radio://0/90/2M --motors
```

### LPS verification

```bash
uv run python scripts/lps-preflight.py --uri radio://0/90/2M --anchors scripts/anchors.py
```

### Hover litmus test

```bash
uv run python test-hover.py --uri radio://0/90/2M
```

## CI-Friendly Hooks

Use the shared checks script in CI or before merging:

```bash
scripts/run-python-checks.sh
```

This should stay focused on software-only checks:

- compile all Python entrypoints
- static lint
- pure unit tests for mission planning / preflight / commissioning defaults

Hardware checks remain operator-run and explicit.
