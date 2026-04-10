"""
Oracle API wrapper for PSDG solver.

Thin interface over solver.py. Use this for benchmarks, agents, and notebooks
instead of calling solver internals directly.

API:
  value(state)         -> int: game-theoretic value (+1 A wins, -1 B wins, 0 draw)
  best_actions(state)  -> list: optimal action(s) from this state
  is_legal(state, action) -> bool: whether action is legal in state
  delta(state, action) -> int: value lost by playing action vs optimal (0 = optimal)

State format: (board, a_crucible, b_crucible, a_crystal, b_crystal, turn)
  Dict: board, a_crucible, b_crucible (or legacy a_hoard, b_hoard), crystals, turn.
  State encoding matches the published PSDG material (https://psdg.pages.dev).
  - board: Tuple[int,...] 6-count histogram for tops 1..6
  - a_crucible, b_crucible: Tuple[(top,facing), ...] sorted (each player's drafted dice)
  - a_crystal, b_crystal: (top, facing); top in 1..5
  - turn: 0 = A to move, 1 = B to move
  - When board is empty (sum==0), we are at Exchange; best_actions returns joint exchange.

Actions:
  - Draft: (top, facing)
  - Exchange: ((a_idx, a_facing), (b_idx, b_facing)) joint

solver.py is standalone; oracle.py imports from it (same directory).
"""

import os
import sys

# Allow importing solver when run from this directory
try:
    _here = os.path.dirname(os.path.abspath(__file__))
    if _here and _here not in sys.path:
        sys.path.insert(0, _here)
except NameError:
    # Notebook cell: no __file__; try cwd for solver.py
    for _dir in (os.getcwd(), "/content"):
        if _dir and _dir not in sys.path:
            sys.path.insert(0, _dir)

from solver import (
    PLAYER_A,
    PLAYER_B,
    apply_draft_action,
    apply_exchange,
    evaluate,
    forced_gift_indices,
    legal_draft_actions,
    side_faces,
    solve_exchange,
    solve_from_position,
)


def _unpack_state(state):
    """Extract (board, a_crucible, b_crucible, a_crystal, b_crystal, turn) from state."""
    if isinstance(state, dict):
        # Dict keys: prefer a_crucible/b_crucible; a_hoard/b_hoard still accepted
        a_key = "a_crucible" if "a_crucible" in state else "a_hoard"
        b_key = "b_crucible" if "b_crucible" in state else "b_hoard"
        return (
            tuple(state["board"]),
            tuple(tuple(d) for d in state[a_key]),
            tuple(tuple(d) for d in state[b_key]),
            tuple(state["a_crystal"]),
            tuple(state["b_crystal"]),
            state["turn"],
        )
    return tuple(state)


def _is_exchange_state(state):
    """True if state is at Exchange (draft complete, board empty)."""
    board, a_crucible, b_crucible, a_crystal, b_crystal, turn = _unpack_state(state)
    return sum(board) == 0 and len(a_crucible) > 0 and len(a_crucible) == len(b_crucible)


def value(state):
    """
    Game-theoretic value from state (+1 A wins, -1 B wins, 0 draw).
    Value is from A's perspective.
    """
    board, a_crucible, b_crucible, a_crystal, b_crystal, turn = _unpack_state(state)
    if _is_exchange_state(state):
        val, _ = solve_exchange(a_crucible, b_crucible, a_crystal, b_crystal)
        return val
    val, _ = solve_from_position(
        board, a_crucible, b_crucible, a_crystal, b_crystal, turn
    )
    return val


def best_actions(state):
    """
    Optimal action(s) from state.
    Draft phase: returns list of (top, facing) moves.
    Exchange phase: returns list of ((a_act, b_act),) joint actions.
    """
    board, a_crucible, b_crucible, a_crystal, b_crystal, turn = _unpack_state(state)
    if _is_exchange_state(state):
        _, joint_actions = solve_exchange(a_crucible, b_crucible, a_crystal, b_crystal)
        return [tuple(ja) for ja in joint_actions] if joint_actions else []
    _, line = solve_from_position(
        board, a_crucible, b_crucible, a_crystal, b_crystal, turn
    )
    # First element is current player's move
    out = []
    for m in line:
        if m is None:
            continue
        if _is_exchange_move(m):
            out.append(tuple(m))
            break
        # Draft move
        out.append(tuple(m))
        break
    return out


def _is_exchange_move(move):
    return (
        isinstance(move, (tuple, list))
        and len(move) == 2
        and isinstance(move[0], (tuple, list))
        and len(move[0]) == 2
    )


