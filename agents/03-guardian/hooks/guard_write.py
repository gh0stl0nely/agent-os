#!/usr/bin/env python3
"""PreToolUse hook for Write, Edit, MultiEdit and NotebookEdit. PROPOSED by the Guardian; the owner installs it.

Blocks: content that looks like a secret, files that normally hold a credential (.env, keys), and edits to the
protected paths in policy.json. Exit 0 with no output = no objection (never an approval). Exit 2 = blocked.
"""
import os
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import guard_lib as g  # noqa: E402


def texts(tool_input):
    """Every piece of text the tool call would put into a file."""
    out = []
    for k in ("content", "new_string", "new_source"):
        if isinstance(tool_input.get(k), str):
            out.append(tool_input[k])
    for e in tool_input.get("edits") or []:
        if isinstance(e, dict) and isinstance(e.get("new_string"), str):
            out.append(e["new_string"])
    return out


def main():
    data = g.read_input()
    name = data.get("tool_name")
    if name not in (None, "Write", "Edit", "MultiEdit", "NotebookEdit"):
        sys.exit(0)
    ti = data.get("tool_input") or {}
    path = ti.get("file_path") or ti.get("notebook_path") or ""
    cwd = data.get("cwd") or os.getcwd()
    try:
        pol = g.load_policy()
    except RuntimeError as e:
        g.deny("policy-unreadable", str(e))
    root = g.repo_root(cwd)
    p = g.resolve(path, cwd) if path else None
    if p and g.is_protected(p, root, pol):
        g.deny("protected-path", f"{os.path.relpath(p, root)} is a protected path.", "Propose the change in agent-system/change-requests/ or ask the owner.")
    if path and g.risky_name(path) and not path.endswith((".example", ".sample", ".template")):
        g.deny("credential-file", f"'{os.path.basename(path)}' is a file that normally holds a secret. Credentials are the owner's to place (R5); write instructions instead.")
    body = "\n".join(texts(ti))
    if body:
        ok, f, err = g.run_scanner(["--text", "-"], cwd, stdin=body)
        if not ok:
            g.deny("scanner-unavailable", err)
        f = [x for x in f if x.get("rule") != "plan-handles-secret"]
        if f:
            g.deny("secret-in-content", g.describe(f) + ". Nothing was written.", "Remove the value; tell the owner to revoke it if it was ever real.")
    sys.exit(0)


if __name__ == "__main__":
    g.run(main)
