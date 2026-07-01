"""Kill-shot: 'more training doesn't help tops-only.'

Same solver-as-examiner discipline as everywhere else (train with terminal
reward only, no oracle labels; audit afterwards). We fix the demo opening and the
STRONG opponent (OptimalB), then sweep the training budget WELL PAST the Step-1
plateau (e.g. 2-8x) for both observation encoders:

  * full/optimal      -> should hit optimal (0 regret, 100% win) early and stay.
  * tops_only/optimal -> should PLATEAU at strictly positive regret/loss, ABOVE
    the learner-independent structural floor, no matter how big the budget gets.

The structural floors (exchange + draft) for THIS exact opening are computed once
and printed for reference: that is the line the tops-only learner cannot cross.

Usage:
    python3 robustness_budget.py                              # default panel
    python3 robustness_budget.py 250000,500000,1000000,2000000 0,1,2 400
"""

import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit import audit  # noqa: E402  (also puts the solver dir on sys.path)
from env import FixedStartEnv  # noqa: E402
from opponents import OptimalB  # noqa: E402
from position import EXPECTED_ROOT_VALUE  # noqa: E402
from run_cross_opening import exchange_floor  # noqa: E402
from solver import solve_from_roll  # noqa: E402
from structural_floors_cross import draft_floor  # noqa: E402
from tabular_q import train  # noqa: E402


def _ms(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    if len(xs) == 1:
        return xs[0], 0.0
    return statistics.mean(xs), max(xs) - min(xs)


def _fmt(xs, pct=True):
    m, sp = _ms(xs)
    if m is None:
        return f"{'n/a':>15}"
    return f"{m:6.1%} [{sp:5.1%}]" if pct else f"{m:7.4f}[{sp:6.4f}]"


def main():
    grid = ([int(x) for x in sys.argv[1].split(",")]
            if len(sys.argv) > 1 else [250_000, 500_000, 1_000_000, 2_000_000])
    seeds = ([int(x) for x in sys.argv[2].split(",")]
             if len(sys.argv) > 2 else [0, 1, 2])
    audit_eps = int(sys.argv[3]) if len(sys.argv) > 3 else 400
    which = sys.argv[4] if len(sys.argv) > 4 else "both"
    obs_list = (["full", "tops_only"] if which == "both" else [which])

    probe = FixedStartEnv(OptimalB())
    rootv, _ = solve_from_roll(probe.board0, probe.a_crystal, probe.b_crystal)
    assert rootv == EXPECTED_ROOT_VALUE, "root value mismatch -- check position"
    board, a_cry, b_cry = probe.board0, probe.a_crystal, probe.b_crystal

    # Learner-independent floors for THIS opening (the lines no policy can cross).
    _, _, _, _, efloor = exchange_floor(board, a_cry, b_cry)
    _, _, _, _, dfloor = draft_floor(board, a_cry, b_cry)
    print(f"root value (oracle): {rootv}  opponent: optimal  opening: demo")
    print(f"structural floors (learner-independent): "
          f"exchange={efloor:.4f}  draft={dfloor:.4f}  total>={efloor+dfloor:.4f}")
    print(f"Step-1 plateau was ~500k; this panel goes to {max(grid):,} ({max(grid)/500_000:.0f}x).")
    print(f"grid={grid}  seeds={seeds}  audit_eps={audit_eps}")
    print()

    hdr = (f"{'obs_mode':>10} | {'episodes':>9} | {'root_opt':>8} | {'opt_rate':>15} | "
           f"{'draft_reg':>15} | {'exch_reg':>15} | {'win':>15} | {'loss':>15}")

    rows = {}  # (obs_mode, episodes) -> metric dict
    for obs_mode in obs_list:
        env = FixedStartEnv(OptimalB(), obs_mode=obs_mode)
        print(f"=== {obs_mode} vs optimal (mean [spread] across seeds) ===")
        print(hdr)
        print("-" * len(hdr))
        for episodes in grid:
            m = {k: [] for k in ("root", "opt", "dreg", "ereg", "win", "loss")}
            for seed in seeds:
                t0 = time.perf_counter()
                Q = train(env, episodes=episodes, alpha=0.1, eps=0.2, seed=seed)
                rep = audit(env, Q, episodes=audit_eps, seed=12345)
                dt = time.perf_counter() - t0
                m["root"].append(1.0 if rep["root_optimal"] else 0.0)
                m["opt"].append(rep["optimal_move_rate"])
                m["dreg"].append(rep["draft_mean_regret"])
                m["ereg"].append(rep["exchange_mean_regret"])
                m["win"].append(rep["win_rate"])
                m["loss"].append(rep["loss_rate"])
                print(f"    [{obs_mode:9s} {episodes:>9} seed {seed}] "
                      f"opt={rep['optimal_move_rate']:.3f} "
                      f"dreg={rep['draft_mean_regret']:.4f} "
                      f"ereg={rep['exchange_mean_regret']:.4f} "
                      f"win={rep['win_rate']:.3f} loss={rep['loss_rate']:.3f} "
                      f"({dt:.1f}s)", flush=True)
            rows[(obs_mode, episodes)] = m
            rmean, _ = _ms(m["root"])
            print(f"{obs_mode:>10} | {episodes:>9} | {rmean*100:6.0f}% | {_fmt(m['opt'])} | "
                  f"{_fmt(m['dreg'], pct=False)} | {_fmt(m['ereg'], pct=False)} | "
                  f"{_fmt(m['win'])} | {_fmt(m['loss'])}", flush=True)
        print()

    print("=" * 70)
    print("VERDICT")
    print("=" * 70)
    if ("full", grid[-1]) in rows:
        fbig = rows[("full", grid[-1])]
        fwin, _ = _ms(fbig["win"]); floss, _ = _ms(fbig["loss"])
        print(f"full @ {grid[-1]:,}:      win {fwin:.1%}  loss {floss:.1%}   (budget is NOT the bottleneck)")
    if ("tops_only", grid[0]) in rows:
        tsmall = rows[("tops_only", grid[0])]
        tbig = rows[("tops_only", grid[-1])]
        treg_s, _ = _ms([d + e for d, e in zip(tsmall["dreg"], tsmall["ereg"])])
        treg_b, _ = _ms([d + e for d, e in zip(tbig["dreg"], tbig["ereg"])])
        tloss_s, _ = _ms(tsmall["loss"]); tloss_b, _ = _ms(tbig["loss"])
        twin_b, _ = _ms(tbig["win"])
        # how many seeds are fully solved (0 total regret) at the largest budget?
        solved_b = sum(1 for d, e in zip(tbig["dreg"], tbig["ereg"]) if d + e < 1e-9)
        print(f"tops_only @ {grid[0]:,}:  total regret {treg_s:.4f}  loss {tloss_s:.1%}")
        print(f"tops_only @ {grid[-1]:,}: total regret {treg_b:.4f}  loss {tloss_b:.1%}  win {twin_b:.1%}")
        print(f"  seeds fully solved (0 regret) @ {grid[-1]:,}: {solved_b}/{len(seeds)}")
        print(f"structural floor (exch+draft): {efloor+dfloor:.4f}  (avg-over-nodes bound)")
        print()
        print(f"{max(grid)/min(grid):.0f}x more training changed tops-only mean total regret by "
              f"{treg_b - treg_s:+.4f}.")
        print("Read on-trajectory outcome (win/loss) separately from the structural floor:")
        print("the floor bounds AVERAGE regret over enumerated aliased nodes, not the")
        print("outcome against one fixed opponent (aliased nodes can sit off the played line).")


if __name__ == "__main__":
    main()