def is_legal(state, action):
    """
    Whether action is legal in state.
    Draft: action = (top, facing); checks board and turn.
    Exchange: action = ((a_idx, a_facing), (b_idx, b_facing)); checks both.
    """
    board, a_crucible, b_crucible, a_crystal, b_crystal, turn = _unpack_state(state)
    if _is_exchange_state(state):
        if not (
            isinstance(action, (tuple, list))
            and len(action) == 2
            and isinstance(action[0], (tuple, list))
        ):
            return False
        a_act, b_act = tuple(action[0]), tuple(action[1])
        # A legal
        a_legal_idx = forced_gift_indices(a_crucible, a_crystal)
        if a_act[0] not in a_legal_idx:
            return False
        if a_act[1] not in side_faces(a_crucible[a_act[0]][0]):
            return False
        # B legal
        b_legal_idx = forced_gift_indices(b_crucible, b_crystal)
        if b_act[0] not in b_legal_idx:
            return False
        if b_act[1] not in side_faces(b_crucible[b_act[0]][0]):
            return False
        return True
    # Draft
    if not (isinstance(action, (tuple, list)) and len(action) == 2):
        return False
    top, facing = action[0], action[1]
    legal = legal_draft_actions(board)
    return (top, facing) in legal


def delta(state, action):
    """
    Value lost by playing action vs optimal. 0 = optimal.
    From A's perspective: delta = value(state) - value_after_action.
    """
    board, a_crucible, b_crucible, a_crystal, b_crystal, turn = _unpack_state(state)
    opt_val = value(state)
    if _is_exchange_state(state):
        a_act, b_act = tuple(action[0]), tuple(action[1])
        a_new, b_new = apply_exchange(a_crucible, b_crucible, a_act, b_act)
        actual = evaluate(a_new, b_new, a_crystal, b_crystal)
        return opt_val - actual
    # Draft
    top, facing = action[0], action[1]
    if turn == PLAYER_A:
        new_board, new_a_crucible = apply_draft_action(board, a_crucible, (top, facing))
        new_state = (new_board, new_a_crucible, b_crucible, a_crystal, b_crystal, PLAYER_B)
    else:
        new_board, new_b_crucible = apply_draft_action(board, b_crucible, (top, facing))
        new_state = (new_board, a_crucible, new_b_crucible, a_crystal, b_crystal, PLAYER_A)
    val_after = value(new_state)
    return opt_val - val_after


# --- Convenience: solve from initial roll ---


def value_from_roll(board, a_crystal, b_crystal):
    """Value from initial roll (empty crucibles)."""
    return value((board, (), (), a_crystal, b_crystal, PLAYER_A))


def best_actions_from_roll(board, a_crystal, b_crystal):
    """Best actions from initial roll (A's first move)."""
    return best_actions((board, (), (), a_crystal, b_crystal, PLAYER_A))


# --- Optional: Oracle class for stateful use ---


class Oracle:
    """
    Oracle instance. Holds default crystals; state is passed to each method.
    """

    def __init__(self, a_crystal=(4, 6), b_crystal=(2, 1)):
        self.a_crystal = tuple(a_crystal)
        self.b_crystal = tuple(b_crystal)

    def value(self, state):
        return value(state)

    def best_actions(self, state):
        return best_actions(state)

    def is_legal(self, state, action):
        return is_legal(state, action)

    def delta(self, state, action):
        return delta(state, action)


if __name__ == "__main__":
    # Quick demo
    from solver import EXAMPLE_BOARD

    A_CRYSTAL, B_CRYSTAL = (4, 6), (2, 1)  # (2,5) invalid: 5 is opposite 2
    state = (EXAMPLE_BOARD, (), (), A_CRYSTAL, B_CRYSTAL, PLAYER_A)
    print("Oracle API demo")
    print("=" * 40)
    print(f"Board: {EXAMPLE_BOARD}")
    v = value(state)
    print(f"value(state) = {v}  ({['B wins', 'draw', 'A wins'][v+1]})")
    acts = best_actions(state)
    print(f"best_actions(state) = {acts}")
    if acts:
        a = acts[0]
        print(f"is_legal(state, {a}) = {is_legal(state, a)}")
        print(f"delta(state, {a}) = {delta(state, a)}")
    print()
    print("value_from_roll:", value_from_roll(EXAMPLE_BOARD, A_CRYSTAL, B_CRYSTAL))
    print("OK")
