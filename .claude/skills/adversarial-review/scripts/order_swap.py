#!/usr/bin/env python3
"""Reconcile a comparative judgment that was made twice with the order swapped.

Judges tend to favour whichever option is shown first (position bias). So every comparison between two
options (two sources that disagree, two candidate values, a draft and its revision) is judged twice, once
as A-then-B and once as B-then-A. Only a preference that survives the swap counts.

Each judgment is a JSON object whose keys come in this order (reasoning before the result):
  {"order": ["opt-1", "opt-2"], "reasoning": "...", "preferred_position": 1 | 2 | "tie"}

Usage: order_swap.py --ab judgment_ab.json --ba judgment_ba.json
Exit code: 0 decided, 1 inconclusive.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "agents" / "02-verifier" / "lib"))
import vlib  # noqa: E402


def _winner(j):
    pos = j["preferred_position"]
    return None if pos == "tie" else j["order"][pos - 1]


def reconcile(ab, ba):
    for name, j in (("first", ab), ("second", ba)):
        if not vlib.reasoning_precedes(j, "preferred_position"):
            return {"reasoning": f"The {name} judgment is malformed: reasoning must come first and be non-empty.",
                    "result": "inconclusive", "winner": None, "note": "malformed_judgment"}
        if j["preferred_position"] not in (1, 2, "tie") or not isinstance(j.get("order"), list) or len(j["order"]) != 2:
            return {"reasoning": f"The {name} judgment needs order of two ids and preferred_position 1, 2 or 'tie'.",
                    "result": "inconclusive", "winner": None, "note": "malformed_judgment"}
    if ab["order"] != list(reversed(ba["order"])):
        return {"reasoning": "The second run did not present the same two options in the opposite order.",
                "result": "inconclusive", "winner": None, "note": "order_not_swapped"}
    wa, wb = _winner(ab), _winner(ba)
    if wa is not None and wa == wb:
        return {"reasoning": f"Both orders prefer {wa}; the preference survives the swap.", "result": "decided",
                "winner": wa, "note": "consistent"}
    if wa is None and wb is None:
        return {"reasoning": "Both orders found the options equal.", "result": "decided", "winner": None, "note": "tie"}
    if wa is not None and wb is not None and ab["preferred_position"] == ba["preferred_position"]:
        return {"reasoning": f"The judge picked position {ab['preferred_position']} both times, so it followed the position, "
                             "not the content.", "result": "inconclusive", "winner": None, "note": "position_bias_suspected"}
    return {"reasoning": "The two runs disagree (one found a winner, the other a tie, or they picked different options).",
            "result": "inconclusive", "winner": None, "note": "inconsistent"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ab", required=True)
    ap.add_argument("--ba", required=True)
    a = ap.parse_args()
    res = reconcile(vlib.read_json(a.ab), vlib.read_json(a.ba))
    print(vlib.dump(res), end="")
    sys.exit(0 if res["result"] == "decided" else 1)


if __name__ == "__main__":
    main()
