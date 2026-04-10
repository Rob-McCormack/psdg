#!/usr/bin/env python3
"""
Fixed board + fixed crystals: enumerate every B last-draft pick (optimal + all blunders).

For each choice, report A's outcome under:
  - Re-solving at Exchange (equilibrium joint action)
  - Static principal-line Exchange (A commits to line; B best-responds)

Compares to the principal-line story: after a blunder, crucibles differ, so static A's
gift may be wrong for the true position.

Usage:
  python3 fixed_board_blunder_sweep.py
  python3 fixed_board_blunder_sweep.py --seed 42 --dice 6
  python3 fixed_board_blunder_sweep.py --board 0,1,1,2,1,1 --crystal-a 4,6 --crystal-b 2,1
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import random
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from solver import (
    apply_draft_action,
    apply_exchange,
    evaluate,
    forced_gift_indices,
    legal_draft_actions,
    random_board_n,
    side_faces,
    solve_exchange,
    solve_from_roll,
)

# solver-beaten-by-blunder.py is not a valid module name; load by path
_sbb_path = os.path.join(_HERE, "solver-beaten-by-blunder.py")
_sbb_spec = importlib.util.spec_from_file_location("solver_beaten_by_blunder", _sbb_path)
_sbb = importlib.util.module_from_spec(_sbb_spec)
assert _sbb_spec.loader is not None
_sbb_spec.loader.exec_module(_sbb)
get_b_optimal_move = _sbb.get_b_optimal_move
get_principal_exchange = _sbb.get_principal_exchange
play_until_b_last_turn = _sbb.play_until_b_last_turn

# Re-use same crystal RNG as solver-beaten-by-blunder
def _random_crystal(seed: int) -> tuple:
    rng = random.Random(seed)
    top = rng.randint(1, 5)
    faces = side_faces(top)
    return (top, rng.choice(faces))


def _outcome_after_b_pick(
    board_before,
    a_crucible,
    b_crucible,
    b_move,
    a_crystal,
    b_crystal,
    line,
    use_static: bool,
) -> int:
    _, b_crucible_after = apply_draft_action(board_before, b_crucible, b_move)

    if use_static:
        a_act, b_act = get_principal_exchange(line)
        if a_act is None:
            _, joint = solve_exchange(a_crucible, b_crucible_after, a_crystal, b_crystal)
            a_act = joint[0][0] if joint else None
        if a_act is not None:
            a_legal_idx = forced_gift_indices(a_crucible, a_crystal)
            if a_act[0] not in a_legal_idx:
                _, joint = solve_exchange(a_crucible, b_crucible_after, a_crystal, b_crystal)
                a_act = joint[0][0] if joint else a_act
            b_legal_actions = [
                (bi, bf)
                for bi in forced_gift_indices(b_crucible_after, b_crystal)
                for bf in side_faces(b_crucible_after[bi][0])
            ]
            best_for_b = 2
            b_act = b_legal_actions[0] if b_legal_actions else None
            for ba in b_legal_actions:
                a_new, b_new = apply_exchange(a_crucible, b_crucible_after, a_act, ba)
                v = evaluate(a_new, b_new, a_crystal, b_crystal)
                if v < best_for_b:
                    best_for_b = v
                    b_act = ba
        else:
            _, joint = solve_exchange(a_crucible, b_crucible_after, a_crystal, b_crystal)
            a_act, b_act = joint[0] if joint else (None, None)
    else:
        _, joint = solve_exchange(a_crucible, b_crucible_after, a_crystal, b_crystal)
        a_act, b_act = joint[0] if joint else (None, None)

    if a_act is None or b_act is None:
        return 0
    a_new, b_new = apply_exchange(a_crucible, b_crucible_after, a_act, b_act)
    return evaluate(a_new, b_new, a_crystal, b_crystal)


def _parse_board(s: str) -> tuple:
    parts = [int(x.strip()) for x in s.split(",")]
    if len(parts) != 6:
        raise SystemExit("board must be 6 integers: c1..c6 for tops 1..6")
    return tuple(parts)


def _parse_crystal(s: str) -> tuple:
    parts = [int(x.strip()) for x in s.split(",")]
    if len(parts) != 2:
        raise SystemExit("crystal must be top,facing")
    return tuple(parts)


def sweep_board(board: tuple, a_crystal: tuple, b_crystal: tuple, n_dice: int):
    """Returns (val_root, rows, b_opt, legal_count) where rows match single-run format."""
    if sum(board) != n_dice:
        raise ValueError(f"board sum {sum(board)} != n_dice {n_dice}")

    val_root, line = solve_from_roll(board, a_crystal, b_crystal)
    board_before, a_crucible, b_crucible, line = play_until_b_last_turn(board, line)

    b_opt = get_b_optimal_move(board_before, a_crucible, b_crucible, a_crystal, b_crystal)
    legal = legal_draft_actions(board_before)

    blunders = [m for m in legal if m != b_opt]
    choices = ([("optimal", b_opt)] if b_opt is not None else []) + [
        ("blunder", m) for m in blunders
    ]

    rows = []
    for label, move in choices:
        rs = _outcome_after_b_pick(
            board_before, a_crucible, b_crucible, move, a_crystal, b_crystal, line, False
        )
        st = _outcome_after_b_pick(
            board_before, a_crucible, b_crucible, move, a_crystal, b_crystal, line, True
        )
        rows.append((label, move, rs, st, st - rs))

    return val_root, rows, b_opt, len(legal)


def main():
    ap = argparse.ArgumentParser(description="Enumerate B last-pick blunders on a fixed board")
    ap.add_argument("--seed", type=int, default=42, help="Seed for board+crystals when not explicit")
    ap.add_argument("--dice", type=int, default=6, choices=[4, 6, 8])
    ap.add_argument("--board", type=str, default=None, help="Override: c1,c2,c3,c4,c5,c6")
    ap.add_argument("--crystal-a", type=str, default=None)
    ap.add_argument("--crystal-b", type=str, default=None)
    ap.add_argument(
        "--batch",
        type=int,
        default=0,
        help="If >0, run this many seeds from --seed upward (random board+crystals each); print aggregate",
    )
    args = ap.parse_args()

    if args.batch > 0:
        if args.board or args.crystal_a or args.crystal_b:
            raise SystemExit("--batch is only for random board+crystals per seed")
        total_bl = 0
        gaps_neg = 0
        seeds_with_any_gap_neg = 0
        blunder_outcome_changes = 0  # rs != st for at least one blunder row
        for i in range(args.batch):
            s = args.seed + i
            random.seed(s)
            board = random_board_n(args.dice, s)
            a_crystal = _random_crystal(s + 8000)
            b_crystal = _random_crystal(s + 8001)
            val_root, rows, _, _ = sweep_board(board, a_crystal, b_crystal, args.dice)
            bl = [r for r in rows if r[0] == "blunder"]
            for r in bl:
                total_bl += 1
                if r[4] < 0:
                    gaps_neg += 1
                if r[2] != r[3]:
                    blunder_outcome_changes += 1
            if any(r[4] < 0 for r in bl):
                seeds_with_any_gap_neg += 1

        print("Batch fixed-board blunder sweep (one random open per seed, enumerate B blunders)")
        print("=" * 60)
        print(f"dice: {args.dice}  seeds: {args.seed} .. {args.seed + args.batch - 1}  ({args.batch} boards)")
        print(f"total blunder rows enumerated: {total_bl}")
        print(f"rows where static A worse than re-solve (st-rs < 0): {gaps_neg}/{total_bl}")
        if total_bl:
            print(f"fraction st-rs<0: {100 * gaps_neg / total_bl:.2f}%")
        print(f"seeds with ≥1 blunder where st-rs < 0: {seeds_with_any_gap_neg}/{args.batch}")
        print(f"blunder rows where A's outcome differs (rs vs st): {blunder_outcome_changes}/{total_bl}")
        return

    random.seed(args.seed)

    if args.board:
        board = _parse_board(args.board)
    else:
        board = random_board_n(args.dice, args.seed)

    a_crystal = _parse_crystal(args.crystal_a) if args.crystal_a else _random_crystal(args.seed + 8000)
    b_crystal = _parse_crystal(args.crystal_b) if args.crystal_b else _random_crystal(args.seed + 8001)

    val_root, rows, b_opt, legal_n = sweep_board(board, a_crystal, b_crystal, args.dice)

    print("Fixed-board blunder sweep (B's last draft pick)")
    print("=" * 60)
    print(f"board (counts tops 1..6): {board}")
    print(f"a_crystal: {a_crystal}  b_crystal: {b_crystal}")
    print(f"game value from roll (A perspective): {val_root:+d}")
    print(f"legal last picks for B: {legal_n}  (including optimal)")
    print(f"B optimal (re-solve from node): {b_opt}")
    print()

    hdr = f"{'kind':<8} {'pick (top,facing)':<18} {'A_rs':>5} {'A_st':>5} {'st-rs':>6}"
    print(hdr)
    print("-" * len(hdr))
    for label, move, rs, st, gap in rows:
        print(f"{label:<8} {str(move):<18} {rs:>5d} {st:>5d} {gap:>6d}")

    # Summary stats (blunders only)
    bl = [r for r in rows if r[0] == "blunder"]
    if bl:
        gaps = [r[4] for r in bl]
        worse_static = sum(1 for g in gaps if g < 0)
        print()
        print("Summary (blunders only):")
        print(f"  Count: {len(bl)}")
        print(f"  Static worse for A than re-solve (st-rs < 0): {worse_static}/{len(bl)}")
        print(f"  Mean (st-rs): {sum(gaps)/len(gaps):+.3f}")
        rs_wins_blunder = sum(1 for r in bl if r[2] == 1)
        st_wins_blunder = sum(1 for r in bl if r[3] == 1)
        print(f"  A wins under re-solve after blunder: {rs_wins_blunder}/{len(bl)}")
        print(f"  A wins under static after blunder:   {st_wins_blunder}/{len(bl)}")

    opt_row = next((r for r in rows if r[0] == "optimal"), None)
    if opt_row:
        print()
        print("Optimal B pick row:")
        print(f"  re-solve A outcome: {opt_row[2]:+d}  static A outcome: {opt_row[3]:+d}  gap: {opt_row[4]:+d}")


if __name__ == "__main__":
    main()
