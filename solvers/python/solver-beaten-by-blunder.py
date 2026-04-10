#!/usr/bin/env python3
"""
Solver Beaten by Blunder — Simple Combined Test

Tests whether a solver can lose to a weaker player (one who blunders late).

Uses random crystals per board (v1.13 setup). Same design as blunder_test_random_crystals.js.

Two conditions:
  1. Re-solving: Solver re-solves at every move (including Exchange). Guarantees at least game value.
  2. Static: Solver follows initial principal line only. No re-solving.

B (opponent) blunders on their last draft pick. We compare solver (A) win rate.

If static loses more than re-solving → blunder can defeat the solver (static-line vulnerability).
If re-solving still loses sometimes → mixed-strategy variance (weaker player gets lucky).

Usage:
  python3 solver-beaten-by-blunder.py [--trials N] [--dice 4|6|8] [--seed N]
  python3 solver-beaten-by-blunder.py --trials 50 --dice 6 --seed 42 --checkpoint blunder-6dice.json

With --checkpoint FILE: writes after each trial, resumes from FILE if it exists (deterministic seed).
"""

import argparse
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from solver import (
    PLAYER_B,
    apply_draft_action,
    apply_exchange,
    evaluate,
    forced_gift_indices,
    legal_draft_actions,
    random_board_n,
    side_faces,
    solve_exchange,
    solve_from_position,
    solve_from_roll,
    total_score,
)


def _random_crystal(seed: int) -> tuple:
    """Random Red Crystal: top 1..5, facing in side_faces(top). Matches v1.13 setup."""
    rng = random.Random(seed)
    top = rng.randint(1, 5)
    faces = side_faces(top)
    return (top, rng.choice(faces))


def _is_exchange_move(move) -> bool:
    return (
        isinstance(move, (tuple, list))
        and len(move) == 2
        and isinstance(move[0], (tuple, list))
        and len(move[0]) == 2
    )


def play_until_b_last_turn(board, line):
    """
    Play principal line until just before B's last pick.
    Returns (board, a_crucible, b_crucible, line) at that position.
    """
    a_crucible = ()
    b_crucible = ()
    current_board = board
    move_idx = 0

    # Count draft moves: 4-dice = 4 picks, 8-dice = 8 picks. B's last is at odd index.
    n_dice = sum(board)
    b_last_idx = n_dice - 1  # 0-indexed: last move overall is B's last

    for i, move in enumerate(line):
        if move is None:
            continue
        if _is_exchange_move(move):
            break
        if i % 2 == 0:  # A's move
            current_board, a_crucible = apply_draft_action(current_board, a_crucible, move)
        else:  # B's move
            if i == b_last_idx:
                # This would be B's last move; we stop BEFORE playing it
                return (current_board, a_crucible, b_crucible, line)
            current_board, b_crucible = apply_draft_action(current_board, b_crucible, move)
    return (current_board, a_crucible, b_crucible, line)


def get_b_optimal_move(board, a_crucible, b_crucible, a_crystal, b_crystal):
    """Re-solve from this position (B to move); return B's optimal draft action."""
    _, line = solve_from_position(
        board, a_crucible, b_crucible, a_crystal, b_crystal, PLAYER_B
    )
    # First element of line is B's move (B to move)
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


