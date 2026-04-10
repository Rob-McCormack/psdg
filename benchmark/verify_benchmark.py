#!/usr/bin/env python3
"""
Verify PSDG benchmark by re-solving each entry and checking values match.

  python3 verify_benchmark.py benchmark/benchmark.json
"""

import json
import os
import sys

# Add solvers to path
_here = os.path.dirname(os.path.abspath(__file__))
_solvers = os.path.join(_here, "..", "solvers", "python")
if _solvers not in sys.path:
    sys.path.insert(0, _solvers)

from solver import random_board_n, side_faces, solve_from_roll


def _is_valid_crystal(c):
    """Crystal (top, facing): top 1..5, facing must be side face (not top or 7-top)."""
    if not isinstance(c, (tuple, list)) or len(c) != 2:
        return False
    top, facing = c[0], c[1]
    if top < 1 or top > 5:
        return False
    return facing in side_faces(top)


def main():
    if len(sys.argv) < 2:
        print("Usage: verify_benchmark.py <benchmark.json>")
        sys.exit(1)

    path = sys.argv[1]
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    crystals = data["crystals"]
    a_crystal = tuple(crystals["a"])
    b_crystal = tuple(crystals["b"])
    if not _is_valid_crystal(a_crystal) or not _is_valid_crystal(b_crystal):
        print("Invalid crystals: top must be 1-5, facing must be a side face (not top or 7-top).")
        print("  E.g. (1,6) invalid: 6 is opposite 1. (2,5) invalid: 5 is opposite 2.")
        sys.exit(1)
    entries = data["entries"]

    errors = []
    for e in entries:
        if e["source"] == "random":
            board = random_board_n(e["dice"], e["seed"])
        else:
            board = tuple(e["board"])

        val, _ = solve_from_roll(board, a_crystal, b_crystal)
        expected = e["value"]
        if val != expected:
            errors.append({
                "id": e["id"],
                "expected": expected,
                "got": val,
                "board": e["board"],
            })

    if errors:
        print(f"FAIL: {len(errors)} mismatches of {len(entries)} entries")
        for err in errors[:10]:
            print(f"  id={err['id']} expected={err['expected']} got={err['got']} board={err['board']}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
        sys.exit(1)

    print(f"OK: {len(entries)} entries verified")


if __name__ == "__main__":
    main()
