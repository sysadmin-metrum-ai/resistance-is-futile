#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_RUNNER=("uv" "run" "python")

if ! command -v uv >/dev/null 2>&1; then
  PYTHON_RUNNER=("python3")
fi

ANCHORS_FILE="scripts/anchors.py"
URI=""
HEALTH_URI=""
RUN_MOTORS=0
RUN_MULTI=0
SKIP_GEOMETRY=0
SKIP_HOVER=0
SKIP_LPS=0

usage() {
  cat <<'EOF'
Usage: scripts/sanity-check.sh [options]

Runs the ordered operator sanity flow for anchor geometry, fleet health,
LPS readiness, single-drone hover, and optional multi-drone smoke checks.

Options:
  --anchors PATH       Anchor positions file (default: scripts/anchors.py)
  --uri URI            Primary drone URI for single-drone hover/LPS steps
  --health-uri URI     Single URI override for hardware health stage
  --motors             Include motor spin test during fleet health
  --multi              Include multi-drone smoke test
  --skip-geometry      Skip anchor geometry stage
  --skip-lps           Skip LPS preflight stage
  --skip-hover         Skip single-drone hover stage
  -h, --help           Show this help
EOF
}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "ERROR: required command '$1' not found" >&2
    exit 2
  fi
}

run_stage() {
  local number="$1"
  local name="$2"
  local success_action="$3"
  local failure_action="$4"
  shift 4

  local stage_title
  stage_title=$(printf 'Stage %02d: %s' "$number" "$name")

  printf '\n========================================================================\n'
  echo "$stage_title"
  printf '========================================================================\n'
  echo "CMD: $*"
  printf '%s\n' '------------------------------------------------------------------------'

  set +e
  "$@"
  local rc=$?
  set -e

  STAGE_TITLES+=("$stage_title")
  STAGE_CODES+=("$rc")
  if [[ "$rc" -eq 0 ]]; then
    STAGE_ACTIONS+=("$success_action")
    echo "Stage Result: GO"
    echo "Next Action: $success_action"
  else
    STAGE_ACTIONS+=("$failure_action")
    echo "Stage Result: NO-GO"
    echo "Next Action: $failure_action"
    OVERALL_STATUS="NO-GO"
    print_summary
    exit "$rc"
  fi
}

print_summary() {
  printf '\n########################################################################\n'
  echo "SANITY FLOW SUMMARY"
  printf '########################################################################\n'

  local idx
  for idx in "${!STAGE_TITLES[@]}"; do
    local status="GO"
    if [[ "${STAGE_CODES[$idx]}" -ne 0 ]]; then
      status="NO-GO"
    fi
    printf '[%-5s] %s\n' "$status" "${STAGE_TITLES[$idx]}"
    printf '        %s\n' "${STAGE_ACTIONS[$idx]}"
  done

  printf '\nOVERALL: %s\n' "$OVERALL_STATUS"
  printf 'Operator Next Actions:\n'
  if [[ "$OVERALL_STATUS" == "GO" ]]; then
    printf -- '- Proceed to the next planned verification or demo mission.\n'
    printf -- '- Keep the same anchors and launch pads to preserve test repeatability.\n'
  else
    printf -- '- Fix the NO-GO stage above before attempting later stages.\n'
    printf -- '- Re-run this script after the corrective action to confirm a clean pass.\n'
  fi
}

STAGE_TITLES=()
STAGE_CODES=()
STAGE_ACTIONS=()
OVERALL_STATUS="GO"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --anchors)
      ANCHORS_FILE="$2"
      shift 2
      ;;
    --uri)
      URI="$2"
      shift 2
      ;;
    --health-uri)
      HEALTH_URI="$2"
      shift 2
      ;;
    --motors)
      RUN_MOTORS=1
      shift
      ;;
    --multi)
      RUN_MULTI=1
      shift
      ;;
    --skip-geometry)
      SKIP_GEOMETRY=1
      shift
      ;;
    --skip-hover)
      SKIP_HOVER=1
      shift
      ;;
    --skip-lps)
      SKIP_LPS=1
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

cd "$ROOT_DIR"
require_cmd "${PYTHON_RUNNER[0]}"

echo "Operator sanity flow starting from $ROOT_DIR"
echo "Anchors file: $ANCHORS_FILE"
if [[ -n "$URI" ]]; then
  echo "Primary URI: $URI"
fi
if [[ -n "$HEALTH_URI" ]]; then
  echo "Health-stage URI override: $HEALTH_URI"
fi

if [[ "$SKIP_GEOMETRY" -eq 0 ]]; then
  run_stage 1 "Anchor geometry" \
    "Anchor geometry is acceptable for flight checks." \
    "Fix anchor placement or survey values before continuing." \
    "${PYTHON_RUNNER[@]}" scripts/check-anchor-geometry.py --anchors "$ANCHORS_FILE"
fi

HEALTH_CMD=("${PYTHON_RUNNER[@]}" test-health.py)
if [[ "$RUN_MOTORS" -eq 1 ]]; then
  HEALTH_CMD+=("--motors")
fi
if [[ -n "$HEALTH_URI" ]]; then
  HEALTH_CMD+=("--uri" "$HEALTH_URI")
fi
run_stage 2 "Fleet health" \
  "Fleet hardware checks passed. You can move to LPS readiness." \
  "Charge batteries, fix self-test issues, or inspect motors before flight." \
  "${HEALTH_CMD[@]}"

if [[ "$SKIP_LPS" -eq 0 ]]; then
  LPS_CMD=("${PYTHON_RUNNER[@]}" scripts/lps-preflight.py --anchors "$ANCHORS_FILE")
  if [[ -n "$URI" ]]; then
    LPS_CMD+=("--uri" "$URI")
  fi
  run_stage 3 "LPS preflight" \
    "Localization is stable enough to attempt hover." \
    "Check anchor programming, line of sight, deck detection, and estimator mode." \
    "${LPS_CMD[@]}"
fi

if [[ "$SKIP_HOVER" -eq 0 ]]; then
  HOVER_CMD=("${PYTHON_RUNNER[@]}" test-hover.py)
  if [[ -n "$URI" ]]; then
    HOVER_CMD+=("--uri" "$URI")
  fi
  run_stage 4 "Single-drone hover" \
    "Single-drone hover passed. You can move on to multi-drone verification." \
    "Do not attempt swarm flight. Re-run after fixing localization or hover stability." \
    "${HOVER_CMD[@]}"
fi

if [[ "$RUN_MULTI" -eq 1 ]]; then
  run_stage 5 "Multi-drone smoke" \
    "Multi-drone spacing and hover checks passed." \
    "Reduce to fewer drones or re-space launch pads before the demo run." \
    "${PYTHON_RUNNER[@]}" test-hover-multidrone.py
fi

print_summary
exit 0
