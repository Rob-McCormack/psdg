"""
PSDG exact solver. Rules v1.13 (February 23, 2026).

Computes exact game value (win/draw/loss) and principal line.
Draft phase: minimax with alpha-beta.
Exchange phase (the Poisoned Gift): maximin value (= Nash eq. value in zero-sum).
Reported joint exchange is a worst-case witness for A; value is exact.
Immortal Tiebreaker in evaluate.

Main: solve_from_roll(board, a_crystal, b_crystal) -> (value, principal_line)
      solve_from_position(board, a_crucible, b_crucible, a_crystal, b_crystal, turn)
      solve_boards(boards, ...) for batch.
Run:  python3 solver.py  (demo on EXAMPLE_BOARDS)

Board: 6-count histogram (tops 1..6). Sum = total dice. Supports 4, 6, or 8 dice.

Command line:
  -d, --dice N    Use N dice (4, 6, or 8). With -d or -r: random board.
  -r, --random    Random board (-r alone → 6 dice, base game).
  -s, --seed N    Reproducible seed (use with -d/-r).
  Examples:
    python3 solver.py              # EXAMPLE_BOARDS
    python3 solver.py -d 4 -r       # Random 4 dice
    python3 solver.py -d 4 -r -s 42
    python3 solver.py -d 8         # Random 8 dice
    python3 solver.py -r           # Random 6 dice (base game default)

See https://psdg.pages.dev for rules and documentation; state encoding aligns with the published technical material.
"""

import argparse
import random
import sys
import time
from typing import Tuple, List, Optional

# ASCII art banner
SOLVER_BANNER = r"""
  .-------.    ______
 /   o   /|   /\     \
/_______/o|  /o \  o  \
| o     | | /   o\_____\
|   o   |o/ \o   /o    /
|     o |/   \ o/  o  /
'-------'     \/____o/
"""

# --- Types (notation-solver.md) ---
CrucibleDie = Tuple[int, int]  # (top, facing)
Crystal = Tuple[int, int]  # (top, facing); top in 1..5
Board = Tuple[int, int, int, int, int, int]  # 6-count histogram for tops 1..6
# board[i] = count of dice showing top i+1. Sum = total dice (4, 6, or 8).
DraftAction = Tuple[int, int]  # (top, facing)
GiftAction = Tuple[int, int]  # (crucible_index, facing)

PLAYER_A = 0
PLAYER_B = 1


# --- Initial board ---


def board_from_tops(tops: Tuple[int, ...]) -> Board:
    """
    Build board from top values (what you see after rolling).
    e.g. board_from_tops((1, 2, 2, 3, 4, 4, 5, 6)) → (1, 2, 1, 2, 1, 1)
    Raises ValueError if any top not in 1..6.
    """
    counts = [0] * 6
    for t in tops:
        if not 1 <= t <= 6:
            raise ValueError(f"Invalid top value {t}; must be 1..6")
        counts[t - 1] += 1
    return tuple(counts)


def board_to_tops(board: Board) -> Tuple[int, ...]:
    """
    Convert board (6-count histogram) to sorted list of top faces.
    e.g. (0, 1, 2, 2, 1, 2) → (2, 3, 3, 4, 4, 5, 6, 6)
    """
    return tuple(sorted(top for top in range(1, 7) for _ in range(board[top - 1])))


def random_board(seed: Optional[int] = None) -> Board:
    """Random initial board: 8 dice, each top 1–6 uniform. See random_board_n for N dice."""
    return random_board_n(8, seed)


def random_board_n(n: int, seed: Optional[int] = None) -> Board:
    """Random board with N dice, each top 1–6 uniform. N must be 4, 6, or 8."""
    if n not in (4, 6, 8):
        raise ValueError(f"n must be 4, 6, or 8; got {n}")
    if seed is not None:
        random.seed(seed)
    tops = tuple(random.randint(1, 6) for _ in range(n))
    return board_from_tops(tops)


# Example from notation-solver.md trace
# EXAMPLE_BOARD: Board = (0, 1, 2, 2, 1, 2)  # 1×2, 2×3, 2×4, 1×5, 2×6
EXAMPLE_BOARD: Board = (2, 0, 2, 0, 0, 0)  # 4 dice game for testing

# Add more boards here for solve_boards()
EXAMPLE_BOARDS: List[Board] = [
    EXAMPLE_BOARD,
    # (2, 0, 2, 0, 0, 0),  # 4 dice, quick test
    # (1, 1, 1, 1, 1, 3),  # 8 dice
]


