#!/usr/bin/env python3
"""
Blunder test on the 500-game benchmark.

B (opponent) blunders on last draft pick. Measures: when the opponent blunders,
how often does the blunderer beat the solver? (Solver re-solves at Exchange.)

Usage:
  python3 blunder_test_benchmark.py [benchmark_500_6d.json] [--limit N]
  python3 blunder_test_benchmark.py --print-outcomes  # A wins / draws / B wins + root→outcome transitions
  python3 blunder_test_benchmark.py --static      # Static: A from principal line, B best-responds (sequential)
  python3 blunder_test_benchmark.py --static --static-simultaneous-exchange  # Static: B plays Nash (simultaneous)
  python3 blunder_test_benchmark.py --sequential # Sequential Exchange (first mover commits, second best-responds)
  python3 blunder_test_benchmark.py --sequential --sequential-order B  # B moves first
  python3 blunder_test_benchmark.py --blunder A  # A blunders instead
"""

import json
import os
import random
import sys
from collections import Counter

_HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(_HERE)
BENCHMARK_DIR = os.path.join(REPO_ROOT, "benchmark")
SOLVERS_PYTHON = os.path.join(REPO_ROOT, "solvers", "python")
sys.path.insert(0, SOLVERS_PYTHON)

from solver import (
    PLAYER_A,
    PLAYER_B,
    apply_draft_action,
    apply_exchange,
    evaluate,
    forced_gift_indices,
    legal_draft_actions,
    side_faces,
    solve_exchange,
    solve_exchange_sequential,
    solve_from_position,
    solve_from_roll,
)


def _is_exchange_move(move) -> bool:
    return (
        isinstance(move, (tuple, list))
        and len(move) == 2
        and isinstance(move[0], (tuple, list))
        and len(move[0]) == 2
    )


def get_a_optimal_move(board, a_crucible, b_crucible, a_crystal, b_crystal):
    """Re-solve from this position (A to move); return A's optimal draft action."""
    _, line = solve_from_position(
        board, a_crucible, b_crucible, a_crystal, b_crystal, PLAYER_A
    )
    for m in line:
        if m is not None and not _is_exchange_move(m):
            return m
    return None


def get_b_optimal_move(board, a_crucible, b_crucible, a_crystal, b_crystal):
    """Re-solve from this position (B to move); return B's optimal draft action."""
    _, line = solve_from_position(
        board, a_crucible, b_crucible, a_crystal, b_crystal, PLAYER_B
    )
    for m in line:
        if m is not None and not _is_exchange_move(m):
            return m
    return None


def get_principal_exchange(line):
    """Extract (a_act, b_act) from principal line."""
    for m in line:
        if _is_exchange_move(m):
            return tuple(m[0]), tuple(m[1])
    return None, None


