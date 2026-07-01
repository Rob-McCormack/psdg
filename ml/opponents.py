"""Fixed opponent policies for B (no learning).

Opponent interface (called by FixedStartEnv):
  * draft(state, env, rng) -> (top, facing)      # B is the player to move
  * gift(state, env, rng)  -> (b_index, b_facing) # B's Exchange gift

Both see only B's own legal set plus the public board / oracle; B never reads
A's (unrevealed) gift, so the simultaneous Exchange stays honest.

Policies:
  * RandomLegal : uniform random over legal draft picks / legal gifts.
  * OptimalB    : oracle-optimal B. Drafts that minimise A's game value;
                  gifts that maximin B's security at the simultaneous node.
                  Memoised by true state so a long training run stays cheap
                  (the solver itself memoises only within a single call).
"""

import os
import sys

_SOLVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "solvers", "python")
_SOLVER_DIR = os.path.normpath(_SOLVER_DIR)
if _SOLVER_DIR not in sys.path:
    sys.path.insert(0, _SOLVER_DIR)

from solver import (  # noqa: E402
    PLAYER_A,
    _draft_value,
    apply_draft_action,
    apply_exchange,
    evaluate,
    forced_gift_indices,
    legal_draft_actions,
    side_faces,
)

from env import gift_actions  # noqa: E402


class RandomLegal:
    """Uniform random over legal draft picks / legal gifts."""

    name = "random_legal"

    def draft(self, s, env, rng):
        return rng.choice(legal_draft_actions(s.board))

    def gift(self, s, env, rng):
        return rng.choice(gift_actions(s.b, env.b_crystal))


class OptimalB:
    """Oracle-optimal B (strongest fixed opponent).

    Draft: among B's legal twists, keep those that MINIMISE A's oracle value of
    the resulting (A-to-move) position; pick uniformly among co-optimal ties.

    Gift: B's maximin (security) gift -- minimise A's best reply -- which is the
    honest strong play at the simultaneous node (no peeking at A's gift). This
    mirrors the security-regret notion the auditor uses for A.

    Both are memoised by the true state so 500k episodes don't re-solve.
    """

    name = "optimal"

    def __init__(self):
        self._draft_cache = {}   # (board, a, b) -> tuple(co-optimal B drafts)
        self._gift_cache = {}     # (a, b) -> tuple(co-optimal B gifts)
        self._memo = {}           # shared solver memo (exact values only) -> fast

    def draft(self, s, env, rng):
        key = (s.board, s.a, s.b)
        opts = self._draft_cache.get(key)
        if opts is None:
            best_val = None
            best = []
            for m in legal_draft_actions(s.board):
                nb, nbb = apply_draft_action(s.board, s.b, m)
                # After B's pick it is A to move; B wants to minimise A's value.
                # Full-window solve with a SHARED memo: exact, and reuses work
                # across sibling/earlier states (kills per-opening re-solving).
                v, _ = _draft_value(nb, s.a, nbb, env.a_crystal, env.b_crystal,
                                    PLAYER_A, self._memo)
                if best_val is None or v < best_val:
                    best_val, best = v, [m]
                elif v == best_val:
                    best.append(m)
            opts = tuple(best)
            self._draft_cache[key] = opts
        return opts[0] if len(opts) == 1 else rng.choice(opts)

    def gift(self, s, env, rng):
        key = (s.a, s.b)
        opts = self._gift_cache.get(key)
        if opts is None:
            a_legal = [
                (ai, af)
                for ai in forced_gift_indices(s.a, env.a_crystal)
                for af in side_faces(s.a[ai][0])
            ]
            b_legal = [
                (bi, bf)
                for bi in forced_gift_indices(s.b, env.b_crystal)
                for bf in side_faces(s.b[bi][0])
            ]
            best_val = None  # B minimises A's best reply (lower is better for B)
            best = []
            for b_gift in b_legal:
                a_best = max(
                    evaluate(*apply_exchange(s.a, s.b, a_gift, b_gift),
                             env.a_crystal, env.b_crystal)
                    for a_gift in a_legal
                )
                if best_val is None or a_best < best_val:
                    best_val, best = a_best, [b_gift]
                elif a_best == best_val:
                    best.append(b_gift)
            opts = tuple(best)
            self._gift_cache[key] = opts
        return opts[0] if len(opts) == 1 else rng.choice(opts)