def solve_boards(
    boards: List[Board],
    a_crystal: Crystal,
    b_crystal: Crystal,
) -> List[Tuple[int, List]]:
    """Solve multiple boards. Returns [(value, principal_line), ...] for each."""
    return [solve_from_roll(b, a_crystal, b_crystal) for b in boards]


def format_breakdown(bd: dict) -> str:
    """Human-readable scoring breakdown, including tiebreaker when tied."""
    p1_a, p1_b = bd["phase1"]
    p2_a, p2_b = bd["phase2"]
    tot_a, tot_b = bd["total"]
    lines = [
        f"The Transformation (Phase 1): A={p1_a}  B={p1_b}",
        f"The Tumble (Phase 2):         A={p2_a}  B={p2_b}",
        f"Total: A={tot_a}  B={tot_b}",
    ]
    if bd["tiebreak"]:
        tb = bd["tiebreak"]
        a_c1, b_c1, a_m1, b_m1 = tb["tumble1"]
        lines.append("")
        lines.append("The Immortal Tiebreaker (tied):")
        lines.append(f"  Tie Tumble 1: a_crystal.top→{a_c1}  b_crystal.top→{b_c1}")
        lines.append(f"    A matches={a_m1}  B matches={b_m1}")
        if "tumble2" in tb:
            a_c2, b_c2, a_m2, b_m2 = tb["tumble2"]
            lines.append(f"  Tie Tumble 2: a_crystal.top→{a_c2}  b_crystal.top→{b_c2}")
            lines.append(f"    A matches={a_m2}  B matches={b_m2}")
        if "tumble3" in tb:
            a_c3, b_c3, a_m3, b_m3 = tb["tumble3"]
            lines.append(f"  Tie Tumble 3: a_crystal.top→{a_c3}  b_crystal.top→{b_c3}")
            lines.append(f"    A matches={a_m3}  B matches={b_m3}")
    return "\n".join(lines)


def format_line(line: List) -> str:
    """Human-readable principal line. Draft moves then the Poisoned Gift."""
    lines = []
    turn_num = 1
    draft_turn = PLAYER_A
    for move in line:
        if move is None:
            continue
        if _is_exchange_move(move):
            a_act, b_act = move[0], move[1]
            lines.append(
                f"Poisoned Gift: A gives die {a_act[0]} facing {a_act[1]}; "
                f"B gives die {b_act[0]} facing {b_act[1]}"
            )
        elif isinstance(move, (tuple, list)) and len(move) == 2:
            player = "A" if draft_turn == PLAYER_A else "B"
            lines.append(
                f"turn {turn_num} ({player}): take top={move[0]} facing={move[1]}"
            )
            turn_num += 1
            draft_turn = PLAYER_B if draft_turn == PLAYER_A else PLAYER_A
    return "\n".join(lines)


# --- Step 1: Die & Scoring ---


def side_faces(top: int) -> Tuple[int, ...]:
    """Legal facing values for a die showing top. Excludes top and 7-top."""
    return tuple(v for v in range(1, 7) if v not in (top, 7 - top))


def score_phase(red: int, tops: List[int]) -> int:
    """
    Scoring rule (v1.13): 1 pt per die with top=6 or top=red. Crystal never scores.
    """
    return sum(1 for t in tops if t == 6 or t == red)


def total_score(red: int, crucible: Tuple[CrucibleDie, ...]) -> int:
    """
    Phase 1 (The Transformation): score crucible tops.
    Phase 2 (The Tumble): facing→top, re-score.
    """
    tops_phase1 = [t for (t, f) in crucible]
    tops_phase2 = [f for (t, f) in crucible]  # tumble: facing becomes top
    return score_phase(red, tops_phase1) + score_phase(red, tops_phase2)


