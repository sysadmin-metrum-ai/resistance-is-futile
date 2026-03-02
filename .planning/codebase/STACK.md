# Technology Stack

**Analysis Date:** 2026-02-27

## Languages

**Primary:**
- Python 3 - Used in root project for drone control scripts (e.g., `test-hover.py`)
- Go 1.25.0 - Used in `tools/drone-acharya` for trilateration calculator CLI tool

**Secondary:**
- None detected

## Runtime

**Environment:**
- Python 3.x (Ubuntu 22.04+ recommended per README)
- Go 1.25.0

**Package Manager:**
- Python: pip with virtual environments (`python3 -m venv`)
- Go: Native Go modules (go.mod)
- Lockfile: Not detected (Go uses go.mod; Python uses requirements.txt without lockfile)

## Frameworks

**Core (Python):**
- cflib - Crazyflie Python library for drone communication
- cfclient - Crazyflie client GUI (includes cflib as dependency)
- Standard library: time, ctypes (via cflib)

**CLI (Go):**
- spf13/cobra v1.10.2 - CLI framework for drone-acharya
- spf13/pflag v1.0.9 - Flag parsing (cobra dependency)
- inconshreveable/mousetrap v1.1.0 - CLI enhancement (cobra dependency)

**Testing:**
- Go: Built-in testing package (`testing` in stdlib)
- Python: Not detected (no pytest, unittest, or test frameworks found)

**Build/Dev:**
- Go: Native `go build`/`go run`
- Python: Virtual environment with pip

## Key Dependencies

**Python (Crazyflie):**
- cfclient - Main drone control library
- cflib - Low-level Crazyflie protocol library
- pyusb (optional) - USB communication backend
- vispy (transitive) - 3D visualization in cfclient
- libusb (system) - USB driver for radio communication

**Go (drone-acharya):**
- Standard library only for core logic
- No external dependencies beyond cobra/pflag

## Configuration

**Environment:**
- Virtual environment for Python isolation
- USB device permissions via udev rules (Crazyradio, Crazyflie)
- Environment variable `LIBGL_ALWAYS_SOFTWARE=1` for cfclient rendering

**Build:**
- Go: No build config files (uses standard go.mod)
- Python: requirements.txt (minimal)

## Platform Requirements

**Development:**
- Linux laptop (Ubuntu 22.04+)
- USB 2.0/3.0 ports
- Crazyradio 2.0 USB dongle
- Python 3, pip, venv support

**Production:**
- Not applicable (embedded/robotics project running on local hardware)

**Hardware:**
- Crazyflie 2.1 drone with Loco Positioning deck
- Crazyradio 2.0 USB dongle
- 4-8 Loco Positioning nodes (UWB anchors)

---

*Stack analysis: 2026-02-27*
