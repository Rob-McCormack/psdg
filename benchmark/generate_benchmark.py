#!/usr/bin/env python3
"""
Generate PSDG benchmark suite.

Creates JSON with seeded boards + oracle values. Run from repo root:
  python3 generate_benchmark.py -n 1000 -o benchmark/benchmark.json
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import List, Tuple

# Add solvers to path
_here = os.path.dirname(os.path.abspath(__file__))
_solvers = os.path.join(_here, "..", "solvers", "python")
if _solvers not in sys.path:
    sys.path.insert(0, _solvers)

from solver import (
    board_from_tops,
    evaluate_breakdown,
    random_board_n,
    replay_line,
    solve_from_roll,
)

# Default crystals (same as solver demo). (2,5) invalid: 5 is opposite 2.
A_CRYSTAL = (4, 6)
B_CRYSTAL = (2, 1)


def _score_for_json(bd: dict) -> dict:
    """Score breakdown, JSON-serializable (tuples → lists)."""
    out = {
        "phase1": list(bd["phase1"]),
        "phase2": list(bd["phase2"]),
        "total": list(bd["total"]),
        "tiebreak": None,
    }
    if bd.get("tiebreak"):
        out["tiebreak"] = {k: list(v) for k, v in bd["tiebreak"].items()}
    return out


def _tb_depth_from_breakdown(bd: dict) -> int:
    """0 = none, 1 = TB1, 2 = TB2, 3 = TB3."""
    if not bd.get("tiebreak"):
        return 0
    return 3 if "tumble3" in bd["tiebreak"] else (2 if "tumble2" in bd["tiebreak"] else 1)


def solve_board(board: Tuple[int, ...]) -> Tuple[int, int, dict]:
    """Return (value, tb_depth, score_breakdown) from initial roll."""
    val, line = solve_from_roll(board, A_CRYSTAL, B_CRYSTAL)
    a_crucible, b_crucible = replay_line(board, line, A_CRYSTAL, B_CRYSTAL)
    bd = evaluate_breakdown(a_crucible, b_crucible, A_CRYSTAL, B_CRYSTAL)
    tb_depth = _tb_depth_from_breakdown(bd)
    return val, tb_depth, bd


def generate_random_entries(n: int, dice: int = 8, seed_offset: int = 0) -> List[dict]:
    """Generate n random entries with seeds 0..n-1."""
    entries = []
    for i in range(n):
        seed = seed_offset + i
        board = random_board_n(dice, seed)
        value, tb_depth, bd = solve_board(board)
        entries.append({
            "id": seed,
            "seed": seed,
            "dice": dice,
            "board": list(board),
            "value": value,
            "tb_depth": tb_depth,
            "score": _score_for_json(bd),
            "source": "random",
        })
    return entries


def generate_curated_entries(start_id: int, max_dice: int = 8) -> List[dict]:
    """Add curated boards. start_id = first id for curated. max_dice: skip curated with more dice (8 is slow)."""
    from curated_boards import CURATED_4, CURATED_6, CURATED_8

    entries = []
    idx = start_id
    for boards, dice in [(CURATED_4, 4), (CURATED_6, 6), (CURATED_8, 8)]:
        if dice > max_dice:
            continue
        for board, note in boards:
            value, tb_depth, bd = solve_board(board)
            entries.append({
                "id": idx,
                "board": list(board),
                "value": value,
                "tb_depth": tb_depth,
                "score": _score_for_json(bd),
                "source": "curated",
                "note": note,
                "dice": sum(board),
            })
            idx += 1
    return entries


def main():
    parser = argparse.ArgumentParser(description="Generate PSDG benchmark")
    parser.add_argument("-n", "--num-random", type=int, default=50, help="Number of random boards")
    parser.add_argument("-d", "--dice", type=int, default=6, choices=[4, 6, 8], help="Dice per board (6=base, 4=fast, 8=slower)")
    parser.add_argument("--curated-max-dice", type=int, default=8, choices=[4, 6, 8], help="Max dice for curated boards (8 is slow)")
    parser.add_argument("-o", "--output", required=True, help="Output JSON path")
    parser.add_argument("-q", "--quiet", action="store_true", help="Less output")
    args = parser.parse_args()

    if not args.quiet:
        print("Generating benchmark...")
        print(f"  Random {args.dice}d: {args.num_random}")

    entries = generate_random_entries(args.num_random, dice=args.dice)
    curated = generate_curated_entries(len(entries), max_dice=args.curated_max_dice)

    if not args.quiet:
        print(f"  Curated: {len(curated)}")

    # Re-id curated to avoid collision
    for i, e in enumerate(curated):
        e["id"] = len(entries) + i
    entries.extend(curated)

    data = {
        "version": 1,
        "rules": "v1.13",
        "crystals": {"a": list(A_CRYSTAL), "b": list(B_CRYSTAL)},
        "generated": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entries": entries,
    }

    out_path = args.output
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    if not args.quiet:
        n = len(entries)
        a_wins = sum(1 for e in entries if e["value"] == 1)
        b_wins = sum(1 for e in entries if e["value"] == -1)
        draws = sum(1 for e in entries if e["value"] == 0)
        tb0 = sum(1 for e in entries if e.get("tb_depth", 0) == 0)
        tb1 = sum(1 for e in entries if e.get("tb_depth") == 1)
        tb2 = sum(1 for e in entries if e.get("tb_depth") == 2)
        tb3 = sum(1 for e in entries if e.get("tb_depth") == 3)
        decided_tb2 = sum(1 for e in entries if e.get("tb_depth") == 2 and e["value"] != 0)
        decided_tb3 = sum(1 for e in entries if e.get("tb_depth") == 3 and e["value"] != 0)
        pct = lambda x: f"{100 * x / n:.1f}"
        print(f"  Total: {n} | A wins: {a_wins} | B wins: {b_wins} | Draws: {draws}")
        print(f"  Outcomes:  A wins: {a_wins} ({pct(a_wins)}%)  B wins: {b_wins} ({pct(b_wins)}%)  Draws: {draws} ({pct(draws)}%)")
        print(f"  Decided by:  Raw: {tb0} ({pct(tb0)}%)  TB1: {tb1} ({pct(tb1)}%)  TB2: {decided_tb2} ({pct(decided_tb2)}%)  TB3: {decided_tb3} ({pct(decided_tb3)}%)  Draw: {draws} ({pct(draws)}%)")
        print(f"  Tiebreak reached:  TB1: {tb1 + tb2 + tb3} ({pct(tb1 + tb2 + tb3)}%)  TB2: {tb2 + tb3} ({pct(tb2 + tb3)}%)  TB3: {tb3} ({pct(tb3)}%)")
        print(f"  Wrote {out_path}")


if __name__ == "__main__":
    main()