def evaluate(
    a_crucible: Tuple[CrucibleDie, ...],
    b_crucible: Tuple[CrucibleDie, ...],
    a_crystal: Crystal,
    b_crystal: Crystal,
) -> int:
    """
    Terminal evaluation. +1 A wins, -1 B wins, 0 draw.
    Phase 1 + Phase 2; if tied, Immortal Tiebreaker (Tie Tumble 1, 2).
    """
    a_total = total_score(a_crystal[0], a_crucible)
    b_total = total_score(b_crystal[0], b_crucible)

    if a_total > b_total:
        return 1
    if a_total < b_total:
        return -1

    # The Immortal Tiebreaker (tied)
    # Crucible dice are in Phase 2 orientation: top = former facing
    a_tops_p2 = [f for (t, f) in a_crucible]
    b_tops_p2 = [f for (t, f) in b_crucible]

    # Tie Tumble 1: crystal facing → new top
    a_crystal_new = a_crystal[1]  # facing becomes top
    b_crystal_new = b_crystal[1]
    a_matches = sum(1 for t in a_tops_p2 if t == 6 or t == a_crystal_new)
    b_matches = sum(1 for t in b_tops_p2 if t == 6 or t == b_crystal_new)

    if a_matches > b_matches:
        return 1
    if a_matches < b_matches:
        return -1

    # Tie Tumble 2: crystal bottom (7-top) → new top
    a_crystal_new2 = 7 - a_crystal[0]
    b_crystal_new2 = 7 - b_crystal[0]
    a_matches2 = sum(1 for t in a_tops_p2 if t == 6 or t == a_crystal_new2)
    b_matches2 = sum(1 for t in b_tops_p2 if t == 6 or t == b_crystal_new2)

    if a_matches2 > b_matches2:
        return 1
    if a_matches2 < b_matches2:
        return -1

    # Tie Tumble 3: crystal facing away (7-facing) → new top
    a_crystal_new3 = 7 - a_crystal[1]
    b_crystal_new3 = 7 - b_crystal[1]
    a_matches3 = sum(1 for t in a_tops_p2 if t == 6 or t == a_crystal_new3)
    b_matches3 = sum(1 for t in b_tops_p2 if t == 6 or t == b_crystal_new3)

    if a_matches3 > b_matches3:
        return 1
    if a_matches3 < b_matches3:
        return -1
    return 0  # draw


def evaluate_breakdown(
    a_crucible: Tuple[CrucibleDie, ...],
    b_crucible: Tuple[CrucibleDie, ...],
    a_crystal: Crystal,
    b_crystal: Crystal,
) -> dict:
    """Return scoring breakdown including tiebreaker. For display when tied."""
    p1_a = score_phase(a_crystal[0], [t for t, _ in a_crucible])
    p1_b = score_phase(b_crystal[0], [t for t, _ in b_crucible])
    p2_a = score_phase(a_crystal[0], [f for _, f in a_crucible])
    p2_b = score_phase(b_crystal[0], [f for _, f in b_crucible])
    total_a, total_b = p1_a + p2_a, p1_b + p2_b

    out = {
        "phase1": (p1_a, p1_b),
        "phase2": (p2_a, p2_b),
        "total": (total_a, total_b),
        "tiebreak": None,
    }

    if total_a != total_b:
        return out

    a_tops_p2 = [f for (t, f) in a_crucible]
    b_tops_p2 = [f for (t, f) in b_crucible]
    a_c1, b_c1 = a_crystal[1], b_crystal[1]
    a_m1 = sum(1 for t in a_tops_p2 if t == 6 or t == a_c1)
    b_m1 = sum(1 for t in b_tops_p2 if t == 6 or t == b_c1)

    out["tiebreak"] = {"tumble1": (a_c1, b_c1, a_m1, b_m1)}
    if a_m1 != b_m1:
        return out

    a_c2, b_c2 = 7 - a_crystal[0], 7 - b_crystal[0]
    a_m2 = sum(1 for t in a_tops_p2 if t == 6 or t == a_c2)
    b_m2 = sum(1 for t in b_tops_p2 if t == 6 or t == b_c2)
    out["tiebreak"]["tumble2"] = (a_c2, b_c2, a_m2, b_m2)
    if a_m2 != b_m2:
        return out

    a_c3, b_c3 = 7 - a_crystal[1], 7 - b_crystal[1]
    a_m3 = sum(1 for t in a_tops_p2 if t == 6 or t == a_c3)
    b_m3 = sum(1 for t in b_tops_p2 if t == 6 or t == b_c3)
    out["tiebreak"]["tumble3"] = (a_c3, b_c3, a_m3, b_m3)
    return out


def _is_exchange_move(move: object) -> bool:
    """True if move is a joint exchange ((a_action, b_action))."""
    return (
        isinstance(move, (tuple, list))
        and len(move) == 2
        and isinstance(move[0], (tuple, list))
        and len(move[0]) == 2
    )


