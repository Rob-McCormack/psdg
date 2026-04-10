#!/usr/bin/env python3
"""
Public benchmark: 5000 games, 6 dice, random crystals (seeds 42–5041).

Uses the same LCG parameters as the canonical 5000-game suite (interoperable with the reference JS runner where that exists).
Reproducible in pure Python. Re-solve checks: `verify_benchmark.py` on the emitted JSON.

Usage: python3 run_benchmark_500_6d.py [-o output.json] [-n N]
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_HERE)
BENCHMARK_DIR = os.path.join(REPO_ROOT, "benchmark")
SOLVERS_PYTHON = os.path.join(REPO_ROOT, "solvers", "python")
sys.path.insert(0, SOLVERS_PYTHON)

from solver import (
    board_from_tops,
    evaluate_breakdown,
    replay_line,
    solve_from_roll,
)

DEFAULT_GAMES = 5000
DICE = 6
SEED_START = 42


def make_rng(seed: int):
    """LCG: same multiplier and increment as the reference suite (ported from the historical JS runner)."""
    s = seed & 0xFFFFFFFF

    def next_():
        nonlocal s
        s = (s * 1664525 + 1013904223) & 0xFFFFFFFF
        return s / 4294967296

    return next_


def side_faces(top: int) -> tuple:
    return tuple(v for v in range(1, 7) if v not in (top, 7 - top))


def random_board_n(n: int, seed: int) -> tuple:
    """JS-compatible: same LCG, same formula."""
    rng = make_rng(seed)
    tops = tuple(int(rng() * 6) + 1 for _ in range(n))
    return board_from_tops(tops)


def random_crystal(rng) -> tuple:
    top = int(rng() * 5) + 1
    faces = side_faces(top)
    facing = faces[int(rng() * len(faces))]
    return (top, facing)


def main():
    output = os.path.join(BENCHMARK_DIR, "benchmark_5000_6d.json")
    n_games = DEFAULT_GAMES
    i = 1
    while i < len(sys.argv):
        if (sys.argv[i] in ("-o", "--output")) and i + 1 < len(sys.argv):
            output = sys.argv[i + 1]
            i += 2
        elif (sys.argv[i] in ("-n", "--games")) and i + 1 < len(sys.argv):
            n_games = int(sys.argv[i + 1])
            i += 2
        else:
            i += 1
    print(f"Running {n_games} games @ {DICE} dice, seeds {SEED_START}–{SEED_START + n_games - 1}...")
    games = []

    for i in range(n_games):
        seed = SEED_START + i
        board = random_board_n(DICE, seed)
        rng_a = make_rng(seed + 10000)
        rng_b = make_rng(seed + 20000)
        a_crystal = random_crystal(rng_a)
        b_crystal = random_crystal(rng_b)

        val, line = solve_from_roll(board, a_crystal, b_crystal)
        a_crucible, b_crucible = replay_line(board, line, a_crystal, b_crystal)
        bd = evaluate_breakdown(a_crucible, b_crucible, a_crystal, b_crystal)

        tb_depth = 0
        if bd.get("tiebreak"):
            tb = bd["tiebreak"]
            tb_depth = 3 if tb.get("tumble3") else (2 if tb.get("tumble2") else 1)

        games.append({
            "seed": seed,
            "board": list(board),
            "a_crystal": list(a_crystal),
            "b_crystal": list(b_crystal),
            "value": val,
            "tb_depth": tb_depth,
            "score": {
                "phase1": bd["phase1"],
                "phase2": bd["phase2"],
                "total": bd["total"],
            },
        })

        if (i + 1) % 100 == 0:
            print(f"  {i + 1}/{n_games} done")

    a_wins = sum(1 for g in games if g["value"] == 1)
    b_wins = sum(1 for g in games if g["value"] == -1)
    draws = sum(1 for g in games if g["value"] == 0)
    pct = lambda x: f"{(100 * x) / n_games:.1f}"

    out = {
        "meta": {
            "n_games": n_games,
            "dice": DICE,
            "seed_start": SEED_START,
            "seed_end": SEED_START + n_games - 1,
            "random_crystals": True,
        },
        "summary": {
            "outcomes": {
                "a_wins": a_wins,
                "b_wins": b_wins,
                "draws": draws,
                "a_wins_pct": pct(a_wins),
                "b_wins_pct": pct(b_wins),
                "draws_pct": pct(draws),
            },
        },
        "games": games,
    }

    out_path = os.path.abspath(output) if not os.path.isabs(output) else output
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)

    print(f"\nWrote {out_path}")
    print(f"Outcomes: A {a_wins} ({pct(a_wins)}%)  B {b_wins} ({pct(b_wins)}%)  Draws {draws} ({pct(draws)}%)")


if __name__ == "__main__":
    main()
