#!/usr/bin/env python3
"""Fail-closed post gate for the daily Threads poster. PROPOSED reference implementation; not installed.
Design and rationale: agent-system/change-requests/03-guardian-poster-fail-closed.md. Standard library only.

The idea: the poster must RECORD ITS INTENT before it creates anything on Threads, and the record must be a
durable write that only one run can win. If the record cannot be written, or an earlier run left one that was
never confirmed, the poster does not post. A missing state entry can then never lead to a second post.

State lives on the unprotected branch `poster-state`, in bloor-assets/state.json:
  {"posted": {date: {...}}, "claims": {date: {"status": "claimed|posted|released", ...}}}
`posted` is exactly what post_threads.py already reads and writes. `claims` is new and ignored by it.

Commands (used by the shell wrappers; the poster imports the module):
  restore            copy the authoritative state into the checkout; refuse if the branch is missing, invalid, or
                     behind the checkout (a date that main knows is missing on the branch)
  save               merge the checkout's state into the branch (never overwrites); used after the post step
  claim DATE [RUN]   record intent to post DATE; exit 0 = go, 10 = already posted, 11 = blocked, 12 = cannot confirm
  complete DATE ID LINK    record that the post is live (the owner uses this by hand after finding the post on Threads)
  release DATE REASON      give up a claim (the poster does this itself only before the publish call; the owner may do it
                     by hand after checking Threads)
DATE for complete, release and status must be YYYY-MM-DD, a real calendar day, and not later than today in the poster's own
timezone (config.json "timezone", America/Toronto). Anything else exits 2 and changes nothing. After 8 pm Toronto the UTC date
is already tomorrow: do not type that one. (POSTER_GATE_TODAY=YYYY-MM-DD replaces "today" for the test suite only.)
  export PATH        write the branch's history in the old format, for a rollback (refuses while a claim is unconfirmed)
  status [DATE]      read-only: list what the branch records (posted / claimed / released); with DATE exit 0 = posted,
                     11 = claimed and unconfirmed, 3 = nothing recorded for that day, 2 = DATE is not a valid past-or-today date
"""
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

sys.dont_write_bytecode = True
BRANCH = os.environ.get("STATE_BRANCH", "poster-state")
FILE = os.environ.get("STATE_FILE", "bloor-assets/state.json")
REMOTE = os.environ.get("STATE_REMOTE", "origin")
NAME = os.environ.get("GIT_AUTHOR_NAME", "github-actions")
EMAIL = os.environ.get("GIT_AUTHOR_EMAIL", "github-actions@users.noreply.github.com")
RANK = {"released": 0, "claimed": 1, "posted": 2}


def rebuild_help():
    """What the owner must do when the state branch is missing, rewound or re-created. The ORDER is the safety:
    a branch that was deleted and re-created from main has forgotten every post made since its history was last saved,
    so if today's post is already live the next run (a backup cron, a manual run) would post it a second time."""
    return (f"Do NOT simply re-create '{BRANCH}' from main and carry on: a re-created or rewound branch has forgotten the posts made since its history "
            f"was last saved, and if today's post is already live the next run posts it a second time. Do this in order. "
            f"(1) PAUSE the poster first with its own switch: set \"paused\": true in bloor-assets/config.json by pull request, merge it, and wait until no poster run is in progress. "
            f"(2) Create '{BRANCH}' from main (or put it back). "
            f"(3) For every day that has already posted (look at Threads; today at the very least), re-create its claim: "
            f"python3 scripts/poster_gate.py complete DATE ID LINK. Check with: python3 scripts/poster_gate.py status DATE (exit 0 means recorded). "
            f"(4) Only then set \"paused\": false by pull request. "
            f"Runbook: agents/03-guardian/OWNER-SETUP-CHECKLIST.md, section 'poster-state was deleted, rewound or re-created'. At first-time setup the checklist's step 3.1 applies instead.")


class Blocked(Exception):
    """An earlier run claimed or posted this date and the outcome is not confirmed. Do not post."""


class UsageError(Exception):
    """The command line is wrong (for example a date that is malformed or in the future). Nothing was read or written."""


