#!/usr/bin/env bash
# Smoke-test the CLI against a real simc binary (not run by pytest).
# Usage: scripts/smoke.sh [profile.simc]
set -euo pipefail

PROFILE="${1:-examples/example_blood.simc}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="$ROOT/src"

if [[ -z "${SIMC:-}" ]]; then
  for cand in /root/simc-build/src/build/simc /usr/local/bin/simc; do
    [[ -x "$cand" ]] && export SIMC="$cand" && break
  done
fi
if [[ -z "${SIMC:-}" ]]; then
  echo "no simc binary found; set SIMC=/path/to/simc" >&2
  exit 2
fi

echo "== margin =="
python3 -m simc_tank.cli margin "$PROFILE" --rate 100000 --iterations 400
echo
echo "== ttd =="
python3 -m simc_tank.cli ttd "$PROFILE" --iterations 300
echo
echo "== ceiling =="
python3 -m simc_tank.cli ceiling "$PROFILE" --iterations 300
echo
echo "== variants =="
python3 -m simc_tank.cli variants "$PROFILE" --iterations 200
