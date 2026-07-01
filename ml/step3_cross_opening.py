"""Step 3: does the TRAINED aliasing cost generalise across openings?

Step 2 showed, on the single demo opening, that a tops-only learner pays an
excess exchange regret of ~+0.0215 (matching the structural floor 0.021) and
loses ~5.5% of games the full-state learner wins, against an optimal B.

Here we replicate the full/optimal vs tops_only/optimal contrast across many
random openings and ask:
  * Does tops-only pay an excess exchange regret wherever the structure says it
    can (floor > 0)?  Does it convert wins -> losses vs optimal B?
  * Do zero-floor openings (no structural aliasing) show ~no trained excess
    (control)?
  * How does the TRAINED excess track the independently-derived STRUCTURAL floor?

Opponent is optimal B (the punishing case). Parallel across openings.

Usage:
    python3 step3_cross_opening.py                       # defaults below
    python3 step3_cross_opening.py 300000 0,1,2 300 20 6 # eps seeds audit Ktest Kctrl
"""

import os
import statistics
import sys
import time
from multiprocessing import Pool

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit import audit  # noqa: E402  (also puts the solver dir on sys.path)
from env import FixedStartEnv  # noqa: E402
from opponents import OptimalB  # noqa: E402
from run_cross_opening import exchange_floor, random_opening  # noqa: E402
from solver import solve_from_roll  # noqa: E402
from tabular_q import train  # noqa: E402

import random  # noqa: E402

EPISODES = 300_000
SEEDS = [0, 1, 2]
AUDIT_EPS = 300
K_TEST = 20   # A-win openings WITH a structural aliasing floor (floor > 0)
K_CTRL = 6    # A-win openings with NO structural floor (control)
SAMPLE_SEED = 2026


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return statistics.mean(xs) if xs else None


def run_opening(args):
    """One opening: full/optimal vs tops_only/optimal, averaged over seeds."""
    board, a_cry, b_cry, floor, episodes, seeds, audit_eps = args
    opp = OptimalB()  # one optimal B per opening (caches reused across cells/seeds)
    out = {"board": board, "a_cry": a_cry, "b_cry": b_cry, "floor": floor}
    for obs_mode in ("full", "tops_only"):
        env = FixedStartEnv(opp, board=board, a_crystal=a_cry, b_crystal=b_cry,
                            obs_mode=obs_mode)
        win, loss, ereg, dreg, opt = [], [], [], [], []
        for seed in seeds:
            Q = train(env, episodes=episodes, alpha=0.1, eps=0.2, seed=seed)
            rep = audit(env, Q, episodes=audit_eps, seed=12345)
            win.append(rep["win_rate"])
            loss.append(rep["loss_rate"])
            ereg.append(rep["exchange_mean_regret"])
            dreg.append(rep["draft_mean_regret"])
            opt.append(rep["optimal_move_rate"])
        tag = obs_mode
        out[f"{tag}_win"] = _mean(win)
        out[f"{tag}_loss"] = _mean(loss)
        out[f"{tag}_ereg"] = _mean(ereg)
        out[f"{tag}_dreg"] = _mean(dreg)
        out[f"{tag}_opt"] = _mean(opt)
    out["excess_ereg"] = out["tops_only_ereg"] - out["full_ereg"]
    out["excess_dreg"] = out["tops_only_dreg"] - out["full_dreg"]
    out["excess_loss"] = out["tops_only_loss"] - out["full_loss"]
    return out


def _qual_one(args):
    """Compute (board, a_cry, b_cry, root_v, floor) for one candidate opening."""
    board, a_cry, b_cry = args
    root_v, _ = solve_from_roll(board, a_cry, b_cry)
    if root_v != 1:  # keep A-win openings so "wins -> losses" is meaningful
        return (board, a_cry, b_cry, root_v, None)
    _, _, _, _, floor = exchange_floor(board, a_cry, b_cry)
    return (board, a_cry, b_cry, root_v, floor)


def qualify(n_test, n_ctrl, rng, batch=240):
    """Parallel: score a batch of candidate openings, bucket A-win by floor>0/==0."""
    cands = [random_opening(rng) for _ in range(batch)]
    with Pool(processes=max(1, (os.cpu_count() or 2) - 1)) as pool:
        scored = pool.map(_qual_one, cands)
    test, ctrl = [], []
    for board, a_cry, b_cry, root_v, floor in scored:
        if root_v != 1 or floor is None:
            continue
        if floor > 1e-9 and len(test) < n_test:
            test.append((board, a_cry, b_cry, floor))
        elif floor <= 1e-9 and len(ctrl) < n_ctrl:
            ctrl.append((board, a_cry, b_cry, floor))
    return test, ctrl


