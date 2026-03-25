# Crazyflie Loco Positioning System Setup

Development environment and flight scripts for Crazyflie 2.1 drones with Loco Positioning System (LPS) for indoor 3D positioning.

## Hardware

- Crazyflie 2.1 drone with Loco Positioning deck
- Crazyradio 2.0 USB dongle
- 4-8 Loco Positioning nodes (UWB anchors)
- Linux laptop (Ubuntu 22.04+)

## 1. System Dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv \
  libxcb-xinerama0 libxcb-cursor0 libusb-1.0-0-dev libudev-dev git picocom
```

## 2. USB Permissions (udev rules)

```bash
sudo groupadd -f plugdev
sudo usermod -a -G plugdev $USER
```

```bash
cat <<'EOF' | sudo tee /etc/udev/rules.d/99-bitcraze.rules > /dev/null
# Crazyradio 2.0 (native firmware)
SUBSYSTEM=="usb", ATTRS{idVendor}=="35f0", ATTRS{idProduct}=="bad2", MODE="0664", GROUP="plugdev"
# Crazyradio (CRPA emulation)
SUBSYSTEM=="usb", ATTRS{idVendor}=="1915", ATTRS{idProduct}=="7777", MODE="0664", GROUP="plugdev"
# Crazyradio bootloader
SUBSYSTEM=="usb", ATTRS{idVendor}=="1915", ATTRS{idProduct}=="0101", MODE="0664", GROUP="plugdev"
# Crazyflie (over USB)
SUBSYSTEM=="usb", ATTRS{idVendor}=="0483", ATTRS{idProduct}=="5740", MODE="0664", GROUP="plugdev"
EOF
sudo udevadm control --reload-rules
sudo udevadm trigger
```

**Log out and log back in** for group membership to take effect.

## 3. Python Environment

```bash
python3 -m venv ~/crazyflie-env
source ~/crazyflie-env/bin/activate
pip install --upgrade pip
pip install cfclient
```

This installs cfclient (GUI) and cflib (Python API) together.

## 4. Crazyradio 2.0 Firmware

cflib only supports CRPA emulation firmware (USB ID `1915:7777`). If your radio shows `35f0:bad2` in `lsusb`, flash CRPA emulation:

1. Download the firmware:
   ```bash
   cd ~/Downloads
   wget https://github.com/bitcraze/crazyradio2-firmware/releases/download/1.1/crazyradio2-CRPA-emulation-1.1.uf2
   ```

2. Enter bootloader mode: hold the button on the dongle while plugging it in (LED pulses red)

3. Copy firmware to the USB drive that appears:
   ```bash
   cp ~/Downloads/crazyradio2-CRPA-emulation-1.1.uf2 /media/$USER/Crazyradio2/
   ```

4. The dongle reboots automatically. Verify:
   ```bash
   lsusb | grep 1915
   # Expected: ID 1915:7777 Nordic Semiconductor ASA
   ```

## 5. Loco Node Firmware and Anchor ID Setup

Connect each node one at a time via USB. The node appears as a serial port.

```bash
picocom /dev/ttyACM0 -b 115200
```

In the serial console:

- Press `h` for help menu
- Press `0`-`3` to set the anchor ID (each node needs a unique ID)
- Press `m` to change mode -- select **TWR Anchor**
- Exit with `Ctrl+A` then `Ctrl+X`

Repeat for all nodes, assigning IDs 0 through N-1.

### Mode Selection

| Mode | Min Anchors | Max Drones | Best For |
|------|-------------|------------|----------|
| TWR | 4 (6+ recommended) | 1 | Single drone, best accuracy |
| TDoA 2 | 8 | Unlimited | Swarms, fixed 8 anchors |
| TDoA 3 | 6+ | Unlimited | Swarms, scalable spaces |

**Use TWR for setups with 4 anchors.** TDoA modes require more anchors for stable positioning.

## 6. Anchor Position Configuration

Anchors measure distances but do not know their own positions. You must enter each anchor's XYZ coordinates (in meters) manually.

1. Pick a room corner as origin (0, 0, 0)
2. Measure each anchor's position relative to the origin
3. Aim for +/- 2-3 cm accuracy; Z (height) is most critical

In cfclient:

1. Launch: `source ~/crazyflie-env/bin/activate && LIBGL_ALWAYS_SOFTWARE=1 cfclient`
2. Connect to the Crazyflie
3. Open the **Loco Positioning** tab
4. Click each anchor and enter its X, Y, Z coordinates
5. Click **Write to anchors** to save

### Anchor Placement Tips

- Place anchors in a 3D arrangement (not all at the same height)
- Keep antenna 15cm from walls/ceiling/metal
- Maintain line of sight from drone to at least 3-4 anchors
- Spread anchors at least 2-3 meters apart

## 7. Set Crazyflie Loco Mode

In cfclient, go to the **Parameters** tab and set `loco.mode`:

| Value | Mode |
|-------|------|
| 0 | Auto |
| 1 | TWR |
| 2 | TDoA 2 |
| 3 | TDoA 3 |

Set to **1** for TWR setups.

### Caution: TDoA3 debug params can cause large drift

During troubleshooting we temporarily changed estimator tuning:

- `tdoa3.stddev=0.8` (from default ~`0.15`)
- `kalman.robustTdoa=1`

This made the estimator under-weight UWB corrections and produced large stationary drift (especially Z) even though anchors and link were otherwise healthy.

For normal TDoA3 operation, reset to:

```bash
# keep mode forced to TDoA3
python - <<'PY'
import time
import cflib.crtp
from cflib.crazyflie import Crazyflie
from cflib.crazyflie.syncCrazyflie import SyncCrazyflie

