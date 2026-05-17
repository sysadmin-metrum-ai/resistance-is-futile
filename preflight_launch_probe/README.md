# Preflight Launch Probe

Isolated cflib timing experiment. It does not use or modify the API flow.

The script connects, resets/waits for Kalman, reads Lighthouse pose, arms, then keeps the link open while waiting for launch input. After launch, it measures how long it takes to dispatch `takeoff()`.

Run from the repo root:

```bash
uv run python preflight_launch_probe/run_probe.py --uris radio://0/80/2M/E7E7E7E701
```

Multiple drones:

```bash
uv run python preflight_launch_probe/run_probe.py --uris radio://0/80/2M/E7E7E7E701 radio://0/80/2M/E7E7E7E702
```

Measure preflight only:

```bash
uv run python preflight_launch_probe/run_probe.py --uris radio://0/80/2M/E7E7E7E701 --preflight-only
```
