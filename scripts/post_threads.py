#!/usr/bin/env python3
"""Post today's queued item to Threads. Standard library only.

Usage: post_threads.py [--dry-run] [--force] [--date YYYY-MM-DD]
  --dry-run  choose and validate the post, call no API, change nothing
  --force    ignore the 11am time gate (used for manual runs)
Env: THREADS_ACCESS_TOKEN (required for a real post)
Exit codes: 0 ok / nothing to do, 1 problem (GitHub emails you on failure).
"""
import argparse, json, os, sys, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent / "bloor-assets"
API = "https://graph.threads.net/v1.0"
MAX_TEXT = 500


def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def fail(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def call(method, path, params, token):
    params = dict(params, access_token=token)
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    req = urllib.request.Request(url if method == "POST" else f"{url}?{data.decode()}",
                                 data=data if method == "POST" else None, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        fail(f"Threads API {method} {path} -> {e.code}: {e.read().decode()[:500]}")


def wait_ready(cid, token):
    for _ in range(60):  # up to ~5 min, videos take a while
        s = call("GET", cid, {"fields": "status,error_message"}, token)
        if s.get("status") == "FINISHED":
            return
        if s.get("status") in ("ERROR", "EXPIRED"):
            fail(f"container {cid} failed: {s}")
        time.sleep(5)
    fail(f"container {cid} not ready after 5 minutes")


def choose(today):
    footer = load("config.json").get("footer", "")
    queue, manifest = load("queue.json")["posts"], load("manifest.json")["assets"]
    assets = {a["file"]: a for a in manifest}
    entry = next((p for p in queue if p["on"] == today), None)
    if entry is None:
        fail(f"nothing is queued for {today}. The queue has run out: ask Claude for the next batch.")
    entry = dict(entry, text=entry["text"] + ("\n\n" + footer if footer else ""))
    if len(entry["text"]) > MAX_TEXT:
        fail(f"post text is {len(entry['text'])} chars, Threads allows {MAX_TEXT}")
    media = []
    for f in entry.get("media", load("config.json").get("default_media", [])):
        a = assets.get(f)
        if a is None:
            fail(f"{f} is not in manifest.json")
        if not (ROOT / f).exists():
            fail(f"{f} is missing from the repo")
        if a.get("expires") and today > a["expires"]:
            fail(f"{f} expired on {a['expires']}: refusing to post it")
        media.append(a)
    return entry, media


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", action="store_true", help="verify the token only; posts nothing")
    ap.add_argument("--date")
    args = ap.parse_args()

    if args.check:
        token = os.environ.get("THREADS_ACCESS_TOKEN") or fail("THREADS_ACCESS_TOKEN is not set")
        me = call("GET", "me", {"fields": "id,username"}, token)
        print(f"Token works. Connected as @{me.get('username')} (id {me.get('id')}). Nothing posted.")
        return

    cfg, state = load("config.json"), load("state.json")
    now = datetime.now(ZoneInfo(cfg["timezone"]))
    today = args.date or now.strftime("%Y-%m-%d")

    # GitHub starts scheduled runs late, so the workflow starts early and waits for the target time.
    if not args.force and not args.dry_run and not args.date:
        h = cfg["post_hour_local"]
        if now.hour == h - 1 and now.minute >= 30 and not cfg.get("paused"):
            wait = (60 - now.minute) * 60 - now.second
            print(f"Early start ({now:%H:%M}). Waiting {wait // 60} min until {h}:00 Toronto.")
            time.sleep(wait)
            now = datetime.now(ZoneInfo(cfg["timezone"]))

    if cfg.get("paused") and not args.dry_run:
        print("Posting is paused (config.json). Nothing done.")
        return
    if not args.force and not args.dry_run and not (cfg["post_hour_local"] <= now.hour <= cfg["post_hour_local"] + 3):
        print(f"It is {now:%H:%M} in Toronto, outside the posting window. Nothing done.")
        return
    if today in state["posted"] and not args.dry_run:
        print(f"Already posted for {today}: {state['posted'][today].get('permalink')}")
        return

    entry, media = choose(today)
    base = cfg["raw_base_url"]
    print(f"Post for {today}:\n---\n{entry['text']}\n---\nmedia: {[m['file'] for m in media]}"
          f"  topic: {entry.get('topic_tag')}")
    if args.dry_run:
        print("Dry run: nothing posted.")
        return

    token = os.environ.get("THREADS_ACCESS_TOKEN") or fail("THREADS_ACCESS_TOKEN is not set")
    kind = lambda f: "VIDEO" if f.lower().endswith((".mp4", ".mov")) else "IMAGE"
    topic = {"topic_tag": entry["topic_tag"]} if entry.get("topic_tag") else {}

    def item(a, extra):
        k = kind(a["file"])
        p = {"media_type": k, "alt_text": a["alt_text"],
             ("video_url" if k == "VIDEO" else "image_url"): base + urllib.parse.quote(a["file"])}
        return call("POST", "me/threads", {**p, **extra}, token)["id"]

    if not media:
        cid = call("POST", "me/threads", {"media_type": "TEXT", "text": entry["text"], **topic}, token)["id"]
    elif len(media) == 1:
        cid = item(media[0], {"text": entry["text"], **topic})
    else:
        kids = [item(a, {"is_carousel_item": "true"}) for a in media]
        for k in kids:
            wait_ready(k, token)
        cid = call("POST", "me/threads", {"media_type": "CAROUSEL", "children": ",".join(kids),
                                          "text": entry["text"], **topic}, token)["id"]
    wait_ready(cid, token)
    pid = call("POST", "me/threads_publish", {"creation_id": cid}, token)["id"]
    link = call("GET", pid, {"fields": "permalink"}, token).get("permalink")
    state["posted"][today] = {"id": pid, "permalink": link,
                              "at": datetime.now(ZoneInfo(cfg["timezone"])).isoformat()}
    (ROOT / "state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(f"Posted: {link}")


if __name__ == "__main__":
    main()