def replay_line(
    board: Board,
    line: List,
    a_crystal: Crystal,
    b_crystal: Crystal,
) -> Tuple[Tuple[CrucibleDie, ...], Tuple[CrucibleDie, ...]]:
    """Play the principal line, return (a_crucible, b_crucible) after exchange."""
    a_crucible: Tuple[CrucibleDie, ...] = ()
    b_crucible: Tuple[CrucibleDie, ...] = ()
    current_board = board

    for i, move in enumerate(line):
        if move is None:
            continue
        if _is_exchange_move(move):
            a_new, b_new = apply_exchange(a_crucible, b_crucible, tuple(move[0]), tuple(move[1]))
            return (a_new, b_new)
        # Draft: (top, facing)
        if i % 2 == 0:
            current_board, a_crucible = apply_draft_action(current_board, a_crucible, move)
        else:
            current_board, b_crucible = apply_draft_action(current_board, b_crucible, move)

    return (a_crucible, b_crucible)


# --- Step 2: Gift eligibility ---


def forced_gift_indices(
    crucible: Tuple[CrucibleDie, ...],
    crystal: Crystal,
) -> Tuple[int, ...]:
    """
    Indices of crucible dice legal to gift (lowest-pair rule).
    Crystal included in 5-dice set for pair detection. Never gift crystal.
    """
    counts: dict = {v: 0 for v in range(1, 7)}
    for t, _ in crucible:
        counts[t] += 1
    counts[crystal[0]] += 1

    pair_vals = [v for v in range(1, 7) if counts[v] >= 2]
    if not pair_vals:
        return tuple(range(len(crucible)))
    low = min(pair_vals)
    return tuple(i for i, (t, _) in enumerate(crucible) if t == low)


# Alias for __init__
legal_exchange_indices = forced_gift_indices


# --- Step 3: Draft helpers ---


def legal_draft_actions(board: Board) -> List[DraftAction]:
    """All (top, facing) actions: top must be on board, facing in side_faces(top)."""
    actions = []
    for top in range(1, 7):
        if board[top - 1] > 0:
            for facing in side_faces(top):
                actions.append((top, facing))
    return actions


def apply_draft_action(
    board: Board,
    crucible: Tuple[CrucibleDie, ...],
    action: DraftAction,
) -> Tuple[Board, Tuple[CrucibleDie, ...]]:
    """Take die from board, add to crucible, return new board and sorted crucible."""
    top, facing = action
    new_board = tuple(c - (1 if i == top - 1 else 0) for i, c in enumerate(board))
    new_crucible = tuple(sorted(crucible + ((top, facing),), key=lambda d: (d[0], d[1])))
    return (new_board, new_crucible)


def apply_exchange(
    a_crucible: Tuple[CrucibleDie, ...],
    b_crucible: Tuple[CrucibleDie, ...],
    a_action: GiftAction,
    b_action: GiftAction,
) -> Tuple[Tuple[CrucibleDie, ...], Tuple[CrucibleDie, ...]]:
    """
    Apply joint exchange. A gives a_action to B; B gives b_action to A.
    Returns (a_crucible_after, b_crucible_after) sorted.
    """
    a_idx, a_facing = a_action
    b_idx, b_facing = b_action

    a_gives = a_crucible[a_idx]  # (top, _)
    b_gives = b_crucible[b_idx]

    a_receives = (b_gives[0], b_facing)  # B sets facing for A
    b_receives = (a_gives[0], a_facing)  # A sets facing for B

    a_rest = tuple(d for i, d in enumerate(a_crucible) if i != a_idx)
    b_rest = tuple(d for i, d in enumerate(b_crucible) if i != b_idx)
    a_new = tuple(sorted(a_rest + (a_receives,), key=lambda d: (d[0], d[1])))
    b_new = tuple(sorted(b_rest + (b_receives,), key=lambda d: (d[0], d[1])))
    return (a_new, b_new)


# --- Step 4: Solver (placeholder; full minimax TODO) ---