def run_trial(
    seed: int,
    n_dice: int,
    use_static: bool,
    b_blunders: bool,
    record_tiebreaker: bool = False,
) -> tuple:
    """
    Run one trial.
    Returns (outcome,) where outcome is +1 if A wins, -1 if B wins, 0 draw.
    If record_tiebreaker: returns (outcome, used_tiebreaker) where used_tiebreaker
    is True when raw Phase1+Phase2 scores were tied (tiebreaker decided the game).
    use_static: if True, A follows principal line at Exchange; else re-solves.
    b_blunders: if True, B blunders on last pick; else B plays optimal.
    """
    random.seed(seed)
    board = random_board_n(n_dice, seed)
    a_crystal = _random_crystal(seed + 8000)
    b_crystal = _random_crystal(seed + 8001)

    # Solve from start -> principal line
    _, line = solve_from_roll(board, a_crystal, b_crystal)

    # Play until just before B's last pick
    board_before, a_crucible, b_crucible, _ = play_until_b_last_turn(board, line)

    b_optimal = get_b_optimal_move(
        board_before, a_crucible, b_crucible, a_crystal, b_crystal
    )
    b_legal = legal_draft_actions(board_before)

    if b_blunders:
        b_blunder_options = [m for m in b_legal if m != b_optimal]
        if not b_blunder_options:
            # Only one legal move (e.g. one die, one facing) - no blunder possible
            b_move = b_optimal
        else:
            b_move = random.choice(b_blunder_options)
    else:
        b_move = b_optimal

    # Apply B's last move
    _, b_crucible = apply_draft_action(board_before, b_crucible, b_move)

    # A's crucible unchanged (A already made all picks before B's last)
    # Draft complete. Now Exchange.
    if use_static:
        a_act, b_act = get_principal_exchange(line)
        # A plays a_act. B plays optimal for B (minimizes A's payoff) given actual crucibles
        if a_act is None:
            # Fallback: solve for A
            _, joint = solve_exchange(a_crucible, b_crucible, a_crystal, b_crystal)
            a_act = joint[0][0] if joint else None
        if a_act is not None:
            # Check a_act still legal (A's crucible unchanged so should be)
            a_legal_idx = forced_gift_indices(a_crucible, a_crystal)
            if a_act[0] not in a_legal_idx:
                # Principal line exchange invalid for A (shouldn't happen if crucible same)
                _, joint = solve_exchange(a_crucible, b_crucible, a_crystal, b_crystal)
                a_act = joint[0][0] if joint else a_act
            # B plays best response to A's a_act
            b_legal_actions = [
                (bi, bf)
                for bi in forced_gift_indices(b_crucible, b_crystal)
                for bf in side_faces(b_crucible[bi][0])
            ]
            best_for_b = 2
            b_act = b_legal_actions[0] if b_legal_actions else None
            for ba in b_legal_actions:
                a_new, b_new = apply_exchange(a_crucible, b_crucible, a_act, ba)
                v = evaluate(a_new, b_new, a_crystal, b_crystal)
                if v < best_for_b:
                    best_for_b = v
                    b_act = ba
        else:
            _, joint = solve_exchange(a_crucible, b_crucible, a_crystal, b_crystal)
            a_act, b_act = joint[0] if joint else (None, None)
    else:
        # Re-solving: both play equilibrium
        _, joint = solve_exchange(a_crucible, b_crucible, a_crystal, b_crystal)
        a_act, b_act = joint[0] if joint else (None, None)

    if a_act is None or b_act is None:
        return (0, False) if record_tiebreaker else 0

    a_new, b_new = apply_exchange(a_crucible, b_crucible, a_act, b_act)
    outcome = evaluate(a_new, b_new, a_crystal, b_crystal)
    if record_tiebreaker:
        a_total = total_score(a_crystal[0], a_new)
        b_total = total_score(b_crystal[0], b_new)
        used_tiebreaker = a_total == b_total
        return outcome, used_tiebreaker
    return outcome


