#!/usr/bin/env bash
# PROPOSED by the Guardian (not installed). Run after checkout and BEFORE the post step.
# Copies the authoritative post history (and any unconfirmed claim) from the unprotected branch into the working tree.
# Fails closed: if the branch is missing, the file is not valid, or the branch is BEHIND this checkout (main records a
# post the branch lacks), the run stops instead of posting from a stale history. The logic lives in poster_gate.py.
set -euo pipefail
exec python3 -B "$(dirname "$0")/poster_gate.py" restore
