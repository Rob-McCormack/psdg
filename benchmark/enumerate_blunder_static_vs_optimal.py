#!/usr/bin/env python3
"""
Enumerated-blunder (draw-independent) version of the static-vs-optimal paired
analysis. Removes the single seeded-blunder-draw conditional of
`mcnemar_static_vs_optimal.py`.

At B's last draft pick exactly one board die remains, so B's "blunder" is a Twist
choice with up to ~3 suboptimal legal facings. Instead of sampling ONE (as the
published 427 suite does), we ENUMERATE every suboptimal last twist per seed and
compute the static-A (frozen principal-line Gift, sequential Exchange) outcome for
each.

Per seed we record:
  root_v        = optimal-vs-optimal root value (+1 A / 0 draw / -1 B)
  n_blunders    = number of suboptimal legal last twists
  n_bwin        = how many of them yield a realized B-win under static A

From these we report draw-independent metrics:

  EXPECTED (uniform over blunders, matching the suite's draw):
    expected static B-win count   = sum_seed (n_bwin / n_blunders)   [de-noised 427]
    expected 2x2 cells c, b, net  (non-integer expectations)

  EXISTENCE (fully draw-independent integer counts):
    # A-win openings (root +1) exploitable by AT LEAST ONE worse move  [the 116-analog]
    # B-win openings (root -1) where SOME blunder forfeits B's win
    distribution of per-seed exploit fractions
"""

import json
import os
import sys
from collections import Counter
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from blunder_test_benchmark import (  # noqa: E402
    get_b_optimal_move,
    get_principal_exchange,
)
from solver import (  # noqa: E402
    apply_draft_action,
    apply_exchange,
    evaluate,
    forced_gift_indices,
    legal_draft_actions,
    side_faces,
    solve_exchange,
    solve_from_roll,
)


def _is_exchange_move(move) -> bool:
    return (
        isinstance(move, (tuple, list))
        and len(move) == 2
        and isinstance(move[0], (tuple, list))
        and len(move[0]) == 2
    )


def _static_seq_outcome(a_crucible, b_crucible_final, a_act, a_crystal, b_crystal):
    """A plays frozen principal-line gift a_act; B best-responds (sequential)."""
    if a_act is None:
        _, joint = solve_exchange(a_crucible, b_crucible_final, a_crystal, b_crystal)
        a_act2, b_act = joint[0] if joint else (None, None)
        a_act = a_act2
    else:
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
    if a_act is None or b_act is None:
        return 0
    a_new, b_new = apply_exchange(a_crucible, b_crucible_final, a_act, b_act)
    return evaluate(a_new, b_new, a_crystal, b_crystal)


def _worker(g):
    board = tuple(g["board"])
    a_crystal = tuple(g["a_crystal"])
    b_crystal = tuple(g["b_crystal"])
    root_v = int(g["value"])
    n_dice = sum(board)
    b_last_idx = n_dice - 1

    _, line = solve_from_roll(board, a_crystal, b_crystal)

    a_crucible = ()
    b_crucible = ()
    current_board = board
    for i, move in enumerate(line):
        if move is None:
            continue
        if _is_exchange_move(move):
            break
        if i % 2 == 0:
            current_board, a_crucible = apply_draft_action(current_board, a_crucible, move)
        else:
            if i == b_last_idx:
                break
            current_board, b_crucible = apply_draft_action(current_board, b_crucible, move)

    b_optimal = get_b_optimal_move(current_board, a_crucible, b_crucible, a_crystal, b_crystal)
    b_legal = legal_draft_actions(current_board)
    blunder_opts = [m for m in b_legal if m != b_optimal]
    a_act, _ = get_principal_exchange(line)

    n_blunders = len(blunder_opts)
    n_bwin = 0
    for m in blunder_opts:
        _, b_crucible_final = apply_draft_action(current_board, b_crucible, m)
        outcome = _static_seq_outcome(
            a_crucible, b_crucible_final, a_act, a_crystal, b_crystal
        )
        if outcome == -1:
            n_bwin += 1
    return root_v, n_blunders, n_bwin


