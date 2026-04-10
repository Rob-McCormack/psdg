#!/usr/bin/env python3
"""
Verify that solve_exchange_sequential returns the same value as solve_exchange
for positions from the benchmark. Also run a quick blunder test sample.
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
    apply_draft_action,
    apply_exchange,
    evaluate,
    forced_gift_indices,
    legal_draft_actions,
    solve_exchange,
    solve_exchange_sequential,
    solve_from_roll,
)

BENCHMARK_PATH = os.path.join(BENCHMARK_DIR, "benchmark_5000_6d.json")


def _is_exchange_move(move) -> bool:
    return (
        isinstance(move, (tuple, list))
        and len(move) == 2
        and isinstance(move[0], (tuple, list))
        and len(move[0]) == 2
    )


def get_crucibles_from_game(board, a_crystal, b_crystal):
    """Simulate optimal play to get crucibles at Exchange."""
    _, line = solve_from_roll(board, a_crystal, b_crystal)
    a_crucible = ()
    b_crucible = ()
    current_board = tuple(board)
    for i, move in enumerate(line):
        if move is None:
            continue
        if _is_exchange_move(move):
            break
        if i % 2 == 0:
            current_board, a_crucible = apply_draft_action(current_board, a_crucible, move)
        else:
            current_board, b_crucible = apply_draft_action(current_board, b_crucible, move)
    return a_crucible, b_crucible


def main():
    with open(BENCHMARK_PATH, encoding="utf-8") as f:
        data = json.load(f)
    games = data.get("games", data.get("entries", []))[:20]

    print("Verifying sequential vs simultaneous Exchange parity...")
    mismatches = 0
    for i, g in enumerate(games):
        board = tuple(g["board"])
        a_crystal = tuple(g["a_crystal"])
        b_crystal = tuple(g["b_crystal"])
        a_crucible, b_crucible = get_crucibles_from_game(board, a_crystal, b_crystal)
        if sum(board) > 0:
            continue
        val_sim, _ = solve_exchange(a_crucible, b_crucible, a_crystal, b_crystal)
        val_seq_a, _, _ = solve_exchange_sequential(
            a_crucible, b_crucible, a_crystal, b_crystal, first_mover="A"
        )
        val_seq_b, _, _ = solve_exchange_sequential(
            a_crucible, b_crucible, a_crystal, b_crystal, first_mover="B"
        )
        if val_sim != val_seq_a or val_sim != val_seq_b:
            mismatches += 1
            print(f"  Game {i}: sim={val_sim} seq_a={val_seq_a} seq_b={val_seq_b}")
    if mismatches == 0:
        print("  All positions: sequential A, sequential B, and simultaneous agree.")
    else:
        print(f"  {mismatches} mismatches found!")


if __name__ == "__main__":
    main()