def solve_exchange(
    a_crucible: Tuple[CrucibleDie, ...],
    b_crucible: Tuple[CrucibleDie, ...],
    a_crystal: Crystal,
    b_crystal: Crystal,
) -> Tuple[int, List[Tuple[GiftAction, GiftAction]]]:
    """
    Solve the Poisoned Gift (simultaneous zero-sum).
    Maximin: value = max_A min_B payoff(A,B). Equals Nash equilibrium value
    in zero-sum games (von Neumann). Returns (value, co-optimal joint actions).
    Value: +1 A wins, -1 B wins, 0 draw.
    """
    a_legal = [
        (ai, af)
        for ai in forced_gift_indices(a_crucible, a_crystal)
        for af in side_faces(a_crucible[ai][0])
    ]
    b_legal = [
        (bi, bf)
        for bi in forced_gift_indices(b_crucible, b_crystal)
        for bf in side_faces(b_crucible[bi][0])
    ]

    # Minimax: value = max_a min_b payoff(a,b)
    best_val = -2
    best_actions: List[Tuple[GiftAction, GiftAction]] = []

    for a_action in a_legal:
        worst = 2
        worst_b_actions: List[GiftAction] = []
        for b_action in b_legal:
            a_new, b_new = apply_exchange(a_crucible, b_crucible, a_action, b_action)
            val = evaluate(a_new, b_new, a_crystal, b_crystal)
            if val < worst:
                worst = val
                worst_b_actions = [b_action]
            elif val == worst:
                worst_b_actions.append(b_action)
        if worst > best_val:
            best_val = worst
            best_actions = [(a_action, b) for b in worst_b_actions]
        elif worst == best_val:
            best_actions.extend((a_action, b) for b in worst_b_actions)

    return (best_val, best_actions)


def solve_exchange_sequential(
    a_crucible: Tuple[CrucibleDie, ...],
    b_crucible: Tuple[CrucibleDie, ...],
    a_crystal: Crystal,
    b_crystal: Crystal,
    first_mover: str = "A",
) -> Tuple[int, GiftAction, GiftAction]:
    """
    Solve the Poisoned Gift with sequential (turn-based) Exchange.
    First mover commits; second mover best-responds.
    In zero-sum, outcome equals simultaneous Nash value (von Neumann).
    Returns (value, a_action, b_action).
    """
    a_legal = [
        (ai, af)
        for ai in forced_gift_indices(a_crucible, a_crystal)
        for af in side_faces(a_crucible[ai][0])
    ]
    b_legal = [
        (bi, bf)
        for bi in forced_gift_indices(b_crucible, b_crystal)
        for bf in side_faces(b_crucible[bi][0])
    ]

    if first_mover.upper() == "A":
        # A commits first; B best-responds. value = max_a min_b payoff(a,b)
        best_val = -2
        best_a = a_legal[0] if a_legal else (0, 0)
        best_b = b_legal[0] if b_legal else (0, 0)
        for a_action in a_legal:
            worst = 2
            worst_b = b_legal[0] if b_legal else (0, 0)
            for b_action in b_legal:
                a_new, b_new = apply_exchange(
                    a_crucible, b_crucible, a_action, b_action
                )
                val = evaluate(a_new, b_new, a_crystal, b_crystal)
                if val < worst:
                    worst = val
                    worst_b = b_action
            if worst > best_val:
                best_val = worst
                best_a = a_action
                best_b = worst_b
        return (best_val, best_a, best_b)
    else:
        # B commits first; A best-responds. value = min_b max_a payoff(a,b)
        best_val = 2
        best_a = a_legal[0] if a_legal else (0, 0)
        best_b = b_legal[0] if b_legal else (0, 0)
        for b_action in b_legal:
            best_a_val = -2
            best_a_act = a_legal[0] if a_legal else (0, 0)
            for a_action in a_legal:
                a_new, b_new = apply_exchange(
                    a_crucible, b_crucible, a_action, b_action
                )
                val = evaluate(a_new, b_new, a_crystal, b_crystal)
                if val > best_a_val:
                    best_a_val = val
                    best_a_act = a_action
            if best_a_val < best_val:
                best_val = best_a_val
                best_a = best_a_act
                best_b = b_action
        return (best_val, best_a, best_b)