def run_trial_b_blunders(
    board,
    a_crystal,
    b_crystal,
    seed: int,
    use_static: bool = False,
    static_simultaneous_exchange: bool = False,
    sequential: bool = False,
    sequential_order: str = "A",
) -> int:
    """
    B blunders on last draft pick. A re-solves at Exchange.
    Returns outcome (+1 A wins, 0 draw, -1 B wins).
    """
    board = tuple(board)
    a_crystal = tuple(a_crystal)
    b_crystal = tuple(b_crystal)
    n_dice = sum(board)
    b_last_idx = n_dice - 1  # 0-indexed: B's last pick

    _, line = solve_from_roll(board, a_crystal, b_crystal)

    a_crucible = ()
    b_crucible = ()
    current_board = board

    for i, move in enumerate(line):
        if move is None:
            continue
        if _is_exchange_move(move):
            break
        if i % 2 == 0:  # A's move
            current_board, a_crucible = apply_draft_action(current_board, a_crucible, move)
        else:  # B's move
            if i == b_last_idx:
                break
            current_board, b_crucible = apply_draft_action(current_board, b_crucible, move)

    b_optimal = get_b_optimal_move(
        current_board, a_crucible, b_crucible, a_crystal, b_crystal
    )
    b_legal = legal_draft_actions(current_board)
    blunder_opts = [m for m in b_legal if m != b_optimal]
    if not blunder_opts:
        b_move = b_optimal
    else:
        rng = random.Random(seed)
        b_move = rng.choice(blunder_opts)

    _, b_crucible_final = apply_draft_action(current_board, b_crucible, b_move)

    if use_static:
        a_act, _ = get_principal_exchange(line)
        if a_act is None:
            val, joint = solve_exchange(a_crucible, b_crucible_final, a_crystal, b_crystal)
            a_act, b_act = joint[0] if joint else (None, None)
        elif static_simultaneous_exchange:
            # A commits wrong (from principal line); B plays Nash (doesn't observe A)
            _, joint = solve_exchange(a_crucible, b_crucible_final, a_crystal, b_crystal)
            _, b_act = joint[0] if joint else (None, None)
        else:
            # A commits wrong; B best-responds (sequential: B observes A)
            b_legal_actions = [
                (bi, bf)
                for bi in forced_gift_indices(b_crucible_final, b_crystal)
                for bf in side_faces(b_crucible_final[bi][0])
            ]
            best_for_b = 2
            b_act = b_legal_actions[0] if b_legal_actions else None
            for ba in b_legal_actions:
                a_new, b_new = apply_exchange(a_crucible, b_crucible_final, a_act, ba)
                v = evaluate(a_new, b_new, a_crystal, b_crystal)
                if v < best_for_b:
                    best_for_b = v
                    b_act = ba
    elif sequential:
        _, a_act, b_act = solve_exchange_sequential(
            a_crucible, b_crucible_final, a_crystal, b_crystal, first_mover=sequential_order
        )
    else:
        val, joint = solve_exchange(a_crucible, b_crucible_final, a_crystal, b_crystal)
        a_act, b_act = joint[0] if joint else (None, None)

    if a_act is None or b_act is None:
        return 0
    a_new, b_new = apply_exchange(a_crucible, b_crucible_final, a_act, b_act)
    return evaluate(a_new, b_new, a_crystal, b_crystal)


def run_trial_a_blunders(board, a_crystal, b_crystal, seed: int) -> int:
    """
    A blunders on last draft pick. Returns outcome (+1, 0, -1).
    """
    board = tuple(board)
    a_crystal = tuple(a_crystal)
    b_crystal = tuple(b_crystal)
    n_dice = sum(board)
    a_last_idx = n_dice - 2  # 0-indexed: A's last pick

    _, line = solve_from_roll(board, a_crystal, b_crystal)

    a_crucible = ()
    b_crucible = ()
    current_board = board

    for i, move in enumerate(line):
        if move is None:
            continue
        if _is_exchange_move(move):
            break
        if i % 2 == 0:  # A's move
            if i == a_last_idx:
                break
            current_board, a_crucible = apply_draft_action(current_board, a_crucible, move)
        else:
            current_board, b_crucible = apply_draft_action(current_board, b_crucible, move)

    a_optimal = get_a_optimal_move(
        current_board, a_crucible, b_crucible, a_crystal, b_crystal
    )
    a_legal = legal_draft_actions(current_board)
    blunder_opts = [m for m in a_legal if m != a_optimal]
    if not blunder_opts:
        a_move = a_optimal
    else:
        rng = random.Random(seed)
        a_move = rng.choice(blunder_opts)

    board_after_a, a_crucible_final = apply_draft_action(current_board, a_crucible, a_move)
    b_optimal = get_b_optimal_move(
        board_after_a, a_crucible_final, b_crucible, a_crystal, b_crystal
    )
    _, b_crucible_final = apply_draft_action(board_after_a, b_crucible, b_optimal)

    val, joint = solve_exchange(a_crucible_final, b_crucible_final, a_crystal, b_crystal)
    if not joint:
        return 0
    a_act, b_act = joint[0]
    a_new, b_new = apply_exchange(
        a_crucible_final, b_crucible_final, a_act, b_act
    )
    return evaluate(a_new, b_new, a_crystal, b_crystal)


