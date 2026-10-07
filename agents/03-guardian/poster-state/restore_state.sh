#!/usr/bin/env bash
# PROPOSED by the Guardian (not installed). Run after checkout and BEFORE the post step.
# Copies the authoritative post history from the unprotected branch into the working tree.
# Fails closed: if the branch is missing or the file is not valid JSON, the run stops (GitHub emails the owner)
# instead of posting from a stale history, which could post twice in one day.
set -euo pipefail
BRANCH="${STATE_BRANCH:-poster-state}"
FILE="${STATE_FILE:-bloor-assets/state.json}"
REMOTE="${STATE_REMOTE:-origin}"

if ! git ls-remote --exit-code --heads "$REMOTE" "$BRANCH" >/dev/null 2>&1; then
  echo "ERROR: branch '$BRANCH' does not exist on $REMOTE. Create it once from main (see OWNER-SETUP-CHECKLIST.md) before this workflow runs." >&2
  exit 1
fi
git fetch --no-tags --depth=1 "$REMOTE" "$BRANCH"
mkdir -p "$(dirname "$FILE")"
git show "FETCH_HEAD:$FILE" > "$FILE.tmp"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert isinstance(d.get("posted"), dict)' "$FILE.tmp" \
  || { echo "ERROR: $FILE on '$BRANCH' is not a valid post history." >&2; rm -f "$FILE.tmp"; exit 1; }
mv "$FILE.tmp" "$FILE"
echo "Post history restored from $REMOTE/$BRANCH."