def main():
    parser = argparse.ArgumentParser(
        description="Test: Can a blunder defeat the solver?"
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=500,
        help="Trials per condition (default 500)",
    )
    parser.add_argument(
        "--dice",
        type=int,
        choices=[4, 6, 8],
        default=6,
        help="Dice count (6 is base; 4 is fast)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base random seed",
    )
    parser.add_argument("--opinion", action="store_true", help="Print likelihood opinion")
    parser.add_argument("--json", action="store_true", help="Output JSON line only (for batch aggregation)")
    parser.add_argument(
        "--checkpoint",
        type=str,
        default=None,
        help="Write results after each trial; resume from this file if it exists",
    )
    parser.add_argument(
        "--tiebreak",
        action="store_true",
        help="Record whether each game was decided by tiebreaker (raw scores tied)",
    )
    args = parser.parse_args()

    if args.opinion:
        print(OPINION_LIKELIHOOD)
        return

    n = args.trials
    n_dice = args.dice
    base_seed = args.seed
    json_only = args.json
    checkpoint_file = args.checkpoint
    record_tiebreak = args.tiebreak

    # Load checkpoint if resuming
    results = []  # list of (rs_opt, rs_bl, st_opt, st_bl) or with _tb fields
    if checkpoint_file and os.path.isfile(checkpoint_file):
        import json
        with open(checkpoint_file) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                    if "rs_opt_tb" in row:
                        results.append((
                            row["rs_opt"], row["rs_bl"], row["st_opt"], row["st_bl"],
                            row["rs_opt_tb"], row["rs_bl_tb"], row["st_opt_tb"], row["st_bl_tb"],
                        ))
                    else:
                        tup = (row["rs_opt"], row["rs_bl"], row["st_opt"], row["st_bl"])
                        if record_tiebreak:
                            results.append(tup + (False, False, False, False))  # unknown
                        else:
                            results.append(tup)
                except (json.JSONDecodeError, KeyError):
                    pass
        if not json_only and results:
            print(f"Resuming: {len(results)} trials already in {checkpoint_file}")

    if not json_only:
        print("Solver Beaten by Blunder — Simple Combined Test")
        print("=" * 50)
        print(f"Trials per condition: {n}")
        print(f"Dice: {n_dice}")
        print(f"B blunders on last draft pick (alternative facing/top)")
        if record_tiebreak:
            print("Tiebreaker tracking: ON (recording when raw scores tied)")
        if checkpoint_file:
            print(f"Checkpoint: {checkpoint_file}")
        print()

    # Run trials (skip already completed)
    for i in range(len(results), n):
        seed = base_seed + i
        if record_tiebreak:
            rs_opt, rs_opt_tb = run_trial(seed, n_dice, use_static=False, b_blunders=False, record_tiebreaker=True)
            rs_bl, rs_bl_tb = run_trial(seed, n_dice, use_static=False, b_blunders=True, record_tiebreaker=True)
            st_opt, st_opt_tb = run_trial(seed, n_dice, use_static=True, b_blunders=False, record_tiebreaker=True)
            st_bl, st_bl_tb = run_trial(seed, n_dice, use_static=True, b_blunders=True, record_tiebreaker=True)
            results.append((rs_opt, rs_bl, st_opt, st_bl, rs_opt_tb, rs_bl_tb, st_opt_tb, st_bl_tb))
        else:
            rs_opt = run_trial(seed, n_dice, use_static=False, b_blunders=False)
            rs_bl = run_trial(seed, n_dice, use_static=False, b_blunders=True)
            st_opt = run_trial(seed, n_dice, use_static=True, b_blunders=False)
            st_bl = run_trial(seed, n_dice, use_static=True, b_blunders=True)
            results.append((rs_opt, rs_bl, st_opt, st_bl))

        if checkpoint_file:
            import json
            row = {"i": i, "seed": seed, "rs_opt": rs_opt, "rs_bl": rs_bl, "st_opt": st_opt, "st_bl": st_bl}
            if record_tiebreak:
                row["rs_opt_tb"] = rs_opt_tb
                row["rs_bl_tb"] = rs_bl_tb
                row["st_opt_tb"] = st_opt_tb
                row["st_bl_tb"] = st_bl_tb
            with open(checkpoint_file, "a") as f:
                f.write(json.dumps(row) + "\n")
            if not json_only and (i + 1) % 5 == 0:
                print(f"  ... trial {i+1}/{n} done (checkpointed)")

    # Unpack results (handle both 4-tuple and 8-tuple)
    def unpack(r):
        return (r[0], r[1], r[2], r[3]) if len(r) == 4 else (r[0], r[1], r[2], r[3])

    wins_rs_opt = sum(1 for r in results if unpack(r)[0] == 1)
    wins_rs_bl = sum(1 for r in results if unpack(r)[1] == 1)
    wins_st_opt = sum(1 for r in results if unpack(r)[2] == 1)
    wins_st_bl = sum(1 for r in results if unpack(r)[3] == 1)

    if not json_only:
        print()
        print("Analysis:")
        delta_blunder_rs = (wins_rs_bl - wins_rs_opt) / n * 100
        delta_blunder_st = (wins_st_bl - wins_st_opt) / n * 100
        delta_static = (wins_st_opt - wins_rs_opt) / n * 100
        delta_static_vs_blunder = (wins_st_bl - wins_rs_bl) / n * 100

        print(f"  When B blunders, re-solving A gains {delta_blunder_rs:+.1f}pp (expect >=0)")
        print(f"  When B blunders, static A changes by {delta_blunder_st:+.1f}pp")
        print(f"  Static vs re-solving (B optimal): {delta_static:+.1f}pp")
        print(f"  Static vs re-solving (B blunders): {delta_static_vs_blunder:+.1f}pp")

        if wins_st_bl < wins_rs_bl:
            print()
            print(">>> Static solver loses MORE when B blunders (vulnerability confirmed)")
        if sum(1 for r in results if unpack(r)[1] == -1) > 0:
            print()
            print(">>> Re-solving A sometimes loses to blundering B (variance or game-theoretic loss)")

        # Tiebreaker summary
        if record_tiebreak and all(len(r) == 8 for r in results):
            tb_rs_opt = sum(1 for r in results if r[4])
            tb_rs_bl = sum(1 for r in results if r[5])
            tb_st_opt = sum(1 for r in results if r[6])
            tb_st_bl = sum(1 for r in results if r[7])
            print()
            print("Tiebreaker (raw scores tied):")
            print(f"  Re-solving vs optimal B:     {tb_rs_opt}/{n} games")
            print(f"  Re-solving vs blundering B: {tb_rs_bl}/{n} games")
            print(f"  Static vs optimal B:         {tb_st_opt}/{n} games")
            print(f"  Static vs blundering B:     {tb_st_bl}/{n} games")

    if json_only:
        import json
        print(json.dumps({
            "n": n, "dice": n_dice, "seed": base_seed,
            "wins_rs_opt": wins_rs_opt, "wins_rs_bl": wins_rs_bl,
            "wins_st_opt": wins_st_opt, "wins_st_bl": wins_st_bl,
        }))


OPINION_LIKELIHOOD = """
Opinion: How likely is "solver loses to weaker player"?

  Static-line vulnerability: MODERATE-HIGH
    When the solver follows a precomputed principal line and doesn't re-solve,
    opponent blunders change the crucibles. The solver's Exchange choice was
    optimal for the principal-line crucibles, not the actual crucibles. Expect a
    measurable gap (on the order of a few %) — as seen in this test.

  Mixed-strategy variance: LOW-MODERATE (unknown without checking)
    If the Exchange subgame often requires mixed equilibria, then even optimal
    play has irreducible variance. The weaker player (who blundered) has lower
    expected value but can still win individual games by luck. Need to sample
    Exchange matrices to see how often mixed strategies are required.

  Overall: The phenomenon is real for static solvers. For re-solving solvers,
  any "losses to weaker player" in this test are mostly game-theoretic — A
  was already losing from the start. True "weaker beats stronger" from pure
  variance would require mixed equilibria in the Exchange.
"""


if __name__ == "__main__":
    main()