def main():
    bench_path = (
        sys.argv[1]
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-")
        else os.path.join(BENCHMARK_DIR, "benchmark_5000_6d.json")
    )
    limit = None
    blunder_who = "B"
    use_static = False
    static_simultaneous_exchange = False
    sequential = False
    sequential_order = "A"
    print_outcomes = False
    i = 1
    while i < len(sys.argv):
        if sys.argv[i] == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == "--print-outcomes":
            print_outcomes = True
            i += 1
        elif sys.argv[i] == "--blunder" and i + 1 < len(sys.argv):
            blunder_who = sys.argv[i + 1].upper()
            i += 2
        elif sys.argv[i] == "--static":
            use_static = True
            i += 1
        elif sys.argv[i] == "--static-simultaneous-exchange":
            static_simultaneous_exchange = True
            i += 1
        elif sys.argv[i] == "--sequential":
            sequential = True
            i += 1
        elif sys.argv[i] == "--sequential-order" and i + 1 < len(sys.argv):
            sequential_order = sys.argv[i + 1].upper()
            i += 2
        elif not sys.argv[i].startswith("-"):
            bench_path = sys.argv[i]
            i += 1
        else:
            i += 1

    with open(bench_path, encoding="utf-8") as f:
        data = json.load(f)

    games = data.get("games", data.get("entries", []))
    if limit is not None:
        games = games[:limit]

    b_wins = 0
    a_wins = 0
    draws = 0
    trans = Counter()
    total = len(games)

    if blunder_who == "B":
        run_trial = lambda *a, **k: run_trial_b_blunders(
            *a,
            use_static=use_static,
            static_simultaneous_exchange=static_simultaneous_exchange,
            sequential=sequential,
            sequential_order=sequential_order,
            **k,
        )
    else:
        run_trial = run_trial_a_blunders

    for i, g in enumerate(games):
        board = tuple(g["board"])
        a_crystal = tuple(g["a_crystal"])
        b_crystal = tuple(g["b_crystal"])
        seed = g.get("seed", i)

        outcome = run_trial(board, a_crystal, b_crystal, seed + 9999)
        if outcome == -1:
            b_wins += 1
        elif outcome == 1:
            a_wins += 1
        else:
            draws += 1
        if print_outcomes:
            root_v = int(g["value"])
            trans[(root_v, int(outcome))] += 1

        if (i + 1) % 100 == 0 or i + 1 == total:
            print(f"  {i + 1}/{total} done", flush=True)

    pct = 100 * b_wins / total
    print()
    if blunder_who == "B":
        if use_static:
            mode = (
                "static + simultaneous Exchange (B plays Nash)"
                if static_simultaneous_exchange
                else "static + sequential Exchange (B best-responds)"
            )
        elif sequential:
            mode = f"sequential Exchange ({sequential_order} first)"
        else:
            mode = "re-solving at Exchange (simultaneous)"
        print(f"Blunder test (B blunders on last draft pick, A uses {mode}):")
        print(f"  Games: {total}")
        print(f"  B wins (blunderer beats solver): {b_wins} ({pct:.1f}%)")
        if print_outcomes and total:
            pa, pd, pb = 100 * a_wins / total, 100 * draws / total, 100 * b_wins / total
            print(f"  Outcomes: A wins {a_wins} ({pa:.1f}%)  draws {draws} ({pd:.1f}%)  B wins {b_wins} ({pb:.1f}%)")
            print("  Root value → realized outcome (benchmark JSON value / trial result):")
            for v in (1, 0, -1):
                for o in (1, 0, -1):
                    k = trans[(v, o)]
                    if k:
                        print(f"    v={v:+d} → {o:+d}: {k}")
            print(
                f"  Slippage from forced-win roots (v=+1): →draw {trans[(1, 0)]}, →B {trans[(1, -1)]} "
                f"(A no longer wins)"
            )
            print(
                f"  From draw roots (v=0): →B {trans[(0, -1)]} (lost draw), →A {trans[(0, 1)]}, →draw {trans[(0, 0)]}"
            )
    else:
        print("Blunder test (A blunders on last draft pick):")
        print(f"  Games: {total}")
        print(f"  B wins: {b_wins} ({pct:.1f}%)")


if __name__ == "__main__":
    main()