def main():
    bench_path = os.path.join(HERE, "benchmark_5000_6d.json")
    limit = None
    args = sys.argv[1:]
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])

    with open(bench_path, encoding="utf-8") as f:
        data = json.load(f)
    games = data["games"]
    if limit is not None:
        games = games[:limit]
    total = len(games)

    rows = []
    with Pool() as pool:
        for j, res in enumerate(pool.imap(_worker, games, chunksize=8)):
            rows.append(res)
            if (j + 1) % 250 == 0 or j + 1 == total:
                print(f"  {j + 1}/{total} done", flush=True)

    opt_B = sum(1 for v, _, _ in rows if v == -1)

    # EXPECTED (uniform over a seed's suboptimal twists)
    exp_static_B = 0.0
    exp_c = 0.0  # expected flips TO B-win   (root != -1)
    exp_b = 0.0  # expected flips AWAY        (root == -1)
    # EXISTENCE (draw-independent integer counts)
    exist_any = Counter()       # root_v -> # seeds with >=1 B-win blunder
    exist_all = Counter()       # root_v -> # seeds where ALL blunders -> B-win
    forced_optimal = 0          # seeds with no suboptimal last twist
    frac_buckets = Counter()    # bucket of exploit fraction among A-win roots
    awin_total = 0

    for v, nb, nbw in rows:
        if nb == 0:
            forced_optimal += 1
            # B forced to optimal; static == optimal == root value
            p = 1.0 if v == -1 else 0.0
        else:
            p = nbw / nb
        exp_static_B += p
        if v == -1:
            exp_b += (1.0 - p)
        else:
            exp_c += p
        if nb > 0 and nbw >= 1:
            exist_any[v] += 1
        if nb > 0 and nbw == nb:
            exist_all[v] += 1
        if v == 1:
            awin_total += 1
            if nb > 0:
                frac = nbw / nb
                if frac == 0:
                    frac_buckets["0 (no blunder exploits)"] += 1
                elif frac < 0.5:
                    frac_buckets["<50% of blunders exploit"] += 1
                elif frac < 1.0:
                    frac_buckets["50-99% of blunders exploit"] += 1
                else:
                    frac_buckets["100% (every blunder exploits)"] += 1

    print()
    print("=" * 66)
    print("Enumerated-blunder static-vs-optimal (draw-independent)")
    print("=" * 66)
    print(f"  N seeds                                  : {total}")
    print(f"  seeds with no suboptimal last twist      : {forced_optimal}")
    print(f"  optimal-vs-optimal B wins (root == -1)   : {opt_B}")
    print()
    print("  EXPECTED over uniform blunder draw (de-noises the sampled 427):")
    print(f"    expected static B-win count            : {exp_static_B:.1f}")
    print(f"    expected flips TO B-win   (c)          : {exp_c:.1f}")
    print(f"    expected flips AWAY       (b)          : {exp_b:.1f}")
    print(f"    expected net (c - b)                   : {exp_c - exp_b:+.1f}")
    print(f"    (sampled single-draw run gave: static 427, c=116, b=88, net +28)")
    print()
    print("  EXISTENCE (fully draw-independent integer counts):")
    for v in (1, 0, -1):
        lbl = {1: "A-win", 0: "draw ", -1: "B-win"}[v]
        print(f"    root {v:+d} ({lbl}): >=1 exploiting blunder : {exist_any[v]:>4}   "
              f"all blunders exploit: {exist_all[v]:>4}")
    print()
    print(f"  *** {exist_any[1]} A-win openings are beatable by AT LEAST ONE worse move ***")
    print(f"      (draw-independent analog of the sampled '116')")
    print()
    print(f"  Among the {awin_total} A-win openings, exploit-fraction profile:")
    for k in ("0 (no blunder exploits)", "<50% of blunders exploit",
              "50-99% of blunders exploit", "100% (every blunder exploits)"):
        if frac_buckets[k]:
            print(f"    {k:32}: {frac_buckets[k]}")


if __name__ == "__main__":
    main()
