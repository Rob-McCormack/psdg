#!/usr/bin/env python3
"""Quick benchmark: run N solves in one process. CPython vs PyPy."""
import os
import sys
import time

SOLVERS = os.path.join(os.path.dirname(__file__), "..", "solvers", "python")
sys.path.insert(0, SOLVERS)
from solver import solve_from_roll, random_board_n

A_CRYSTAL = (1, 2)
B_CRYSTAL = (2, 1)

def bench(n_dice: int, n_runs: int) -> float:
    total = 0
    for i in range(n_runs):
        board = random_board_n(n_dice, i)
        t0 = time.perf_counter()
        solve_from_roll(board, A_CRYSTAL, B_CRYSTAL)
        total += time.perf_counter() - t0
    return total

if __name__ == "__main__":
    n_dice = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    n_runs = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    elapsed = bench(n_dice, n_runs)
    print(f"Python {sys.version.split()[0]}: {n_runs} solves @ {n_dice}d in {elapsed:.2f}s (avg {elapsed/n_runs:.2f}s)")
