#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_RUNNER=("uv" "run" "python")

if ! command -v uv >/dev/null 2>&1; then
  PYTHON_RUNNER=("python3")
fi

URI=""
PROFILE="tdoa3"
FIRMWARE_PATH=""
ANCHORS_FILE="scripts/anchors.py"
RUN_MOTORS=0
SKIP_FLASH=0
SKIP_LPS=0
SKIP_HOVER=0

usage() {
  cat <<'EOF'
Usage: scripts/commission-drone.sh --uri radio://0/90/2M [options]

Explicit new-drone bring-up flow:
  1. Optional firmware flash
  2. Apply required params/modes
  3. Hardware health verification
  4. LPS verification
  5. Hover litmus test

Options:
  --uri URI              Drone URI to commission (required)
  --profile MODE         Commissioning profile: tdoa3 or twr (default: tdoa3)
  --firmware PATH        Firmware image to flash before provisioning
  --anchors PATH         Anchors file for LPS preflight (default: scripts/anchors.py)
  --motors               Include motor spin test in hardware verification
  --skip-flash           Skip firmware flash stage even if --firmware is provided
  --skip-lps             Skip LPS preflight stage
  --skip-hover           Skip hover litmus test
  -h, --help             Show this help
EOF
}

run_stage() {
  local name="$1"
  shift
  printf '\n[%s] %s\n' "$(date '+%H:%M:%S')" "$name"
  echo "CMD: $*"
  "$@"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --uri)
      URI="$2"
      shift 2
      ;;
    --profile)
      PROFILE="$2"
      shift 2
      ;;
    --firmware)
      FIRMWARE_PATH="$2"
      shift 2
      ;;
    --anchors)
      ANCHORS_FILE="$2"
      shift 2
      ;;
    --motors)
      RUN_MOTORS=1
      shift
      ;;
    --skip-flash)
      SKIP_FLASH=1
      shift
      ;;
    --skip-lps)
      SKIP_LPS=1
      shift
      ;;
    --skip-hover)
      SKIP_HOVER=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "ERROR: unknown argument '$1'" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$URI" ]]; then
  echo "ERROR: --uri is required" >&2
  usage
  exit 2
fi

cd "$ROOT_DIR"

echo "Commissioning drone at $URI"
echo "Profile: $PROFILE"
echo "Props off unless you are explicitly running a motor stage."

if [[ -n "$FIRMWARE_PATH" && "$SKIP_FLASH" -eq 0 ]]; then
  run_stage \
    "Firmware flash" \
    uv run python -m cfloader flash "$FIRMWARE_PATH" stm32-fw -w "$URI"
fi

run_stage \
  "Apply runtime profile" \
  "${PYTHON_RUNNER[@]}" scripts/provision-drone.py --uri "$URI" --profile "$PROFILE"

HEALTH_CMD=("${PYTHON_RUNNER[@]}" test-health.py --uri "$URI")
if [[ "$RUN_MOTORS" -eq 1 ]]; then
  HEALTH_CMD+=("--motors")
fi
run_stage "Hardware verification" "${HEALTH_CMD[@]}"

if [[ "$SKIP_LPS" -eq 0 ]]; then
  run_stage \
    "LPS preflight verification" \
    "${PYTHON_RUNNER[@]}" scripts/lps-preflight.py --uri "$URI" --anchors "$ANCHORS_FILE"
fi

if [[ "$SKIP_HOVER" -eq 0 ]]; then
  run_stage \
    "Hover litmus test" \
    "${PYTHON_RUNNER[@]}" test-hover.py --uri "$URI"
fi

printf '\n[%s] COMMISSIONING PASSED for %s\n' "$(date '+%H:%M:%S')" "$URI"