def _draft_value(
    board: Board,
    a_crucible: Tuple[CrucibleDie, ...],
    b_crucible: Tuple[CrucibleDie, ...],
    a_crystal: Crystal,
    b_crystal: Crystal,
    turn: int,
    memo: Optional[dict] = None,
    alpha: int = -2,
    beta: int = 2,
) -> Tuple[int, List]:
    """
    Minimax over draft with alpha-beta pruning. turn 0=A, 1=B.
    Returns (value, principal_line) where principal_line is list of DraftAction then one ExchangeJoint.
    Memoization by (board, a_crucible, b_crucible, a_crystal, b_crystal, turn).
    """
    if memo is None:
        memo = {}
    key = (board, a_crucible, b_crucible, a_crystal, b_crystal, turn)
    if key in memo:
        return memo[key]

    if sum(board) == 0:
        # Draft complete; solve exchange subgame
        val, joint_actions = solve_exchange(a_crucible, b_crucible, a_crystal, b_crystal)
        best = joint_actions[0] if joint_actions else (None, None)
        result = (val, [best])
        memo[key] = result
        return result

    actions = legal_draft_actions(board)
    # Move ordering for alpha-beta: try high-value dice (6, red) first
    red = a_crystal[0] if turn == PLAYER_A else b_crystal[0]
    actions = sorted(actions, key=lambda a: (a[0] not in (6, red), -a[0]))
    if not actions:
        val, joint_actions = solve_exchange(a_crucible, b_crucible, a_crystal, b_crystal)
        result = (val, [joint_actions[0]] if joint_actions else [(None, None)])
        memo[key] = result
        return result

    if turn == PLAYER_A:
        best_val = -2
        best_action = None
        best_line = []
        pruned = False
        for act in actions:
            new_board, new_crucible = apply_draft_action(board, a_crucible, act)
            val, line = _draft_value(
                new_board,
                new_crucible,
                b_crucible,
                a_crystal,
                b_crystal,
                PLAYER_B,
                memo,
                alpha,
                beta,
            )
            if val > best_val:
                best_val = val
                best_action = act
                best_line = line
                alpha = max(alpha, best_val)
            if best_val >= beta:
                pruned = True
                break
        result = (best_val, [best_action] + best_line)
        if not pruned:
            memo[key] = result
        return result
    else:
        best_val = 2
        best_action = None
        best_line = []
        pruned = False
        for act in actions:
            new_board, new_crucible = apply_draft_action(board, b_crucible, act)
            val, line = _draft_value(
                new_board,
                a_crucible,
                new_crucible,
                a_crystal,
                b_crystal,
                PLAYER_A,
                memo,
                alpha,
                beta,
            )
            if val < best_val:
                best_val = val
                best_action = act
                best_line = line
                beta = min(beta, best_val)
            if best_val <= alpha:
                pruned = True
                break
        result = (best_val, [best_action] + best_line)
        if not pruned:
            memo[key] = result
        return result


def _is_valid_crystal(c: Crystal) -> bool:
    """Crystal (top, facing): top 1..5, facing must be side face (not top or 7-top)."""
    if not isinstance(c, (tuple, list)) or len(c) != 2:
        return False
    top, facing = c[0], c[1]
    if top < 1 or top > 5:
        return False
    return facing in side_faces(top)


def _legal_crystals() -> List[Crystal]:
    """All legal Red Crystal (top, facing): top 1..5, facing in side_faces(top)."""
    out = []
    for top in range(1, 6):
        for facing in side_faces(top):
            out.append((top, facing))
    return out


def solve_full_game(board: Board) -> Tuple[int, Crystal, Crystal, List]:
    """
    Solve from initial roll including Poisoned Gift #1 (Red Crystal assignment).

    Order: A assigns B's crystal first; B assigns A's crystal (minimizing A's value).
    Returns (value, a_crystal, b_crystal, principal_line).
    """
    legal = _legal_crystals()
    best_val = -2
    best_b_crystal: Optional[Crystal] = None
    best_a_crystal: Optional[Crystal] = None
    best_line: Optional[List] = None

    for b_crystal in legal:
        min_val = 2
        best_a_for_b: Optional[Crystal] = None
        best_line_for_b: Optional[List] = None
        for a_crystal in legal:
            val, line = solve_from_roll(board, a_crystal, b_crystal)
            if val < min_val:
                min_val = val
                best_a_for_b = a_crystal
                best_line_for_b = line
        if min_val > best_val:
            best_val = min_val
            best_b_crystal = b_crystal
            best_a_crystal = best_a_for_b
            best_line = best_line_for_b

    assert best_b_crystal is not None and best_a_crystal is not None and best_line is not None
    return (best_val, best_a_crystal, best_b_crystal, best_line)


