#!/usr/bin/env python3
"""
Cross-join: standard blunder trial (B off get_b_optimal last draft; A re-solves Exchange)
vs benchmark JSON root `value` (+1 A / 0 draw / -1 B).

Expectation: every trial where B wins (outcome -1) should have value == -1, if the
benchmark `value` and mid-game optimality agree. Mismatches flag principal-line /
solve_from_position inconsistencies (see output seeds).

Usage:
  python3 verify_blunder_root_value_crossjoin.py [benchmark_5000_6d.json]
"""

from __future__ import annotations

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_HERE)
BENCHMARK_DIR = os.path.join(REPO_ROOT, "benchmark")
SOLVERS_PYTHON = os.path.join(REPO_ROOT, "solvers", "python")
sys.path.insert(0, SOLVERS_PYTHON)

from blunder_test_benchmark import run_trial_b_blunders


def main() -> None:
    bench_path = (
        sys.argv[1]
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-")
        else os.path.join(BENCHMARK_DIR, "benchmark_5000_6d.json")
    )
    with open(bench_path) as f:
        data = json.load(f)
    games = data["games"]
    n = len(games)
    b_wins = 0
    violations: list[tuple[int, int]] = []
    for i, g in enumerate(games):
        board = tuple(g["board"])
        a_crystal = tuple(g["a_crystal"])
        b_crystal = tuple(g["b_crystal"])
        seed = g.get("seed", i)
        v_root = g["value"]
        outcome = run_trial_b_blunders(
            board, a_crystal, b_crystal, seed + 9999, use_static=False
        )
        if outcome == -1:
            b_wins += 1
            if v_root != -1:
                violations.append((seed, v_root))
        if (i + 1) % 500 == 0 or i + 1 == n:
            print(f"  {i + 1}/{n} done", flush=True)

    b_roots = sum(1 for g in games if g["value"] == -1)
    print()
    print("Blunder (re-solving) vs benchmark root value")
    print(f"  Games: {n}")
    print(f"  B wins (trial outcome -1): {b_wins}")
    print(f"  Root B-win count (value == -1): {b_roots}")
    print(f"  B wins with value != -1 (mismatches): {len(violations)}")
    if violations:
        print(f"  Mismatch seeds (seed, json value): {violations}")


if __name__ == "__main__":
    main()
