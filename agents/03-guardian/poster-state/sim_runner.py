#!/usr/bin/env python3
"""Runs a copy of scripts/post_threads.py against a FAKE Threads API. No network. Test helper for test_fail_closed.py.

  sim_runner.py SCRIPT [script args...]      env: SIM_WORLD=path to the world file, SIM_FAULT=name

The fake replaces urllib.request.urlopen, so the script's own call(), fail() and error handling run unchanged. The
"world" file is what is live on Threads; it survives between runs, like the real service. Faults:
  container-error   creating the media container fails with HTTP 500 (nothing is published)
  publish-timeout   the publish request TIMES OUT but the post IS live (the worst case: the client cannot know)
  publish-400       the publish request is rejected with HTTP 400 (nothing is published)
  permalink-500     the post is live, then reading its permalink fails with HTTP 500
"""
import io
import json
import os
import runpy
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.dont_write_bytecode = True
WORLD, FAULT = os.environ["SIM_WORLD"], os.environ.get("SIM_FAULT", "")


def world():
    try:
        return json.load(open(WORLD))
    except FileNotFoundError:
        return {"live": [], "containers": 0}


def save(w):
    json.dump(w, open(WORLD, "w"))


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): return False


def http_error(url, code):
    return urllib.error.HTTPError(url, code, "simulated", {}, io.BytesIO(b'{"error":"simulated"}'))


def fake_urlopen(req, timeout=None):
    url = req.full_url if hasattr(req, "full_url") else req
    path = urllib.parse.urlparse(url).path.split("/v1.0/")[-1]
    w = world()
    if path == "me" or path.startswith("me?"):
        out = {"id": "1", "username": "sim"}
    elif path == "me/threads":
        if FAULT == "container-error":
            raise http_error(url, 500)
        w["containers"] += 1
        save(w)
        out = {"id": f"c{w['containers']}"}
    elif path == "me/threads_publish":
        if FAULT == "publish-400":
            raise http_error(url, 400)
        pid = f"p{len(w['live']) + 1}"
        w["live"].append(pid)
        save(w)
        if FAULT == "publish-timeout":
            raise TimeoutError("simulated: the request timed out, the post is live")
        out = {"id": pid}
    elif path.startswith("c"):
        out = {"status": "FINISHED"}
    elif path.startswith("p"):
        if FAULT == "permalink-500":
            raise http_error(url, 500)
        out = {"permalink": f"https://example.invalid/t/{path}"}
    else:
        raise http_error(url, 404)
    return Resp(json.dumps(out).encode())


urllib.request.urlopen = fake_urlopen
script = os.path.abspath(sys.argv[1])
sys.argv = [script] + sys.argv[2:]
sys.path.insert(0, os.path.dirname(script))
os.environ.setdefault("THREADS_ACCESS_TOKEN", "synthetic-not-a-secret")
runpy.run_path(script, run_name="__main__")