def poster_today():
    """Today's date in the poster's own timezone, the one post_threads.py uses to choose the day. POSTER_GATE_TODAY is a
    test-suite override: it is validated like any date and the owner never needs it."""
    o = os.environ.get("POSTER_GATE_TODAY")
    if o:
        check_date_format(o, "POSTER_GATE_TODAY")
        return o
    tzname = "America/Toronto"
    try:
        with open(os.path.join(os.path.dirname(FILE) or ".", "config.json"), encoding="utf-8") as f:
            tzname = json.load(f).get("timezone") or tzname
    except (OSError, ValueError, AttributeError):
        pass
    if ZoneInfo is None:
        raise UsageError("this Python has no timezone database, so today's date in the poster's timezone cannot be worked out; refusing the date")
    try:
        return datetime.now(ZoneInfo(tzname)).strftime("%Y-%m-%d")
    except Exception:
        raise UsageError(f"the poster's timezone '{tzname}' is not known on this machine, so today's date cannot be worked out; refusing the date")


def check_date_format(d, what="DATE"):
    if not isinstance(d, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", d):
        raise UsageError(f"{what} '{str(d)[:30]}' is not in the form YYYY-MM-DD (for example 2026-10-12). A wrongly written date would be stored as a day of its own and the real day would stay unrecorded.")
    try:
        datetime.strptime(d, "%Y-%m-%d")
    except ValueError:
        raise UsageError(f"{what} '{d}' is not a real calendar day.")


def check_date(d, what="DATE"):
    """A day the owner may record, release or look up: well formed, real, and not later than today in the poster's timezone."""
    check_date_format(d, what)
    today = poster_today()
    if d > today:
        raise UsageError(f"{what} {d} is in the future: today in the poster's timezone is {today}. (After 8 pm Toronto the UTC date is already tomorrow; use the Toronto date.) Nothing was changed.")
    return today


class GateError(Exception):
    """The gate cannot confirm that posting is safe. Do not post."""


# ------------------------------------------------------------------ plumbing
def git(*args, cwd=None, check=True):
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and p.returncode != 0:
        raise GateError(f"git {args[0]} failed: {p.stderr.strip()[-200:]}")
    return p


def _before_push():
    """Test seam: called after the new commit exists and before it is pushed. Does nothing in production."""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ state model
def normalise(state):
    if not isinstance(state, dict) or not isinstance(state.get("posted"), dict):
        raise GateError("state file is not a valid post history")
    claims = state.get("claims", {})
    if not isinstance(claims, dict):
        raise GateError("state file has an invalid 'claims' section")
    state["claims"] = claims
    for d in state["posted"]:  # a claim can never contradict a recorded post
        c = claims.get(d)
        if c is not None and RANK.get(c.get("status"), 1) < RANK["posted"]:
            c["status"] = "posted"
    return state


def merge(a, b):
    """Union of two histories (a is the authoritative side: its entry wins for the same day). Posts are never lost; for a
    claim the more advanced status wins."""
    a, b = normalise(json.loads(json.dumps(a))), normalise(json.loads(json.dumps(b)))
    posted = {**b["posted"], **a["posted"]}
    out = {**a, **b, "posted": dict(sorted(posted.items())), "claims": {}}
    for d in set(a["claims"]) | set(b["claims"]):
        ca, cb = a["claims"].get(d), b["claims"].get(d)
        pick = max((c for c in (ca, cb) if c), key=lambda c: (RANK.get(c.get("status"), 1), c.get("at", "")))
        out["claims"][d] = pick
    return normalise(out)


def confirmed_dates(state):
    s = set(state.get("posted", {}))
    s |= {d for d, c in state.get("claims", {}).items() if c.get("status") == "posted"}
    return s


def dump(state):
    s = dict(state)
    if not s.get("claims"):
        s.pop("claims", None)
    return json.dumps(s, indent=2) + "\n"


# ------------------------------------------------------------------ remote access
def fetch_tip():
    r = git("ls-remote", "--exit-code", "--heads", REMOTE, BRANCH, check=False)
    if r.returncode == 2:
        raise GateError(f"branch '{BRANCH}' does not exist on {REMOTE}, so the post history is unknown and nothing was posted. " + rebuild_help())
    if r.returncode != 0:
        raise GateError(f"cannot reach {REMOTE} to read '{BRANCH}': {r.stderr.strip()[-120:]}")
    git("fetch", "--no-tags", "--depth=1", REMOTE, BRANCH)
    p = git("show", f"FETCH_HEAD:{FILE}", check=False)
    if p.returncode != 0:
        raise GateError(f"{FILE} is missing on '{BRANCH}'. " + rebuild_help())
    try:
        return normalise(json.loads(p.stdout))
    except (ValueError, GateError):
        raise GateError(f"{FILE} on '{BRANCH}' is not a valid post history")


def local_state():
    try:
        with open(FILE, encoding="utf-8") as f:
            return normalise(json.load(f))
    except FileNotFoundError:
        return {"posted": {}, "claims": {}}
    except (ValueError, GateError):
        raise GateError(f"{FILE} in this checkout is not a valid post history")


def check_not_behind(local, tip):
    missing = sorted(confirmed_dates(local) - confirmed_dates(tip))
    if missing:
        raise GateError(f"'{BRANCH}' is behind this checkout: it lacks {', '.join(missing)}, which this checkout records as posted. "
                        f"It was probably cut before those posts were saved. Refusing to continue")


def push_state(new_state, message):
    """Commit new_state on top of the fetched tip and push without force. True = accepted, False = branch moved or rejected."""
    wt = tempfile.mkdtemp()
    try:
        git("worktree", "add", "-q", "--detach", wt, "FETCH_HEAD")
        path = os.path.join(wt, FILE)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(dump(new_state))
        git("-c", f"user.name={NAME}", "-c", f"user.email={EMAIL}", "add", FILE, cwd=wt)
        git("-c", f"user.name={NAME}", "-c", f"user.email={EMAIL}", "commit", "-q", "-m", message, cwd=wt)
        _before_push()
        return git("push", "-q", REMOTE, f"HEAD:refs/heads/{BRANCH}", cwd=wt, check=False).returncode == 0
    finally:
        git("worktree", "remove", "--force", wt, check=False)


# ------------------------------------------------------------------ the gate
_claimed = {"date": None, "past_point_of_no_return": False, "completed": False}


def claim(today, run_id="local"):
    """Record intent to post `today`. Returns 'claimed' or 'already-posted'. Raises Blocked or GateError."""
    for _ in range(3):
        tip = fetch_tip()
        local = local_state()
        check_not_behind(local, tip)
        if today in confirmed_dates(tip) or today in confirmed_dates(local):
            return "already-posted"
        c = tip["claims"].get(today)
        if c and c.get("status") != "released":
            raise Blocked(f"an earlier run claimed {today} at {c.get('at')} (run {c.get('run')}) and never confirmed the post. "
                          f"It may be live on Threads. Check Threads, then fix the state (see the change request runbook)")
        new = merge(tip, {"posted": {}, "claims": {today: {"status": "claimed", "run": str(run_id), "at": now()}}})
        if push_state(new, f"Claim {today} post (run {run_id})"):
            _claimed.update(date=today, past_point_of_no_return=False, completed=False)
            return "claimed"
        # the branch moved (another run, or a save): look again; if someone else claimed it, we will be Blocked next time round
    raise GateError("could not record the claim after 3 attempts; not posting")


def claim_or_exit(today, run_id="local"):
    """For the poster: True = go ahead and post; False = already posted today; exits 11 (blocked) or 12 (cannot confirm)."""
    try:
        return claim(today, run_id) == "claimed"
    except Blocked as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        sys.exit(11)
    except GateError as e:
        print(f"ERROR: cannot confirm it is safe to post, so not posting: {e}", file=sys.stderr)
        sys.exit(12)


def point_of_no_return():
    """Call immediately before the publish request. After this a failure must NOT release the claim."""
    _claimed["past_point_of_no_return"] = True


def complete(today, entry):
    """Record that `today` is live. `entry` is exactly what the poster wrote to its own state file."""
    for _ in range(3):
        try:
            tip = fetch_tip()
        except GateError:
            continue
        new = merge(tip, {"posted": {today: entry}, "claims": {today: {"status": "posted", "at": now()}}})
        if push_state(new, f"Record {today} post"):
            _claimed["completed"] = True
            return
    print(f"::error::POSTED {today} but could not record it on '{BRANCH}'. The claim still blocks any re-run today. "
          f"Do not post again; the save step or the owner must record it.", file=sys.stderr)
    sys.exit(1)


def release(today, reason):
    """Give up a claim. Best effort and never raises: if it fails, the claim stays and blocks (the safe direction)."""
    try:
        tip = fetch_tip()
        c = tip["claims"].get(today, {})
        if c.get("status") != "claimed" or today in confirmed_dates(tip):
            return False
        new = normalise(json.loads(json.dumps(tip)))
        # written directly: merge() would keep the higher status ("claimed") and refuse to release
        new["claims"][today] = {**c, "status": "released", "reason": str(reason)[:200], "at": now()}
        return push_state(new, f"Release {today} claim")
    except Exception:
        return False


def finish(exc):
    """Called from the poster's __main__ in a finally block with the exception (or None)."""
    d = _claimed["date"]
    if d and exc is not None and not _claimed["past_point_of_no_return"] and not _claimed["completed"]:
        released = release(d, f"failed before publishing: {type(exc).__name__}")
        print(f"Claim for {d} {'released (nothing was published)' if released else 'could NOT be released; it will block re-runs until the owner clears it'}.", file=sys.stderr)


# ------------------------------------------------------------------ restore / save (workflow steps)
def restore():
    tip = fetch_tip()
    try:
        local = local_state()
    except GateError:
        local = {"posted": {}, "claims": {}}
    check_not_behind(local, tip)
    os.makedirs(os.path.dirname(FILE) or ".", exist_ok=True)
    with open(FILE + ".tmp", "w", encoding="utf-8") as f:
        f.write(dump(tip))
    os.replace(FILE + ".tmp", FILE)
    print(f"Post history restored from {REMOTE}/{BRANCH}.")


def status(date=None):
    if date is not None:
        check_date(date)
    """Read-only. Shows what the branch records so the owner can compare it with Threads. Exit codes with a DATE:
    0 posted, 11 claimed and unconfirmed, 3 nothing recorded (a released claim counts as nothing recorded)."""
    tip = fetch_tip()
    days = sorted(set(tip["posted"]) | set(tip["claims"]))
    def state_of(d):
        if d in confirmed_dates(tip):
            return "posted"
        c = tip["claims"].get(d, {})
        return c.get("status", "none")
    if date is None:
        shown = days[-14:]
        print(f"{len(tip['posted'])} posted day(s) recorded on {REMOTE}/{BRANCH}; last {len(shown)} day(s) with any record:")
        for d in shown:
            print(f"  {d}  {state_of(d)}")
        return 0
    st = state_of(date)
    print(f"{date}: {st}")
    return 0 if st == "posted" else (11 if st == "claimed" else 3)


def save():
    for attempt in (1, 2):
        try:
            tip = fetch_tip()
            merged = merge(tip, local_state())
            if merged == tip:
                print("Post history unchanged; nothing to save.")
                return
            if push_state(merged, "Record today's post"):
                print(f"Post history saved to {REMOTE}/{BRANCH}.")
                return
        except GateError as e:
            print(f"{e}", file=sys.stderr)
        print(f"Push failed on attempt {attempt}; fetching the latest and retrying.", file=sys.stderr)
    print(f"ERROR: could not save the post history to '{BRANCH}'. Do not re-run the post step today without checking Threads.", file=sys.stderr)
    sys.exit(1)


def export(out_path):
    """For a rollback to the old workflow: write the branch's post history in the old format (no claims) so it can be
    committed to main by pull request BEFORE the old workflow is restored. Refuses while any claim is unconfirmed."""
    tip = fetch_tip()
    open_claims = sorted(d for d, c in tip["claims"].items() if c.get("status") == "claimed")
    if open_claims:
        raise GateError(f"unconfirmed claim(s) for {', '.join(open_claims)}: check Threads, then record the post (complete) or release the claim")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({**{k: v for k, v in tip.items() if k != "claims"}}, indent=2) + "\n")
    print(f"Wrote {len(tip['posted'])} posted day(s) to {out_path}. Commit it to main by pull request before restoring the old workflow.")


