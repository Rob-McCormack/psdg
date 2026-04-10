#!/usr/bin/env python3
"""Compare Python solver results for 4-dice boards. Output: one JSON object per line."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from solver import solve_from_roll, board_from_tops

A_CRYSTAL = (4, 6)
B_CRYSTAL = (2, 1)  # (2,5) invalid: 5 is opposite 2

# Fixed 4-dice boards to test (board format: counts for tops 1-6)
import random
seen = set()
TEST_BOARDS = []
random.seed(42)
for _ in range(25):
    tops = tuple(random.randint(1, 6) for _ in range(4))
    board = tuple(board_from_tops(tops))
    if board not in seen:
        seen.add(board)
        TEST_BOARDS.append(board)
EXAMPLE = (2, 0, 2, 0, 0, 0)
if EXAMPLE not in seen:
    TEST_BOARDS.insert(0, EXAMPLE)

def main():
    for board in TEST_BOARDS:
        val, line = solve_from_roll(board, A_CRYSTAL, B_CRYSTAL)
        out = {"board": list(board), "value": val, "line": line}
        print(json.dumps(out, separators=(",", ":")))

if __name__ == "__main__":
    main()
