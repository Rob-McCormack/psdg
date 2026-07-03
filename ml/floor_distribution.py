"""Structural DRAFT-floor distribution across random 6-dice openings.

Learner-independent generalization of `structural_floors_cross.py`: instead of a
small curated opening set, sample many random 6-dice boards and report the
DISTRIBUTION of the tops-only draft aliasing floor. Answers the reviewer's
"is this cherry-picked?" objection with a prevalence + magnitude distribution.

Two crystal conditions are run on the SAME board (paired), reported separately,
never pooled:
  - FIXED  : A=(2,6), B=(1,2)  -- the published single-opening convention
  - RANDOM : crystals drawn per board with the exact convention in
             run_cross_opening.random_opening (crystal top in 1..5).

We do NOT reimplement any game/solver logic. The floor comes from
`structural_floors_cross.draft_floor`; the root value from `solver.solve_from_roll`;
the board/crystal sampling mirrors `run_cross_opening.random_opening` exactly
(6 iid d6 tops -> histogram; crystal facing from `solver.side_faces`).

Calibration gate: before any sampling, `draft_floor` on the demo opening
(ml/position.py) must return floor 0.009686 (+/-1e-6) with 13009 states,
76 groups, 75 aliased, 13 conflicts. Mismatch => STOP.

Checkpointing: one JSONL line per (board, condition) is written as it completes,
so a killed run loses at most the in-flight boards; --resume continues.

Usage:
    python3 floor_distribution.py --n 10                 # smoke test
    python3 floor_distribution.py --n 200 --resume       # full run, resumable
"""

import argparse
import json
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

import random  # noqa: E402

from solver import side_faces, solve_from_roll  # noqa: E402
from structural_floors_cross import draft_floor  # noqa: E402
from position import A_CRYSTAL, B_CRYSTAL, BOARD, BOARD_TOPS  # noqa: E402

DICE = 6
DEFAULT_SEED = 2026
DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "output", "floor_distribution_6d.jsonl")

# Calibration expectations (draft_floor on the demo opening).
CAL_STATES, CAL_GROUPS, CAL_ALIASED, CAL_CONFLICT, CAL_FLOOR = 13009, 76, 75, 13, 0.009686
CAL_TOL = 1e-6


def board_from_seed(seed):
    """6 iid d6 tops -> 6-count histogram (mirrors run_cross_opening.random_opening)."""
    rng = random.Random(seed)
    tops = [rng.randint(1, 6) for _ in range(DICE)]
    board = tuple(tops.count(v) for v in range(1, 7))
    return board, sorted(tops), rng


def random_crystal(rng):
    """Crystal (top, facing); top never 6 (mirrors run_cross_opening.random_opening)."""
    t = rng.randint(1, 5)
    return (t, rng.choice(side_faces(t)))


def calibrate():
    n_states, n_groups, aliased, conflict, floor = draft_floor(BOARD, A_CRYSTAL, B_CRYSTAL)
    ok = (n_states == CAL_STATES and n_groups == CAL_GROUPS and aliased == CAL_ALIASED
          and conflict == CAL_CONFLICT and abs(floor - CAL_FLOOR) <= CAL_TOL)
    print("Calibration gate (demo opening, draft_floor):")
    print(f"  states   {n_states:>7} (expect {CAL_STATES})")
    print(f"  groups   {n_groups:>7} (expect {CAL_GROUPS})")
    print(f"  aliased  {aliased:>7} (expect {CAL_ALIASED})")
    print(f"  conflict {conflict:>7} (expect {CAL_CONFLICT})")
    print(f"  floor    {floor:.6f} (expect {CAL_FLOOR:.6f}, tol {CAL_TOL})")
    print(f"  => {'PASS' if ok else 'FAIL'}", flush=True)
    return ok


def worker(job):
    idx, seed, board, board_tops, condition, a_cry, b_cry = job
    t0 = time.perf_counter()
    root_v, _ = solve_from_roll(board, a_cry, b_cry)
    n_states, n_groups, aliased, conflict, floor = draft_floor(board, a_cry, b_cry)
    return {
        "base_seed": None,  # filled by main
        "board_index": idx,
        "board_seed": seed,
        "board_tops": board_tops,
        "histogram": list(board),
        "condition": condition,
        "a_crystal": list(a_cry),
        "b_crystal": list(b_cry),
        "root_v": root_v,
        "n_states": n_states,
        "n_groups": n_groups,
        "n_aliased": aliased,
        "n_conflicts": conflict,
        "floor": floor,
        "wall_seconds": round(time.perf_counter() - t0, 3),
    }


