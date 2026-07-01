#!/usr/bin/env python3
"""
READ-ONLY diagnostic (no solver changes). Quantifies the principal-line / entry-point
consistency issue and its impact on the published "330 of 3663 A-win openings" figure.

Per seed in the 5,000-game suite we compute three things:

  v_root      = stored benchmark value (from solve_from_roll)          [g['value']]
  v_root_res  = solve_from_position from the OPENING (A to move)        [true root re-solve]
  v_node      = solve_from_position at the node BEFORE B's last pick,
                reached by replaying solve_from_roll's principal line   [Claude's deep-node check]
  outcome     = realized re-solving blunder outcome (use_static=False)  [narrow cross-join]

Reports:
  (1) NARROW cross-join  : realized B-win (outcome=-1) with v_root != -1   [site's "3 seeds"]
  (2) ROOT-LABEL check   : v_root_res != v_root, and among A-win roots
                           (v_root=+1) how many re-solve to != +1
                           -> THIS is the actual contamination of the "330" label
  (3) WITNESS/LINE check : v_node != v_root  (deep node along the stored line)
                           -> compare prevalence to Claude's ~0.85%
"""

import json
import os
import sys
from collections import Counter
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO_ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO_ROOT, "solvers", "python"))

from solver import (  # noqa: E402
    PLAYER_A,
    PLAYER_B,
    _draft_value,
    apply_draft_action,
    solve_from_roll,
)


def _is_exchange_move(move) -> bool:
    return (
        isinstance(move, (tuple, list))
        and len(move) == 2
        and isinstance(move[0], (tuple, list))
        and len(move[0]) == 2
    )


def _worker(g):
    board = tuple(g["board"])
    a_crystal = tuple(g["a_crystal"])
    b_crystal = tuple(g["b_crystal"])
    seed = g["seed"]
    v_root = int(g["value"])
    n_dice = sum(board)
    b_last_idx = n_dice - 1

    # (2) root re-solve from the opening, A to move (value only)
    v_root_res = int(_draft_value(board, (), (), a_crystal, b_crystal, PLAYER_A, {})[0])

    # replay stored principal line to the node before B's last pick
    _, line = solve_from_roll(board, a_crystal, b_crystal)
    a_cru, b_cru, cur = (), (), board
    for i, mv in enumerate(line):
        if mv is None:
            continue
        if _is_exchange_move(mv):
            break
        if i % 2 == 0:
            cur, a_cru = apply_draft_action(cur, a_cru, mv)
        else:
            if i == b_last_idx:
                break
            cur, b_cru = apply_draft_action(cur, b_cru, mv)
    v_node = int(_draft_value(cur, a_cru, b_cru, a_crystal, b_crystal, PLAYER_B, {})[0])

    return seed, v_root, v_root_res, v_node


def main():
    bench = os.path.join(HERE, "benchmark_5000_6d.json")
    args = sys.argv[1:]
    limit = int(args[args.index("--limit") + 1]) if "--limit" in args else None
    games = json.load(open(bench))["games"]
    if limit:
        games = games[:limit]
    total = len(games)

    rows = []
    with Pool() as pool:
        for j, r in enumerate(pool.imap(_worker, games, chunksize=8)):
            rows.append(r)
            if (j + 1) % 250 == 0 or j + 1 == total:
                print(f"  {j + 1}/{total} done", flush=True)

    stored = Counter(v for _, v, _, _ in rows)
    root_mis = [(s, v, vr) for s, v, vr, vn in rows if vr != v]
    awin_root_contam = [(s, v, vr) for s, v, vr, vn in rows if v == 1 and vr != 1]
    node_mis = [(s, v, vn) for s, v, vr, vn in rows if vn != v]
    awin_node_mis = [(s, v, vn) for s, v, vr, vn in rows if v == 1 and vn != 1]
    awin_roots = stored[1]

    print()
    print("=" * 66)
    print("Solver entry-point consistency diagnostic (READ-ONLY)")
    print("=" * 66)
    print(f"  N seeds                         : {total}")
    print(f"  stored value counts (+1/0/-1)   : {stored[1]} / {stored[0]} / {stored[-1]}")
    print()
    print("(2) ROOT-LABEL check  (solve_from_position@root  vs  stored value):")
    print(f"    total root mismatches            : {len(root_mis)}")
    print(f"    among A-win roots (v=+1) -> != +1 : {len(awin_root_contam)}  "
          f"(= {100*len(awin_root_contam)/max(awin_roots,1):.2f}% of {awin_roots})")
    print(f"    *** this is the real contamination of the '330 of {awin_roots}' label ***")
    if root_mis:
        print(f"    mismatch seeds (seed, stored, root_resolve): {root_mis}")
    print()
    print("(3) WITNESS/LINE check (deep node before B's last pick vs stored value):")
    print(f"    total node mismatches            : {len(node_mis)}  "
          f"(= {100*len(node_mis)/total:.2f}% of seeds  <- compare to Claude's ~0.85%)")
    print(f"    among A-win roots (v=+1) -> != +1 : {len(awin_node_mis)}")
    if node_mis:
        print(f"    node-mismatch seeds (seed, stored, node_resolve): {node_mis}")


if __name__ == "__main__":
    main()
