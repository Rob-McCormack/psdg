"""Step-2 matrix: obs_mode x opponent, oracle-audited.

Cells: obs_mode in {full, tops_only} x opponent in {random_legal, optimal}.
For each cell we train A (terminal reward only, no solver labels) at a fixed
budget over several seeds, then run the solver-as-examiner audit.

Reads three things at once:
  * full / random  -> reproduces the Phase-5 proxy story (draft regret persists).
  * full / optimal -> does a strong opponent close the draft-regret gap?
  * tops_only - full (per opponent) -> the TRAINED aliasing cost: tops-only
    cannot distinguish facings, so it should pay excess EXCHANGE regret,
    consistent with the structural floor (~0.021) -- the headline new result.

Usage:
    python3 sweep_matrix.py                     # 500k, seeds 0-4, audit 400
    python3 sweep_matrix.py 200000 0,1,2 400
"""

import os
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit import audit  # noqa: E402  (also puts the solver dir on sys.path)
from env import FixedStartEnv  # noqa: E402
from opponents import OptimalB, RandomLegal  # noqa: E402
from position import EXPECTED_ROOT_VALUE  # noqa: E402
from solver import solve_from_roll  # noqa: E402
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
    episodes = int(sys.argv[1]) if len(sys.argv) > 1 else 500_000
    seeds = ([int(x) for x in sys.argv[2].split(",")]
             if len(sys.argv) > 2 else [0, 1, 2, 3, 4])
    audit_eps = int(sys.argv[3]) if len(sys.argv) > 3 else 400

    # Reuse one opponent instance per type (caches persist across cells/seeds).
    opponents = {"random_legal": RandomLegal(), "optimal": OptimalB()}
    obs_modes = ["full", "tops_only"]

    probe = FixedStartEnv(RandomLegal())
    rootv, _ = solve_from_roll(probe.board0, probe.a_crystal, probe.b_crystal)
    assert rootv == EXPECTED_ROOT_VALUE, "root value mismatch -- check position"
    print(f"root value (oracle): {rootv}")
    print(f"episodes={episodes}  seeds={seeds}  audit_eps={audit_eps}")
    print()

    hdr = (f"{'obs_mode':>10} | {'opponent':>12} | {'root_opt':>8} | {'opt_rate':>15} | "
           f"{'draft_opt':>15} | {'exch_opt':>15} | {'draft_reg':>15} | "
           f"{'exch_reg':>15} | {'win':>15} | {'loss':>15}")
    print("=== obs_mode x opponent (mean [spread] across seeds) ===")
    print(hdr)
    print("-" * len(hdr))

    cells = {}  # (obs_mode, opp_name) -> dict of metric lists
    for opp_name, opp in opponents.items():
        for obs_mode in obs_modes:
            env = FixedStartEnv(opp, obs_mode=obs_mode)
            m = {k: [] for k in ("root", "opt", "dopt", "eopt", "dreg", "ereg", "win", "loss")}
            for seed in seeds:
                t0 = time.perf_counter()
                Q = train(env, episodes=episodes, alpha=0.1, eps=0.2, seed=seed)
                rep = audit(env, Q, episodes=audit_eps, seed=12345)
                dt = time.perf_counter() - t0
                m["root"].append(1.0 if rep["root_optimal"] else 0.0)
                m["opt"].append(rep["optimal_move_rate"])
                m["dopt"].append(rep["draft_optimal_rate"])
                m["eopt"].append(rep["exchange_optimal_rate"])
                m["dreg"].append(rep["draft_mean_regret"])
                m["ereg"].append(rep["exchange_mean_regret"])
                m["win"].append(rep["win_rate"])
                m["loss"].append(rep["loss_rate"])
                print(f"    [{obs_mode:9s}/{opp_name:12s} seed {seed}] "
                      f"root_opt={rep['root_optimal']} opt={rep['optimal_move_rate']:.3f} "
                      f"ereg={rep['exchange_mean_regret']:.4f} win={rep['win_rate']:.3f} "
                      f"({dt:.1f}s)", flush=True)
            cells[(obs_mode, opp_name)] = m
            rmean, _ = _ms(m["root"])
            print(f"{obs_mode:>10} | {opp_name:>12} | {rmean*100:6.0f}% | {_fmt(m['opt'])} | "
                  f"{_fmt(m['dopt'])} | {_fmt(m['eopt'])} | {_fmt(m['dreg'], pct=False)} | "
                  f"{_fmt(m['ereg'], pct=False)} | {_fmt(m['win'])} | {_fmt(m['loss'])}",
                  flush=True)

    print()
    print("=== TRAINED aliasing cost: tops_only - full (mean exch regret) ===")
    for opp_name in opponents:
        ef, _ = _ms(cells[("full", opp_name)]["ereg"])
        et, _ = _ms(cells[("tops_only", opp_name)]["ereg"])
        df, _ = _ms(cells[("full", opp_name)]["dreg"])
        dt_, _ = _ms(cells[("tops_only", opp_name)]["dreg"])
        print(f"  opponent={opp_name:12s}: "
              f"exch_reg full={ef:.4f} tops_only={et:.4f} -> excess={et - ef:+.4f}  | "
              f"draft_reg full={df:.4f} tops_only={dt_:.4f} -> excess={dt_ - df:+.4f}")
    print()
    print("Structural exchange floor for reference: 0.021 (aliasing_exchange.py).")


if __name__ == "__main__":
    main()