URI = "radio://0/90/2M"
cflib.crtp.init_drivers()
with SyncCrazyflie(URI, cf=Crazyflie(rw_cache="./cache")) as scf:
    cf = scf.cf
    cf.param.set_value("loco.mode", "3")
    cf.param.set_value("tdoa3.stddev", "0.15")
    cf.param.set_value("kalman.robustTdoa", "0")
    time.sleep(0.3)
    print("loco.mode=", cf.param.get_value("loco.mode"))
    print("tdoa3.stddev=", cf.param.get_value("tdoa3.stddev"))
    print("kalman.robustTdoa=", cf.param.get_value("kalman.robustTdoa"))
PY
```

Recommended: run `scripts/lps-preflight.py` before flight and treat `NO-GO` as a hard stop.

## 8. Launch cfclient

The 3D view requires software rendering on some systems to avoid vispy/OpenGL errors:

```bash
source ~/crazyflie-env/bin/activate
LIBGL_ALWAYS_SOFTWARE=1 cfclient
```

Or use the launcher script:

```bash
~/launch-cfclient.sh
```

## Quick Reference

```bash
source ~/crazyflie-env/bin/activate  # Activate environment
LIBGL_ALWAYS_SOFTWARE=1 cfclient     # Launch GUI
lsusb | grep 1915                    # Check radio detected
groups $USER                         # Verify plugdev membership
cat /etc/udev/rules.d/99-bitcraze.rules  # Check udev rules
pip show cfclient                    # Check version
```

## Running Flight Scripts

Close cfclient first (only one program can use the radio at a time).

```bash
source ~/crazyflie-env/bin/activate
python test-hover.py
```

The test script waits for the Kalman filter position estimate to stabilize before takeoff. Press `Ctrl+C` at any time to kill motors.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `No backend available` | `sudo apt install libusb-1.0-0-dev` and `pip install pyusb` |
| Radio not found in scan | Check udev rules, replug dongle, verify `lsusb \| grep 1915` |
| Permission denied on USB | Log out and back in after `usermod -a -G plugdev` |
| cfclient won't launch | Activate venv: `source ~/crazyflie-env/bin/activate` |
| `eglSwapBuffers` spam | Launch with `LIBGL_ALWAYS_SOFTWARE=1 cfclient` |
| Connection drops ("Too many packets lost") | Use `LIBGL_ALWAYS_SOFTWARE=1`, try `radio://0/80/1M`, avoid USB 3.0 ports |
| Loco tab shows no anchors | Verify nodes are powered, in same mode as deck, and within UWB range |
| Position drifting wildly | Check mode match (TWR for 4 anchors), verify anchor XYZ positions are correct, and reset `tdoa3.stddev=0.15` + `kalman.robustTdoa=0` if they were changed for debugging |
| Anchor shows 0,0,0 position | Enter and write correct positions via cfclient Loco tab |

## Documentation

- **Venue survey (laser → drone-acharya → push-anchors):** [docs/venue-survey-procedure.md](docs/venue-survey-procedure.md)
- **drone-acharya (template, solve, NED):** [tools/drone-acharya/README.md](tools/drone-acharya/README.md), [tools/drone-acharya/COORDINATES.md](tools/drone-acharya/COORDINATES.md)
- **Drone API usage:** [docs/API_USAGE.md](docs/API_USAGE.md)
- **Infographic prompts** (for generating visual guides): [docs/infographic-prompt-location-map-drone-acharya.md](docs/infographic-prompt-location-map-drone-acharya.md), [docs/infographic-prompt-rotations-translations.md](docs/infographic-prompt-rotations-translations.md), [docs/infographic-prompt-test-flight-after-calibration.md](docs/infographic-prompt-test-flight-after-calibration.md)

## Architecture

```
Loco Anchor Nodes (4-8x)
    | UWB ranging
Crazyflie 2.1 + Loco Deck
    | 2.4GHz radio
Crazyradio 2.0 (USB dongle)
    | USB
Linux Laptop (cfclient / Python scripts)
```
