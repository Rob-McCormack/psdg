"""Fixed-start PSDG environment for player A, wrapping the exact solver.

Design choices:
  * Mechanics are NOT re-implemented. Draft / Exchange / scoring / tiebreaker
    all route through solver.py's transition functions, so the env and the
    examiner share one engine and verification is near-tautological.
  * A-centric single-agent interface: the env auto-plays B (a fixed opponent)
    so a single-agent learner only sees A's decision points.
  * The simultaneous Gift is preserved: B's gift is drawn from B's own legal
    set with no dependence on A's (unrevealed) gift.

State (GState): (board, a, b, phase) where
  board : 6-count histogram (tops 1..6)
  a, b  : tuples of (top, facing) crucible dice, sorted
  phase : 'draft' or 'exchange'
Crystals are held on the env (so they can be perturbed for Phase 9) and are
folded into the hashable key for safety.
"""

import os
import sys
from collections import namedtuple

_SOLVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "solvers", "python")
_SOLVER_DIR = os.path.normpath(_SOLVER_DIR)
if _SOLVER_DIR not in sys.path:
    sys.path.insert(0, _SOLVER_DIR)

from solver import (  # noqa: E402
    PLAYER_A,
    PLAYER_B,
    apply_draft_action,
    apply_exchange,
    evaluate,
    forced_gift_indices,
    legal_draft_actions,
    side_faces,
)

from position import A_CRYSTAL, B_CRYSTAL, BOARD  # noqa: E402

DRAFT = "draft"
EXCHANGE = "exchange"

GState = namedtuple("GState", ["board", "a", "b", "phase"])


def gift_actions(crucible, crystal):
    """Legal (index, facing) gifts for a player, from own dice only."""
    return [
        (idx, facing)
        for idx in forced_gift_indices(crucible, crystal)
        for facing in side_faces(crucible[idx][0])
    ]


class FixedStartEnv:
    """A-centric fixed-start PSDG env. B is a pluggable fixed opponent."""

    def __init__(self, opponent, board=BOARD, a_crystal=A_CRYSTAL, b_crystal=B_CRYSTAL,
                 obs_mode="full"):
        self.opponent = opponent
        self.board0 = tuple(board)
        self.a_crystal = tuple(a_crystal)
        self.b_crystal = tuple(b_crystal)
        # 'full'      : key carries tops AND facings AND ownership (Markov).
        # 'tops_only' : facings dropped -> deliberately aliased / insufficient.
        assert obs_mode in ("full", "tops_only")
        self.obs_mode = obs_mode

    # --- core interface ---

    def reset(self):
        # A is always first player; A is to move at the root.
        return GState(self.board0, (), (), DRAFT)

    def turn(self, s):
        return PLAYER_A if (len(s.a) + len(s.b)) % 2 == 0 else PLAYER_B

    def legal_actions(self, s):
        """Legal actions for the player A is being asked to choose."""
        if s.phase == EXCHANGE:
            return gift_actions(s.a, self.a_crystal)
        return legal_draft_actions(s.board)

    def state_key(self, s):
        """Agent observation key.

        'full' keeps facings (Markov for this game). 'tops_only' drops the
        crucible facings, so positions that differ only in committed facings
        collapse to one key -- the aliasing manipulation. (Crystals are
        constant within a fixed opening, so facings are the sole distinction.)
        """
        if self.obs_mode == "tops_only":
            a_tops = tuple(t for (t, _f) in s.a)
            b_tops = tuple(t for (t, _f) in s.b)
            return (s.board, a_tops, b_tops, s.phase)
        return (s.board, s.a, s.b, s.phase, self.a_crystal, self.b_crystal)

    def a_step(self, s, a_action, rng):
        """Apply A's action, auto-play B to the next A-decision or terminal.

        Returns (next_state_or_None, reward, done). Reward is 0 except at the
        terminal Exchange, where it is the game value from A's perspective.
        """
        if s.phase == EXCHANGE:
            a_gift = a_action
            b_gift = self.opponent.gift(s, self, rng)
            a_after, b_after = apply_exchange(s.a, s.b, a_gift, b_gift)
            reward = evaluate(a_after, b_after, self.a_crystal, self.b_crystal)
            return None, float(reward), True

        # A draft pick.
        nb, na = apply_draft_action(s.board, s.a, a_action)
        return self._advance(GState(nb, na, s.b, DRAFT), rng)

    # --- internals ---

    def _advance(self, s, rng):
        """Auto-play B until it is A's turn (draft) or the Exchange is reached."""
        while True:
            if sum(s.board) == 0:
                return GState(s.board, s.a, s.b, EXCHANGE), 0.0, False
            if self.turn(s) == PLAYER_A:
                return s, 0.0, False
            b_act = self.opponent.draft(s, self, rng)
            nb, nbb = apply_draft_action(s.board, s.b, b_act)
            s = GState(nb, s.a, nbb, DRAFT)


def encode_full(s, a_crystal, b_crystal):
    """Full-state feature vector (for later neural use / collapse checks).

    Includes tops AND facings AND ownership AND crystals AND phase. A tops-only
    encoder (Phase 7) deliberately drops facings; this one must not.
    """
    feats = []
    feats.extend(s.board)
    for cru in (s.a, s.b):
        flat = []
        for (top, facing) in cru:
            flat.extend((top, facing))
        flat.extend([0, 0] * (3 - len(cru)))  # pad to 3 dice
        feats.extend(flat)
    feats.extend(a_crystal)
    feats.extend(b_crystal)
    feats.append(0 if s.phase == DRAFT else 1)
    return tuple(feats)