def load_done(out_path):
    done = set()
    if not os.path.exists(out_path):
        return done
    with open(out_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                done.add((rec["board_index"], rec["condition"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return done


def build_jobs(n, base_seed, done):
    jobs = []
    for i in range(n):
        seed = f"{base_seed}:{i}"
        board, board_tops, rng = board_from_seed(seed)
        if (i, "fixed") not in done:
            jobs.append((i, seed, board, board_tops, "fixed", tuple(A_CRYSTAL), tuple(B_CRYSTAL)))
        # draw random crystals AFTER the board, from the same stream (faithful pairing)
        a_cry = random_crystal(rng)
        b_cry = random_crystal(rng)
        if (i, "random") not in done:
            jobs.append((i, seed, board, board_tops, "random", a_cry, b_cry))
    return jobs


def _pct(xs, q):
    return xs[min(len(xs) - 1, int(q * len(xs)))]


def _bucket(f):
    if f == 0:
        return "0"
    if f <= 0.01:
        return "(0-0.01]"
    if f <= 0.05:
        return "(0.01-0.05]"
    if f <= 0.10:
        return "(0.05-0.1]"
    return ">0.1"


BUCKETS = ["0", "(0-0.01]", "(0.01-0.05]", "(0.05-0.1]", ">0.1"]


def aggregate(out_path):
    by_cond = defaultdict(list)
    with open(out_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            by_cond[rec["condition"]].append(rec)

    for cond in ("fixed", "random"):
        recs = by_cond.get(cond, [])
        if not recs:
            continue
        n = len(recs)
        floors = sorted(r["floor"] for r in recs)
        pos = sum(1 for f in floors if f > 1e-9)
        zeros = sum(1 for f in floors if f == 0)
        awins = [r for r in recs if r["root_v"] == 1]
        awin_pos = sum(1 for r in awins if r["floor"] > 1e-9)

        print()
        print("=" * 64)
        print(f"CONDITION: {cond.upper()}  |  {n} openings")
        print("=" * 64)
        rd = defaultdict(int)
        for r in recs:
            rd[r["root_v"]] += 1
        print(f"root value dist : A-win {rd[1]}  draw {rd[0]}  B-win {rd[-1]}")
        print(f"floor > 0       : {pos}/{n}  ({100*pos/n:.0f}%)")
        print(f"exact zero      : {zeros}/{n}")
        print(f"floor mean      : {sum(floors)/n:.4f}")
        print(f"floor median    : {_pct(floors,0.5):.4f}")
        print(f"floor max       : {floors[-1]:.4f}")
        print(f"percentiles     : p50 {_pct(floors,0.5):.4f}  p75 {_pct(floors,0.75):.4f}  "
              f"p90 {_pct(floors,0.9):.4f}  p99 {_pct(floors,0.99):.4f}")
        counts = defaultdict(int)
        for f in floors:
            counts[_bucket(f)] += 1
        print("histogram       : " + "  ".join(f"{b}:{counts[b]}" for b in BUCKETS))
        if awins:
            print(f"among A-win only : floor>0 {awin_pos}/{len(awins)}  "
                  f"({100*awin_pos/len(awins):.0f}%)")
    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=10, help="number of random boards")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED, help="base seed")
    ap.add_argument("--out", default=DEFAULT_OUT, help="JSONL checkpoint path")
    ap.add_argument("--resume", action="store_true", help="skip (board,condition) already in JSONL")
    ap.add_argument("--aggregate-only", action="store_true", help="just re-print tables from JSONL")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)

    if args.aggregate_only:
        aggregate(args.out)
        return

    if not calibrate():
        print("\nSTOP: calibration gate failed; not sampling.", file=sys.stderr)
        sys.exit(1)

    done = load_done(args.out) if args.resume else set()
    if done:
        print(f"Resume: {len(done)} (board,condition) results already present.", flush=True)
    jobs = build_jobs(args.n, args.seed, done)
    print(f"\nRunning {len(jobs)} jobs "
          f"({args.n} boards x 2 conditions, minus {len(done)} done)  "
          f"seed={args.seed}\n", flush=True)

    if not jobs:
        print("Nothing to do.")
        aggregate(args.out)
        return

    t0 = time.perf_counter()
    procs = min(len(jobs), max(1, (os.cpu_count() or 2) - 1))
    completed = 0
    mode = "a" if args.resume and os.path.exists(args.out) else "w"
    with open(args.out, mode, encoding="utf-8") as fout, \
            Pool(processes=procs) as pool:
        for rec in pool.imap_unordered(worker, jobs):
            rec["base_seed"] = args.seed
            fout.write(json.dumps(rec) + "\n")
            fout.flush()
            completed += 1
            print(f"  [{completed}/{len(jobs)}] board {rec['board_index']:>4} "
                  f"{rec['condition']:>6}  floor {rec['floor']:.4f}  "
                  f"root {rec['root_v']:+d}  ({rec['wall_seconds']:.1f}s)", flush=True)

    print(f"\nwrote {args.out}   compute {time.perf_counter()-t0:.0f}s", flush=True)
    aggregate(args.out)
    print("Reproduce:  python3 floor_distribution.py --n {} --seed {}".format(args.n, args.seed))


if __name__ == "__main__":
    main()
