"""Structural tops-only DRAFT aliasing floor, cross-opening (learner-independent).

Companion to `run_cross_opening.py` (which does the EXCHANGE floor). Here we
compute the analogous floor at A's DRAFT decision nodes: group A-to-move draft
states by their tops-only observation (board, a_tops, b_tops); within a group,
ask whether a single draft action is co-optimal for all members. If not, the
representation is provably insufficient at the draft -- a floor > 0 that no
learner can beat, independent of training dynamics.

We run it on the SAME openings Step 3 used (reuse `qualify`, seed 2026), and
report both floors per opening. The decisive question: do the floor=0 (no
EXCHANGE aliasing) CONTROL openings nevertheless have DRAFT floor > 0?

Regret uses the oracle delta (value lost vs optimal, assuming optimal
continuation) -- integers in {0,1,2} (win/loss units), same as the exchange floor.

Usage:
    python3 structural_floors_cross.py            # 16 test + 4 control (Step-3 set)
    python3 structural_floors_cross.py 16 4
"""

import os
import sys
import time
from collections import defaultdict
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
_SOLVER_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "solvers", "python"))
if _SOLVER_DIR not in sys.path:
    sys.path.insert(0, _SOLVER_DIR)

from solver import (  # noqa: E402
    PLAYER_A,
    PLAYER_B,
    _draft_value,
    apply_draft_action,
    legal_draft_actions,
)
from run_cross_opening import exchange_floor  # noqa: E402
from step3_cross_opening import qualify  # noqa: E402

import random  # noqa: E402

SAMPLE_SEED = 2026


def draft_floor(board, a_cry, b_cry):
    """Tops-only aliasing floor at A's draft decision nodes (shared memo => fast)."""
    memo = {}
    start = (board, (), ())
    visited = {start}
    stack = [start]
    a_states = []
    while stack:
        bd, a, b = stack.pop()
        if sum(bd) == 0:
            continue
        amove = (len(a) + len(b)) % 2 == 0
        if amove:
            a_states.append((bd, a, b))
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

    groups = defaultdict(list)
    for (bd, a, b) in a_states:
        legal = legal_draft_actions(bd)
        vstar, _ = _draft_value(bd, a, b, a_cry, b_cry, PLAYER_A, memo)
        regs = {}
        for act in legal:
            nb, na = apply_draft_action(bd, a, act)
            v_after, _ = _draft_value(nb, na, b, a_cry, b_cry, PLAYER_B, memo)
            regs[act] = vstar - v_after
        opt = {act for act, r in regs.items() if r == 0}
        tkey = (bd, tuple(t for t, _ in a), tuple(t for t, _ in b))
        groups[tkey].append((legal, opt, regs))

    aliased = conflict = 0
    floor_total = members_total = 0.0
    for members in groups.values():
        if len(members) > 1:
            aliased += 1
        inter = None
        for _legal, opt, _regs in members:
            inter = opt if inter is None else inter & opt
        if len(members) > 1 and not inter:
            conflict += 1
        cands = members[0][0]  # same board => same legal set across members
        best = min(sum(regs.get(c, 99) for _l, _o, regs in members) for c in cands)
        floor_total += best
        members_total += len(members)
    floor = floor_total / members_total if members_total else 0.0
    return len(a_states), len(groups), aliased, conflict, floor


def worker(args):
    board, a_cry, b_cry, exch_floor = args
    _, n_groups, aliased, conflict, dfloor = draft_floor(board, a_cry, b_cry)
    return {"board": board, "exch_floor": exch_floor, "draft_floor": dfloor,
            "draft_groups": n_groups, "draft_aliased": aliased, "draft_conflict": conflict}


def _summ(xs):
    xs = sorted(xs)
    n = len(xs)
    if not n:
        return "n/a"
    p = lambda q: xs[min(n - 1, int(q * n))]
    return f"mean {sum(xs)/n:.4f}  median {p(0.5):.4f}  p90 {p(0.9):.4f}  max {xs[-1]:.4f}"


def main():
    k_test = int(sys.argv[1]) if len(sys.argv) > 1 else 16
    k_ctrl = int(sys.argv[2]) if len(sys.argv) > 2 else 4

    t0 = time.perf_counter()
    rng = random.Random(SAMPLE_SEED)
    print(f"Reproducing Step-3 openings (test={k_test} floor>0, ctrl={k_ctrl} floor=0) ...",
          flush=True)
    test, ctrl = qualify(k_test, k_ctrl, rng)
    print(f"  got test={len(test)} ctrl={len(ctrl)}  ({time.perf_counter()-t0:.0f}s)", flush=True)

    jobs = list(test) + list(ctrl)
    n_test = len(test)
    with Pool(processes=min(len(jobs), max(1, (os.cpu_count() or 2) - 1))) as pool:
        results = pool.map(worker, jobs)
    test_r, ctrl_r = results[:n_test], results[n_test:]

    print()
    print("=" * 70)
    print("STRUCTURAL FLOORS (learner-independent): EXCHANGE vs DRAFT, per opening")
    print("=" * 70)
    print(f"{'set':>7} | {'exch_floor':>10} | {'draft_floor':>11} | "
          f"{'draft_groups':>12} | {'draft_conflict':>14}")
    print("-" * 66)
    for r in test_r:
        print(f"{'test':>7} | {r['exch_floor']:10.4f} | {r['draft_floor']:11.4f} | "
              f"{r['draft_groups']:12d} | {r['draft_conflict']:14d}")
    for r in ctrl_r:
        print(f"{'ctrl':>7} | {r['exch_floor']:10.4f} | {r['draft_floor']:11.4f} | "
              f"{r['draft_groups']:12d} | {r['draft_conflict']:14d}")

    print()
    print("TEST openings (exchange floor>0):")
    print(f"  draft_floor : {_summ([r['draft_floor'] for r in test_r])}")
    print(f"  with draft_floor>0 : {sum(1 for r in test_r if r['draft_floor']>1e-9)}/{len(test_r)}")
    print()
    print("CONTROL openings (exchange floor=0) -- the decisive test:")
    print(f"  draft_floor : {_summ([r['draft_floor'] for r in ctrl_r])}")
    cd = sum(1 for r in ctrl_r if r['draft_floor'] > 1e-9)
    print(f"  with draft_floor>0 : {cd}/{len(ctrl_r)}")
    print()
    if cd > 0:
        print("=> Controls with zero EXCHANGE aliasing still have a STRUCTURAL DRAFT floor:")
        print("   the representation is provably insufficient at the DRAFT too (learner-")
        print("   independent). The broad claim holds structurally, not just empirically.")
    else:
        print("=> Controls have NO structural draft floor: the trained control losses are a")
        print("   LEARNING-DYNAMICS effect under aliasing, not an irreducible draft floor.")
        print("   Scope the site claim accordingly.")
    print(f"compute: {time.perf_counter()-t0:.0f}s")


if __name__ == "__main__":
    main()
