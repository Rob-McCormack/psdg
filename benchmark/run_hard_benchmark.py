#!/usr/bin/env python3
"""
Run PSDG hard benchmark: 1000 games with random boards + random crystals.

Replicates Grok's research to verify locally. Tracks:
- TB depth (0, 1, or 2): did game reach Tie Tumble 1 or 2?
- Max regret sensitivity: max over A's moves of (max delta among legal actions)
- Co-optimal moves: count of decision points with multiple optimal actions
- Outcome, seed, board, crystals for reproducibility

Usage (from repository root):
  uv run python benchmark/run_hard_benchmark.py -n 1000 -d 6 -o psdg_1000_hard.json
  uv run python benchmark/run_hard_benchmark.py -n 100 --top 20  # Quick run, emit top 20 hardest
"""

import argparse
import json
import os
import random
import sys
from typing import Dict, List, Tuple

_here = os.path.dirname(os.path.abspath(__file__))
_solvers = os.path.join(_here, "..", "solvers", "python")
if _solvers not in sys.path:
    sys.path.insert(0, _solvers)

from solver import (
    apply_draft_action,
    apply_exchange,
    evaluate,
    evaluate_breakdown,
    forced_gift_indices,
    legal_draft_actions,
    random_board_n,
    replay_line,
    side_faces,
    solve_exchange,
    solve_from_roll,
)
from oracle import best_actions, delta, value


def random_crystal(seed: int) -> Tuple[int, int]:
    """Random Red Crystal: top 1..5, facing in side_faces(top)."""
    rng = random.Random(seed)
    top = rng.randint(1, 5)
    faces = side_faces(top)
    facing = rng.choice(faces)
    return (top, facing)


