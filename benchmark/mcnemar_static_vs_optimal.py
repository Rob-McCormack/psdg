#!/usr/bin/env python3
"""
Paired discordant-cell (McNemar) analysis for the inversion claim:
  "static A (frozen principal-line Gift) loses to a *blundering* B
   MORE often than to an *optimal* B."

Two paired per-seed B-win indicators on the standard 5,000-game 6-dice suite:

  opt_B_win[i]    = (root value == -1)              # optimal-vs-optimal (the 399)
  static_B_win[i] = run_trial_b_blunders(static,    # static A + seeded blunder B,
                                         sequential) #   sequential Exchange (the 427)

Holding A's policy fixed at the frozen principal line, the only manipulated
variable is B (optimal -> forced last-draft blunder). On-path the frozen plan
equals optimal A, so opt_B_win is exactly the static-A-vs-optimal-B column.

Reports the exact 2x2, the discordant cells (b, c), the root-value breakdown of
the seeds that flip TO a B-win, and an exact McNemar (binomial) p-value as a
clearly-scoped *generalization* footnote -- the integer counts are exact on the
published seeds; the p-value only speaks to the setup-RNG population.
"""

import json
import os
import sys
from collections import Counter
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from blunder_test_benchmark import run_trial_b_blunders  # noqa: E402


def _worker(g):
    """Return (root_v, opt_B_win, static_B_win) for one game."""
    board = tuple(g["board"])
    a_crystal = tuple(g["a_crystal"])
    b_crystal = tuple(g["b_crystal"])
    seed = g["seed"]
    root_v = int(g["value"])
    outcome = run_trial_b_blunders(
        board, a_crystal, b_crystal, seed + 9999,
        use_static=True, static_simultaneous_exchange=False, sequential=False,
    )
    return root_v, (root_v == -1), (outcome == -1)


def exact_two_sided_binom_p(k: int, n: int) -> float:
    """Two-sided exact binomial p at prob 0.5 (McNemar exact)."""
    if n == 0:
        return 1.0
    from math import comb

    def pmf(j):
        return comb(n, j) * (0.5 ** n)

    p0 = pmf(k)
    # two-sided: sum of all outcomes at most as probable as observed
    return min(1.0, sum(pmf(j) for j in range(n + 1) if pmf(j) <= p0 + 1e-15))


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

    # 2x2 over (opt_B_win, static_B_win)
    n11 = n10 = n01 = n00 = 0
    flip_to_B_rootval = Counter()    # seeds that flip TO B-win under blunder+static
    flip_away_rootval = Counter()    # seeds that flip AWAY from B-win
    opt_B = 0
    static_B = 0

    with Pool() as pool:
        results = []
        for j, res in enumerate(pool.imap(_worker, games, chunksize=8)):
            results.append(res)
            if (j + 1) % 250 == 0 or j + 1 == total:
                print(f"  {j + 1}/{total} done", flush=True)

    for root_v, opt_B_win, static_B_win in results:
        opt_B += opt_B_win
        static_B += static_B_win
        if opt_B_win and static_B_win:
            n11 += 1
        elif opt_B_win and not static_B_win:
            n10 += 1
            flip_away_rootval[root_v] += 1
        elif (not opt_B_win) and static_B_win:
            n01 += 1
            flip_to_B_rootval[root_v] += 1
        else:
            n00 += 1

    b = n10  # B-win under optimal, NOT under blunder+static (blunder cost B the win)
    c = n01  # B-win under blunder+static, NOT under optimal  (blunder GAINED B a win)
    disc = b + c
    p = exact_two_sided_binom_p(max(b, c), disc)

    print()
    print("=" * 64)
    print("Paired 2x2: optimal-vs-optimal B-win  x  static/blunder B-win")
    print("=" * 64)
    print(f"  N seeds                         : {total}")
    print(f"  optimal-vs-optimal B wins       : {opt_B}   (expect 399)")
    print(f"  static+blunder (seq) B wins     : {static_B}   (expect 427)")
    print()
    print("                         static B-win   static NOT B-win")
    print(f"  optimal B-win        :   {n11:>6}        {n10:>6}   (= {opt_B})")
    print(f"  optimal NOT B-win    :   {n01:>6}        {n00:>6}")
    print(f"                            (= {static_B})")
    print()
    print(f"  Concordant (same in both)       : {n11 + n00}")
    print(f"  Discordant total                : {disc}")
    print(f"  b = flips AWAY from B-win        : {b}  (blunder COST B the win)")
    print(f"  c = flips TO   B-win             : {c}  (blunder GAINED B the win)")
    print(f"  net (c - b)                      : {c - b}")
    print()
    print("  Root-value breakdown of c (flips TO a B-win under static+blunder):")
    for v in (1, 0, -1):
        if flip_to_B_rootval[v]:
            label = {1: "A-win root", 0: "draw root", -1: "B-win root"}[v]
            print(f"    root value {v:+d} ({label:11}): {flip_to_B_rootval[v]}")
    print("  Root-value breakdown of b (flips AWAY from a B-win):")
    for v in (1, 0, -1):
        if flip_away_rootval[v]:
            label = {1: "A-win root", 0: "draw root", -1: "B-win root"}[v]
            print(f"    root value {v:+d} ({label:11}): {flip_away_rootval[v]}")
    print()
    print(f"  McNemar exact two-sided p (generalization footnote) : {p:.3e}")
    print("  NOTE: counts are EXACT on the published seeds + published blunder")
    print("        draw; p only addresses generalization to the setup-RNG")
    print("        population (and is conditional on the seeded blunder draw).")


if __name__ == "__main__":
    main()
