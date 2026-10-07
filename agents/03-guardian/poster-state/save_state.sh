#!/usr/bin/env bash
# PROPOSED by the Guardian (not installed). Run after the post step.
# Commits the post history to the unprotected state branch, never to main. A separate worktree is used so the
# checked-out files are not touched. Retries once if the branch moved meanwhile.
set -euo pipefail
BRANCH="${STATE_BRANCH:-poster-state}"
FILE="${STATE_FILE:-bloor-assets/state.json}"
REMOTE="${STATE_REMOTE:-origin}"
NAME="${GIT_AUTHOR_NAME:-github-actions}"
EMAIL="${GIT_AUTHOR_EMAIL:-github-actions@users.noreply.github.com}"

for attempt in 1 2; do
  git fetch --no-tags --depth=1 "$REMOTE" "$BRANCH"
  tip="$(mktemp)"; merged="$(mktemp)"
  git show "FETCH_HEAD:$FILE" > "$tip" 2>/dev/null || echo '{"posted": {}}' > "$tip"
  # Merge, never overwrite: every day already on the branch is kept, so two runs cannot erase each other's entry.
  python3 - "$FILE" "$tip" "$merged" <<'PY'
import json, sys
local, tip, out = (json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3])
merged = {**tip, **local, "posted": {**tip.get("posted", {}), **local.get("posted", {})}}
open(out, "w", encoding="utf-8").write(json.dumps(merged, indent=2) + "\n")
PY
  if cmp -s "$tip" "$merged"; then
    echo "Post history unchanged; nothing to save."
    exit 0
  fi
  wt="$(mktemp -d)"
  git worktree add -q --detach "$wt" FETCH_HEAD
  mkdir -p "$wt/$(dirname "$FILE")"
  cp "$merged" "$wt/$FILE"
  ok=0
  ( cd "$wt" \
    && git -c user.name="$NAME" -c user.email="$EMAIL" add "$FILE" \
    && git -c user.name="$NAME" -c user.email="$EMAIL" commit -q -m "Record today's post" \
    && git push -q "$REMOTE" "HEAD:refs/heads/$BRANCH" ) && ok=1
  git worktree remove --force "$wt"
  if [ "$ok" = 1 ]; then
    echo "Post history saved to $REMOTE/$BRANCH."
    exit 0
  fi
  echo "Push failed on attempt $attempt; fetching the latest and retrying." >&2
done
echo "ERROR: could not save the post history to '$BRANCH'. Do not re-run the post step today without checking Threads." >&2
exit 1
