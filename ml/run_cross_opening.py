"""Cross-opening replication of the Exchange aliasing effect (the gating test).

For many random openings (board + crystals), compute the win/loss tops-only
aliasing floor and conflict-group count at the Exchange, then report the
distribution and where the demo board (floor 0.021, 4/14 groups) sits.

Within a single opening the crystals are constant, so grouping exchange states
by (a_tops, b_tops) is the correct tops-only aliasing (only crucible facings
are dropped; crystals, being observable and fixed per game, stay implicit).
"""

import os
import random
import sys
import time
from collections import defaultdict
from multiprocessing import Pool

_SOLVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "solvers", "python")
_SOLVER_DIR = os.path.normpath(_SOLVER_DIR)
if _SOLVER_DIR not in sys.path:
    sys.path.insert(0, _SOLVER_DIR)

from solver import (  # noqa: E402
    apply_draft_action,
    apply_exchange,
    evaluate,
    forced_gift_indices,
    legal_draft_actions,
    side_faces,
    solve_from_roll,
)

N_OPENINGS = 120
DICE = 6


def random_opening(rng):
    tops = [rng.randint(1, 6) for _ in range(DICE)]
    board = tuple(tops.count(v) for v in range(1, 7))

    def crystal():
        t = rng.randint(1, 5)  # crystal top never 6
        return (t, rng.choice(side_faces(t)))

    return board, crystal(), crystal()


def exchange_floor(board, a_cry, b_cry):
    # enumerate reachable exchange states
    visited = {(board, (), ())}
    stack = [(board, (), ())]
    exch = []
    while stack:
        bd, a, b = stack.pop()
        if sum(bd) == 0:
            exch.append((a, b))
            continue
        amove = (len(a) + len(b)) % 2 == 0
        for act in legal_draft_actions(bd):
            if amove:
                nb, na = apply_draft_action(bd, a, act)
                ns = (nb, na, b)
            else:
                nb, nbb = apply_draft_action(bd, b, act)
                ns = (nb, a, nbb)
            if ns not in visited:
                visited.add(ns)
                stack.append(ns)
    exch = list(set(exch))

    groups = defaultdict(list)
    for (a, b) in exch:
        bl = [(bi, bf) for bi in forced_gift_indices(b, b_cry) for bf in side_faces(b[bi][0])]
        guar = {}
        for ai in forced_gift_indices(a, a_cry):
            for af in side_faces(a[ai][0]):
                guar[(ai, af)] = min(
                    evaluate(*apply_exchange(a, b, (ai, af), bb), a_cry, b_cry) for bb in bl
                )
        vstar = max(guar.values())
        blind = {}
        for (ai, af), gv in guar.items():
            k = (a[ai][0], af)
            blind[k] = max(gv, blind.get(k, -99))
        opt = {k for k, gv in blind.items() if gv == vstar}
        regs = {k: vstar - gv for k, gv in blind.items()}
        tkey = (tuple(t for t, _ in a), tuple(t for t, _ in b))
        groups[tkey].append((opt, regs))

    aliased = conflict = 0
    floor_total = members_total = 0.0
    for members in groups.values():
        if len(members) > 1:
            aliased += 1
        inter = None
        for opt, _ in members:
            inter = opt if inter is None else inter & opt
        if len(members) > 1 and not inter:
            conflict += 1
        cands = set()
        for _, regs in members:
            cands |= set(regs.keys())
        best = min((sum(regs.get(c, 99) for _, regs in members)) for c in cands)
        floor_total += best
        members_total += len(members)
    return len(exch), len(groups), aliased, conflict, floor_total / members_total


def worker(args):
    board, a_cry, b_cry = args
    root_v, _ = solve_from_roll(board, a_cry, b_cry)
    n_states, n_groups, aliased, conflict, floor = exchange_floor(board, a_cry, b_cry)
    return dict(root_v=root_v, n_states=n_states, n_groups=n_groups,
                aliased=aliased, conflict=conflict, floor=floor)


def main():
    rng = random.Random(2026)
    openings = [random_opening(rng) for _ in range(N_OPENINGS)]

    t0 = time.perf_counter()
    results = []
    with Pool() as pool:
        for i, r in enumerate(pool.imap_unordered(worker, openings, chunksize=2)):
            results.append(r)
            if (i + 1) % 10 == 0 or i + 1 == N_OPENINGS:
                print(f"  {i+1}/{N_OPENINGS} openings done "
                      f"({time.perf_counter()-t0:.0f}s)", flush=True)

    n = len(results)
    rootdist = {1: 0, 0: 0, -1: 0}
    for r in results:
        rootdist[r["root_v"]] += 1
    with_conflict = sum(1 for r in results if r["conflict"] > 0)
    floors = sorted(r["floor"] for r in results)
    conflicts = sorted(r["conflict"] for r in results)

    def pct(xs, p):
        return xs[min(len(xs) - 1, int(p * len(xs)))]

    print()
    print("=" * 64)
    print(f"CROSS-OPENING EXCHANGE ALIASING  |  {n} random 6-dice openings")
    print("=" * 64)
    print(f"root value dist        : A-win {rootdist[1]}  draw {rootdist[0]}  B-win {rootdist[-1]}")
    print(f"openings w/ >=1 conflict group : {with_conflict}/{n}  ({100*with_conflict/n:.0f}%)")
    print()
    print("tops-only exchange floor (win/loss units):")
    print(f"  mean   : {sum(floors)/n:.4f}")
    print(f"  median : {pct(floors,0.5):.4f}")
    print(f"  p90    : {pct(floors,0.9):.4f}")
    print(f"  max    : {floors[-1]:.4f}")
    print(f"  zero   : {sum(1 for f in floors if f==0)}/{n} openings have floor 0")
    print()
    print("conflict-group count per opening:")
    print(f"  mean {sum(conflicts)/n:.2f}   median {pct(conflicts,0.5)}   max {conflicts[-1]}")
    print()
    print("demo board for reference: floor 0.0210, 4 conflict groups")
    print(f"compute time: {time.perf_counter()-t0:.0f}s")


if __name__ == "__main__":
    main()