def run_game_instrumented(
    seed: int,
    n_dice: int,
) -> Dict:
    """
    Run one game with oracle vs oracle. Boards and both crystals randomized.
    Return per-game metrics: outcome, TB depth, max regret sensitivity, co-optimal count.
    """
    board = random_board_n(n_dice, seed)
    initial_board = board  # keep for output
    a_crystal = random_crystal(seed + 10000)
    b_crystal = random_crystal(seed + 20000)

    val, line = solve_from_roll(board, a_crystal, b_crystal)
    a_crucible, b_crucible = replay_line(board, line, a_crystal, b_crystal)
    bd = evaluate_breakdown(a_crucible, b_crucible, a_crystal, b_crystal)

    # TB depth: 0 = no tiebreak, 1 = TB1 resolved it, 2 = TB2 needed
    tb_depth = 0
    if bd["tiebreak"]:
        tb_depth = 1
        if "tumble2" in bd["tiebreak"]:
            tb_depth = 2

    # Walk the game as oracle A vs oracle B, record max regret sensitivity and co-optimal count
    max_regret_sensitivity = 0.0
    co_optimal_count = 0
    state = (board, (), (), a_crystal, b_crystal, 0)  # A to move

    while True:
        board, a_crucible, b_crucible, a_crystal, b_crystal, turn = state

        if sum(board) == 0 and len(a_crucible) == len(b_crucible) and len(a_crucible) > 0:
            # Exchange state
            state_full = (board, a_crucible, b_crucible, a_crystal, b_crystal, turn)
            acts = best_actions(state_full)
            co_optimal_count += max(0, len(acts) - 1)  # extra optimal options
            # Regret sensitivity: max delta over legal joint actions
            worst_d = 0
            for ai in forced_gift_indices(a_crucible, a_crystal):
                for af in side_faces(a_crucible[ai][0]):
                    a_act = (ai, af)
                    for bi in forced_gift_indices(b_crucible, b_crystal):
                        for bf in side_faces(b_crucible[bi][0]):
                            b_act = (bi, bf)
                            d = delta(state_full, (a_act, b_act))
                            worst_d = max(worst_d, d)
            max_regret_sensitivity = max(max_regret_sensitivity, worst_d)
            break  # Exchange ends game

        if turn == 0:  # A to move
            state_full = (board, a_crucible, b_crucible, a_crystal, b_crystal, turn)
            acts = best_actions(state_full)
            co_optimal_count += max(0, len(acts) - 1)
            legal = legal_draft_actions(board)
            worst_d = 0
            for a in legal:
                d = delta(state_full, a)
                worst_d = max(worst_d, d)
            max_regret_sensitivity = max(max_regret_sensitivity, worst_d)
            # Advance: A plays first optimal
            top, facing = acts[0]
            board, a_crucible = apply_draft_action(board, a_crucible, (top, facing))
            turn = 1
        else:
            state_full = (board, a_crucible, b_crucible, a_crystal, b_crystal, turn)
            acts = best_actions(state_full)
            top, facing = acts[0]
            board, b_crucible = apply_draft_action(board, b_crucible, (top, facing))
            turn = 0

        state = (board, a_crucible, b_crucible, a_crystal, b_crystal, turn)

    return {
        "seed": seed,
        "board": list(initial_board),
        "a_crystal": list(a_crystal),
        "b_crystal": list(b_crystal),
        "value": val,
        "tb_depth": tb_depth,
        "score": {
            "phase1": list(bd["phase1"]),
            "phase2": list(bd["phase2"]),
            "total": list(bd["total"]),
            "tiebreak": {k: list(v) for k, v in bd["tiebreak"].items()} if bd.get("tiebreak") else None,
        },
        "max_regret_sensitivity": round(max_regret_sensitivity, 4),
        "co_optimal_moves": co_optimal_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Run PSDG hard benchmark (random boards + crystals)")
    parser.add_argument("-n", "--num-games", type=int, default=100, help="Number of games")
    parser.add_argument("-d", "--dice", type=int, default=6, choices=[4, 6, 8], help="Dice per board")
    parser.add_argument("-s", "--seed-offset", type=int, default=0, help="Offset for game seeds")
    parser.add_argument("-o", "--output", type=str, default="psdg_hard.json", help="Output JSON path")
    parser.add_argument("--top", type=int, default=None, help="Emit top N hardest boards (TB2 + max regret)")
    args = parser.parse_args()

    print(f"Running {args.num_games} games @ {args.dice} dice (random boards + crystals)...")
    results = []
    for i in range(args.num_games):
        seed = args.seed_offset + i
        r = run_game_instrumented(seed, args.dice)
        results.append(r)
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{args.num_games} done")

    # Summary stats (aligned with historical JS --bench schema for analysis/graphing)
    n = args.num_games
    tb0 = sum(1 for r in results if r["tb_depth"] == 0)
    tb1 = sum(1 for r in results if r["tb_depth"] == 1)
    tb2 = sum(1 for r in results if r["tb_depth"] == 2)
    a_wins = sum(1 for r in results if r["value"] == 1)
    b_wins = sum(1 for r in results if r["value"] == -1)
    draws = sum(1 for r in results if r["value"] == 0)
    decided_by_tb2 = sum(1 for r in results if r["tb_depth"] == 2 and r["value"] != 0)
    avg_max_regret = sum(r["max_regret_sensitivity"] for r in results) / len(results)
    high_regret = sum(1 for r in results if r["max_regret_sensitivity"] >= 1.0)
    avg_coopt = sum(r["co_optimal_moves"] for r in results) / len(results)

    tb2_games = [r for r in results if r["tb_depth"] >= 2]
    tb2_avg_regret = sum(r["max_regret_sensitivity"] for r in tb2_games) / len(tb2_games) if tb2_games else 0

    pct = lambda x: round(100 * x / n, 1)
    out = {
        "meta": {
            "n_games": n,
            "dice": args.dice,
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
            "decided_by": {
                "raw_score": {"count": tb0, "pct": pct(tb0)},
                "tb1": {"count": tb1, "pct": pct(tb1)},
                "tb2": {"count": decided_by_tb2, "pct": pct(decided_by_tb2)},
                "draw": {"count": draws, "pct": pct(draws)},
            },
            "tiebreak_reached": {"tb1": tb1 + tb2, "tb2": tb2},
            "avg_max_regret_sensitivity": round(avg_max_regret, 2),
            "high_regret_count": high_regret,
            "high_regret_pct": pct(high_regret),
            "avg_co_optimal_moves": round(avg_coopt, 1),
            "tb2_avg_regret_sensitivity": round(tb2_avg_regret, 2),
        },
        "games": results,
    }

    out_path = args.output
    if not os.path.isabs(out_path):
        out_path = os.path.join(_here, out_path)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {out_path}")

    print("\n--- Summary ---")
    print(f"Outcomes:  A wins: {a_wins} ({pct(a_wins)}%)  B wins: {b_wins} ({pct(b_wins)}%)  Draws: {draws} ({pct(draws)}%)")
    print(f"Decided by:  Raw score: {tb0} ({pct(tb0)}%)  TB1: {tb1} ({pct(tb1)}%)  TB2: {decided_by_tb2} ({pct(decided_by_tb2)}%)  Draw: {draws} ({pct(draws)}%)")
    print(f"Tiebreak reached:  TB1: {tb1 + tb2} ({pct(tb1 + tb2)}%)  TB2: {tb2} ({pct(tb2)}%)")
    print(f"Avg max regret sensitivity: {avg_max_regret:.2f}")
    print(f"Games with high regret (≥1.0): {high_regret} ({pct(high_regret)}%)")
    print(f"Avg co-optimal moves per game: {avg_coopt:.1f}")
    if tb2_games:
        print(f"TB2 games avg regret sensitivity: {tb2_avg_regret:.2f} (vs {avg_max_regret:.2f} overall)")

    if args.top:
        # Top hardest: TB2 first, then by max regret
        hardest = sorted(results, key=lambda r: (-r["tb_depth"], -r["max_regret_sensitivity"]))[: args.top]
        print(f"\n--- Top {args.top} hardest boards (TB depth + max regret) ---")
        print("Seed | TB | MaxRegret | CoOpt | Value")
        for r in hardest:
            print(f"  {r['seed']:4} | {r['tb_depth']} | {r['max_regret_sensitivity']:.1f}      | {r['co_optimal_moves']:5} | {r['value']}")


if __name__ == "__main__":
    main()