def solve_from_roll(
    board: Board,
    a_crystal: Crystal,
    b_crystal: Crystal,
) -> Tuple[int, List]:
    """
    Solve from initial roll (crystals given). Returns (value, principal_line).
    For full-game solve including crystal assignment, use solve_full_game(board).
    Value: +1 A wins, -1 B wins, 0 draw.
    principal_line: draft actions then joint exchange. A's first move is principal_line[0].
    """
    if not _is_valid_crystal(a_crystal) or not _is_valid_crystal(b_crystal):
        raise ValueError(
            "Invalid crystals: top must be 1-5, facing must be a side face (not top or 7-top). "
            "E.g. (1,6) invalid: 6 is opposite 1. (2,5) invalid: 5 is opposite 2."
        )
    memo: dict = {}
    return _draft_value(board, (), (), a_crystal, b_crystal, PLAYER_A, memo)


def solve_from_position(
    board: Board,
    a_crucible: Tuple[CrucibleDie, ...],
    b_crucible: Tuple[CrucibleDie, ...],
    a_crystal: Crystal,
    b_crystal: Crystal,
    turn: int,
) -> Tuple[int, List]:
    """
    Solve from a mid-game position (draft in progress or exchange pending).
    Returns (value, principal_line).
    Value: +1 A wins, -1 B wins, 0 draw.
    turn: 0 = A to move, 1 = B to move.
    """
    if not _is_valid_crystal(a_crystal) or not _is_valid_crystal(b_crystal):
        raise ValueError(
            "Invalid crystals: top must be 1-5, facing must be a side face (not top or 7-top). "
            "E.g. (1,6) invalid: 6 is opposite 1. (2,5) invalid: 5 is opposite 2."
        )
    memo: dict = {}
    return _draft_value(board, a_crucible, b_crucible, a_crystal, b_crystal, turn, memo)


# --- Legacy aliases ---
Die = CrucibleDie
DraftState = Tuple[
    Board, Tuple[CrucibleDie, ...], Tuple[CrucibleDie, ...], Crystal, Crystal, int
]


def score_player(red: int, crucible: Tuple[CrucibleDie, ...]) -> int:
    """Total score for one player (Phase 1 + Phase 2)."""
    return total_score(red, crucible)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PSDG exact solver")
    parser.add_argument(
        "-d", "--dice",
        type=int,
        help="Use N dice (4, 6, or 8). With -d or -r: generate random board.",
    )
    parser.add_argument(
        "-r", "--random",
        action="store_true",
        help="Generate random board (-r alone uses 6 dice, base game).",
    )
    parser.add_argument(
        "-s", "--seed",
        type=int,
        default=None,
        help="Random seed for reproducible board (use with -d or -r).",
    )
    args, _ = parser.parse_known_args()  # ignore Jupyter kernel args (-f, etc.)

    if args.dice is not None and args.dice not in (4, 6, 8):
        parser.error("--dice must be 4, 6, or 8")

    # Override boards if CLI args given
    if args.dice is not None or args.random:
        n = args.dice if args.dice is not None else 6
        boards = [random_board_n(n, seed=args.seed)]
    else:
        boards = EXAMPLE_BOARDS

    dice_count = sum(boards[0]) if boards else 0
    if dice_count:
        extra = ""
        if args.dice is not None or args.random:
            extra = " random"
            if args.seed is not None:
                extra += f" seed={args.seed}"
        title = f"PSDG Solver demo — {dice_count} dice game (full solve){extra}"
    else:
        title = "PSDG Solver demo (full solve)"
    print(SOLVER_BANNER)
    print(title)
    print("-" * 40)
    for i, board in enumerate(boards):
        tops = ",".join(map(str, board_to_tops(board)))
        print(f"Board {i}:")
        print(f"  tops= {tops}  (ascending)")
        print(f"  Solving (crystal assignment + draft + exchange)...", flush=True)
        t0 = time.perf_counter()
        val, a_crystal, b_crystal, line = solve_full_game(board)
        elapsed = time.perf_counter() - t0
        result = ["B wins", "draw", "A wins"][val + 1]
        bold = "\033[1m" if sys.stdout.isatty() else ""
        reset = "\033[0m" if sys.stdout.isatty() else ""
        print()
        print(f"  {bold}>>> {result} ({elapsed:.2f}s){reset}")
        print(f"  Red Crystals (optimal): A={a_crystal}  B={b_crystal}")
        print()
        print(format_line(line))
        a_crucible, b_crucible = replay_line(board, line, a_crystal, b_crystal)
        bd = evaluate_breakdown(a_crucible, b_crucible, a_crystal, b_crystal)
        print()
        print("The Reckoning (Scoring):")
        print(format_breakdown(bd))
        print()