def main(argv):
    cmd = argv[1] if len(argv) > 1 else ""
    try:
        if cmd in ("complete", "release", "status") and len(argv) > 2:
            check_date(argv[2])  # before anything is read or written
        if cmd == "restore":
            restore()
        elif cmd == "save":
            save()
        elif cmd == "claim":
            print(claim(argv[2], argv[3] if len(argv) > 3 else "local"))
        elif cmd == "complete":
            if len(argv) < 5:
                print("usage: poster_gate.py complete DATE ID LINK   (ID and LINK are on the live post in Threads; write 'unknown' if you cannot find the ID)", file=sys.stderr)
                sys.exit(2)
            complete(argv[2], {"id": argv[3], "permalink": argv[4], "at": now(), "recorded_by": "owner, by hand"})
            print(f"Recorded {argv[2]} as posted (today in the poster's timezone is {poster_today()}). Check it: python3 scripts/poster_gate.py status {argv[2]}")
        elif cmd == "status":
            sys.exit(status(argv[2] if len(argv) > 2 else None))
        elif cmd == "export":
            export(argv[2])
        elif cmd == "release":
            print("released" if release(argv[2], argv[3] if len(argv) > 3 else "manual") else "not released")
        else:
            print(__doc__)
            sys.exit(2)
    except UsageError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
    except Blocked as e:
        print(f"BLOCKED: {e}", file=sys.stderr)
        sys.exit(11)
    except GateError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(12 if cmd == "claim" else 1)


if __name__ == "__main__":
    main(sys.argv)