def _summ(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return "n/a"
    n = len(xs)
    p = lambda q: xs[min(n - 1, int(q * n))]
    return f"mean {sum(xs)/n:+.4f}  median {p(0.5):+.4f}  p90 {p(0.9):+.4f}  max {xs[-1]:+.4f}"


def main():
    episodes = int(sys.argv[1]) if len(sys.argv) > 1 else EPISODES
    seeds = ([int(x) for x in sys.argv[2].split(",")]
             if len(sys.argv) > 2 else SEEDS)
    audit_eps = int(sys.argv[3]) if len(sys.argv) > 3 else AUDIT_EPS
    k_test = int(sys.argv[4]) if len(sys.argv) > 4 else K_TEST
    k_ctrl = int(sys.argv[5]) if len(sys.argv) > 5 else K_CTRL

    t0 = time.perf_counter()
    rng = random.Random(SAMPLE_SEED)
    print(f"Qualifying openings (target test={k_test} floor>0, ctrl={k_ctrl} floor=0) ...",
          flush=True)
    test, ctrl = qualify(k_test, k_ctrl, rng)
    print(f"  got test={len(test)} ctrl={len(ctrl)}  ({time.perf_counter()-t0:.0f}s)")
    print(f"  episodes={episodes} seeds={seeds} audit_eps={audit_eps} | optimal-B opponent")
    print(flush=True)

    jobs = [(b, a, bb, f, episodes, seeds, audit_eps) for (b, a, bb, f) in test]
    jobs += [(b, a, bb, f, episodes, seeds, audit_eps) for (b, a, bb, f) in ctrl]

    results = []
    with Pool(processes=min(len(jobs), max(1, (os.cpu_count() or 2) - 1))) as pool:
        for i, r in enumerate(pool.imap_unordered(run_opening, jobs)):
            results.append(r)
            print(f"  [{i+1}/{len(jobs)}] floor={r['floor']:.4f} "
                  f"full(win {r['full_win']:.2f} loss {r['full_loss']:.2f} ereg {r['full_ereg']:.4f}) "
                  f"tops(win {r['tops_only_win']:.2f} loss {r['tops_only_loss']:.2f} "
                  f"ereg {r['tops_only_ereg']:.4f}) excess_ereg={r['excess_ereg']:+.4f} "
                  f"excess_dreg={r['excess_dreg']:+.4f} "
                  f"excess_loss={r['excess_loss']:+.4f} ({time.perf_counter()-t0:.0f}s)",
                  flush=True)

    test_r = [r for r in results if r["floor"] > 1e-9]
    ctrl_r = [r for r in results if r["floor"] <= 1e-9]

    print()
    print("=" * 70)
    print(f"STEP 3 — TRAINED ALIASING COST ACROSS OPENINGS (optimal B)")
    print("=" * 70)
    print(f"openings: {len(test_r)} test (structural floor>0) + {len(ctrl_r)} control (floor=0)")
    print()
    print("TEST openings (structural aliasing present):")
    pay_e = sum(1 for r in test_r if r["excess_ereg"] > 1e-6)
    pay_l = sum(1 for r in test_r if r["excess_loss"] > 1e-6)
    print(f"  tops_only pays excess EXCH regret : {pay_e}/{len(test_r)}")
    print(f"  tops_only converts WINS->LOSSES   : {pay_l}/{len(test_r)}")
    print(f"  excess exch regret : {_summ([r['excess_ereg'] for r in test_r])}")
    print(f"  excess draft regret: {_summ([r['excess_dreg'] for r in test_r])}")
    print(f"  excess loss rate   : {_summ([r['excess_loss'] for r in test_r])}")
    print(f"  structural floor   : {_summ([r['floor'] for r in test_r])}")
    print(f"  full/optimal win   : {_summ([r['full_win'] for r in test_r])}")
    print(f"  full/optimal ereg  : {_summ([r['full_ereg'] for r in test_r])}")
    print()
    print("CONTROL openings (no structural EXCHANGE aliasing; draft aliasing may remain):")
    print(f"  excess exch regret : {_summ([r['excess_ereg'] for r in ctrl_r])}")
    print(f"  excess draft regret: {_summ([r['excess_dreg'] for r in ctrl_r])}")
    print(f"  excess loss rate   : {_summ([r['excess_loss'] for r in ctrl_r])}")
    print()
    print(f"demo opening reference (Step 2): excess_ereg +0.0215, excess_loss +0.055, floor 0.021")
    print(f"total compute: {time.perf_counter()-t0:.0f}s")


if __name__ == "__main__":
    main()
