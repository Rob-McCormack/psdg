"""Exchange-level structural aliasing test (Phase 7, the node most likely to bite).

At the Exchange, the facings of the dice A *keeps* drive its Phase-2 score, so a
tops-only (facing-blind) agent has the most to lose here.

Facing-blind action model: the agent may specify only (gift_top T, given_facing f)
-- eligibility and side_faces depend on tops alone, so that much is observable.
It cannot see its retained dice's facings, nor pick between two same-top dice.
We give the agent the benefit of the doubt on same-top ties (best realization),
so any conflict found is genuine, not an artifact of the model.

For each reachable Exchange state we compute A's exact security-optimal gift set
(maximin over B's true replies), reduce it to facing-blind (T, f) actions, group
states by tops-only observation (a_tops, b_tops), and report:
  * aliased groups with no common optimal facing-blind action (conflict);
  * the irreducible regret floor of the best facing-blind policy
    (full-state floor = 0).
"""

import os
import sys
import time
from collections import defaultdict

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
)

from position import A_CRYSTAL, B_CRYSTAL, BOARD  # noqa: E402

A_CRY, B_CRY = A_CRYSTAL, B_CRYSTAL


def reachable_exchange_states():
    visited = {(BOARD, (), ())}
    stack = [(BOARD, (), ())]
    exch = []
    while stack:
        board, a, b = stack.pop()
        if sum(board) == 0:
            exch.append((a, b))
            continue
        a_to_move = (len(a) + len(b)) % 2 == 0
        for act in legal_draft_actions(board):
            if a_to_move:
                nb, na = apply_draft_action(board, a, act)
                ns = (nb, na, b)
            else:
                nb, nbb = apply_draft_action(board, b, act)
                ns = (nb, a, nbb)
            if ns not in visited:
                visited.add(ns)
                stack.append(ns)
    return list(set(exch))


def main():
    t0 = time.perf_counter()
    states = reachable_exchange_states()

    # Per-state: security value, blind-optimal action set, and best guaranteed
    # value for each facing-blind action (T, f).
    groups = defaultdict(list)
    for (a, b) in states:
        a_legal = [(ai, af) for ai in forced_gift_indices(a, A_CRY) for af in side_faces(a[ai][0])]
        b_legal = [(bi, bf) for bi in forced_gift_indices(b, B_CRY) for bf in side_faces(b[bi][0])]
        guar = {}
        for aact in a_legal:
            guar[aact] = min(
                evaluate(*apply_exchange(a, b, aact, bact), A_CRY, B_CRY) for bact in b_legal
            )
        vstar = max(guar.values())
        # best guaranteed value per facing-blind action (benefit of the doubt on ties)
        blind_guar = {}
        for (ai, af), gv in guar.items():
            key = (a[ai][0], af)
            if key not in blind_guar or gv > blind_guar[key]:
                blind_guar[key] = gv
        blind_opt = {k for k, gv in blind_guar.items() if gv == vstar}
        tkey = (tuple(t for t, _ in a), tuple(t for t, _ in b))
        groups[tkey].append((vstar, blind_guar, blind_opt))

    n_states = len(states)
    n_groups = len(groups)
    aliased = [m for m in groups.values() if len(m) > 1]
    conflict = 0
    floor_total = 0.0
    members_total = 0
    max_group = 0
    for members in groups.values():
        candidates = set()
        for _, blind_guar, _ in members:
            candidates |= set(blind_guar.keys())
        # common optimal facing-blind action?
        inter = None
        for _, _, bopt in members:
            inter = bopt if inter is None else (inter & bopt)
        if not inter:
            conflict += 1
        # irreducible floor: best single facing-blind action over the group
        # (an action only counts where it is legal/realizable in that member)
        best = None
        for cand in candidates:
            tot = 0.0
            ok = True
            for vstar, blind_guar, _ in members:
                if cand not in blind_guar:
                    ok = False
                    break
                tot += vstar - blind_guar[cand]
            if ok and (best is None or tot < best):
                best = tot
        floor_total += best if best is not None else 0.0
        members_total += len(members)
        max_group = max(max_group, len(members))

    print("Exchange decision states (unique)     :", n_states)
    print("tops-only observation groups          :", n_groups)
    print("groups with >1 true state (aliased)   :", len(aliased))
    print("max true states behind one tops-key   :", max_group)
    print("aliased groups with NO common optimal :", conflict,
          f"({100*conflict/max(len(aliased),1):.1f}% of aliased groups)")
    print()
    print("Irreducible mean regret at Exchange (uniform over states):")
    print("  full-state policy floor   : 0.000")
    print(f"  tops-only policy floor    : {floor_total/members_total:.4f}")
    print()
    print(f"compute time: {time.perf_counter()-t0:.1f}s")


if __name__ == "__main__":
    main()
