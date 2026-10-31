#!/usr/bin/env bash
# PROPOSED by the Guardian (not installed). Run after the post step, even when the post step failed (if: always()).
# MERGES the checkout's history into the unprotected state branch, never into main and never overwriting: posts are
# unioned and a claim only moves forward (claimed -> posted). Retries once if the branch moved. The logic lives in
# poster_gate.py; exit 1 means "could not save", and the message tells the owner not to re-run blindly.
set -euo pipefail
exec python3 -B "$(dirname "$0")/poster_gate.py" save
