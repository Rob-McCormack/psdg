#!/usr/bin/env python3
"""
Evaluate an agent against the PSDG oracle. Computes core metrics:

- mean_regret: average value lost per move (delta) when agent plays
- catastrophic_error_rate: % of moves that converted win→draw/loss or draw→loss
- draw_preservation_rate: of games starting draw, % that ended draw or win for A
- conversion_rate: of games starting win-for-A, % that ended win for A

Usage:
  python3 evaluate_agent.py <benchmark.json> <policy>
  policy: "random" | "oracle" | "greedy"

Example:
  python3 evaluate_agent.py benchmark.json random
"""

import json
import os
import random
import sys
from typing import Callable, List, Tuple

# Add solvers to path
_here = os.path.dirname(os.path.abspath(__file__))
_solvers = os.path.join(_here, "..", "solvers", "python")
if _solvers not in sys.path:
    sys.path.insert(0, _solvers)

from solver import (
    PLAYER_A,
    PLAYER_B,
    apply_draft_action,
    apply_exchange,
    evaluate,
    evaluate_breakdown,
    forced_gift_indices,
    legal_draft_actions,
    random_board_n,
    side_faces,
    solve_exchange,
)
from oracle import value, best_actions, delta, is_legal


def _is_exchange_state(state):
    board, a_crucible, b_crucible, _, _, _ = state
    return sum(board) == 0 and len(a_crucible) == len(b_crucible) and len(a_crucible) > 0


def _best_response_b(a_crucible, b_crucible, a_crystal, b_crystal, a_act):
    """B's best response (minimizes A's payoff) given A's exchange action."""
    b_legal_idx = forced_gift_indices(b_crucible, b_crystal)
    best_b = None
    best_val = 2
    for bi in b_legal_idx:
        for bf in side_faces(b_crucible[bi][0]):
            b_act = (bi, bf)
            a_new, b_new = apply_exchange(a_crucible, b_crucible, a_act, b_act)
            val = evaluate(a_new, b_new, a_crystal, b_crystal)
            if val < best_val:
                best_val = val
                best_b = b_act
    return best_b


# --- Policy: oracle (optimal) ---
def policy_oracle(state):
    acts = best_actions(state)
    if not acts:
        return None
    return acts[0]


# --- Policy: random legal ---
def policy_random(state):
    if _is_exchange_state(state):
        board, a_crucible, b_crucible, a_crystal, b_crystal, turn = state
        a_legal_idx = forced_gift_indices(a_crucible, a_crystal)
        ai = random.choice(list(a_legal_idx))
        af = random.choice(list(side_faces(a_crucible[ai][0])))
        a_act = (ai, af)
        b_act = _best_response_b(a_crucible, b_crucible, a_crystal, b_crystal, a_act)
        return (a_act, b_act)
    legal = legal_draft_actions(state[0])
    return random.choice(legal)


# --- Policy: greedy (prefer high top, facing 6) ---
def policy_greedy(state):
    if _is_exchange_state(state):
        board, a_crucible, b_crucible, a_crystal, b_crystal, turn = state
        a_legal_idx = forced_gift_indices(a_crucible, a_crystal)
        # Prefer facing 6 when legal (scores in phase 2)
        candidates = []
        for ai in a_legal_idx:
            top, _ = a_crucible[ai]
            for af in side_faces(top):
                candidates.append((ai, af))
        if not candidates:
            return policy_random(state)
        # Prefer (ai, af) with af=6
        best = max(candidates, key=lambda x: (x[1] == 6, x[1]))
        a_act = best
        b_act = _best_response_b(a_crucible, b_crucible, a_crystal, b_crystal, a_act)
        return (a_act, b_act)
    # Draft: take highest top, set facing to 6 if legal
    legal = legal_draft_actions(state[0])
    sorted_legal = sorted(legal, key=lambda x: (x[0], x[1]), reverse=True)
    return sorted_legal[0]


POLICIES = {
    "oracle": policy_oracle,
    "random": policy_random,
    "greedy": policy_greedy,
}


def run_game(state, policy: Callable) -> Tuple[int, List[dict], tuple, tuple]:
    """
    Run game: agent plays A, oracle plays B.
    Return (final_outcome, moves_a, a_final_crucible, b_final_crucible).
    """
    moves_a = []
    board, a_crucible, b_crucible, a_crystal, b_crystal, turn = state

    while True:
        if _is_exchange_state((board, a_crucible, b_crucible, a_crystal, b_crystal, turn)):
            state = (board, a_crucible, b_crucible, a_crystal, b_crystal, turn)
            action = policy(state)
            if action is None:
                action = policy_random(state)
            d = delta(state, action)
            v_before = value(state)
            moves_a.append({"delta": d, "value_before": v_before})
            a_act, b_act = action[0], action[1]
            a_new, b_new = apply_exchange(a_crucible, b_crucible, a_act, b_act)
            outcome = evaluate(a_new, b_new, a_crystal, b_crystal)
            return outcome, moves_a, a_new, b_new

        if turn == PLAYER_A:
            state = (board, a_crucible, b_crucible, a_crystal, b_crystal, turn)
            action = policy(state)
            if action is None:
                action = policy_random(state)
            d = delta(state, action)
            v_before = value(state)
            moves_a.append({"delta": d, "value_before": v_before})
            top, facing = action
            board, a_crucible = apply_draft_action(board, a_crucible, (top, facing))
            turn = PLAYER_B
        else:
            # B plays optimally
            state = (board, a_crucible, b_crucible, a_crystal, b_crystal, turn)
            b_action = best_actions(state)[0]
            top, facing = b_action
            board, b_crucible = apply_draft_action(board, b_crucible, (top, facing))
            turn = PLAYER_A


def compute_metrics(games: List[dict]) -> dict:
    """Aggregate metrics from list of game results."""
    total_moves = 0
    total_regret = 0
    catastrophic_count = 0
    by_start = {-1: [], 0: [], 1: []}  # outcome lists by oracle value at start

    for g in games:
        start_val = g["start_value"]
        outcome = g["outcome"]
        by_start[start_val].append(outcome)

        for m in g["moves"]:
            total_moves += 1
            d = m["delta"]
            v = m["value_before"]
            total_regret += d
            if d >= 1 and v >= 0:
                catastrophic_count += 1

    n = len(games)
    n_draw_starts = len(by_start[0])
    n_win_starts = len(by_start[1])
    draw_preserved = sum(1 for o in by_start[0] if o >= 0)
    win_converted = sum(1 for o in by_start[1] if o == 1)

    return {
        "n_games": n,
        "mean_regret": total_regret / total_moves if total_moves else 0,
        "total_moves": total_moves,
        "catastrophic_error_count": catastrophic_count,
        "catastrophic_error_rate": catastrophic_count / total_moves if total_moves else 0,
        "draw_preservation_rate": draw_preserved / n_draw_starts if n_draw_starts else None,
        "draw_preservation_n": (draw_preserved, n_draw_starts),
        "conversion_rate": win_converted / n_win_starts if n_win_starts else None,
        "conversion_n": (win_converted, n_win_starts),
        "win_rate": sum(1 for g in games if g["outcome"] == 1) / n if n else 0,
    }


def main():
    if len(sys.argv) < 3:
        print("Usage: evaluate_agent.py <benchmark.json> <policy> [max_games]")
        print("  policy: random | oracle | greedy")
        print("  max_games: optional limit (default 20, or PSDG_EVAL_N env)")
        sys.exit(1)

    path = sys.argv[1]
    policy_name = sys.argv[2].lower()
    if policy_name not in POLICIES:
        print(f"Unknown policy: {policy_name}")
        sys.exit(1)

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    crystals = data["crystals"]
    a_crystal = tuple(crystals["a"])
    b_crystal = tuple(crystals["b"])
    entries = data["entries"]
    policy = POLICIES[policy_name]

    # Prefer 4-dice for speed (8-dice solve is slow per move)
    four_dice = [e for e in entries if e.get("dice", sum(e["board"])) == 4 or sum(e["board"]) == 4]
    if four_dice:
        entries = four_dice
    # Limit games for faster runs (8-dice is slow)
    max_games = int(sys.argv[3]) if len(sys.argv) > 3 else int(os.environ.get("PSDG_EVAL_N", "20"))
    entries = entries[:max_games]

    games = []
    for e in entries:
        if e.get("source") == "random":
            board = random_board_n(e["dice"], e["seed"])
        else:
            board = tuple(e["board"])
        state = (board, (), (), a_crystal, b_crystal, PLAYER_A)
        start_val = value(state)
        outcome, moves, a_final, b_final = run_game(state, policy)
        bd = evaluate_breakdown(a_final, b_final, a_crystal, b_crystal)
        tb_depth = 0
        if bd.get("tiebreak"):
            tb_depth = 2 if "tumble2" in bd["tiebreak"] else 1
        score = {
            "phase1": list(bd["phase1"]),
            "phase2": list(bd["phase2"]),
            "total": list(bd["total"]),
            "tiebreak": {k: list(v) for k, v in bd["tiebreak"].items()} if bd.get("tiebreak") else None,
        }
        games.append({
            "id": e["id"],
            "start_value": start_val,
            "outcome": outcome,
            "moves": moves,
            "tb_depth": tb_depth,
            "score": score,
        })

    metrics = compute_metrics(games)
    n = metrics["n_games"]

    a_wins = sum(1 for g in games if g["outcome"] == 1)
    b_wins = sum(1 for g in games if g["outcome"] == -1)
    draws = sum(1 for g in games if g["outcome"] == 0)
    tb0 = sum(1 for g in games if g["tb_depth"] == 0)
    tb1 = sum(1 for g in games if g["tb_depth"] == 1)
    tb2 = sum(1 for g in games if g["tb_depth"] == 2)
    decided_tb2 = sum(1 for g in games if g["tb_depth"] == 2 and g["outcome"] != 0)
    pct = lambda x: f"{100 * x / n:.1f}%" if n else "0%"

    print(f"Policy: {policy_name}")
    print(f"Games: {n} (4-dice subset)")
    print(f"Outcomes:  A wins: {a_wins} ({pct(a_wins)})  B wins: {b_wins} ({pct(b_wins)})  Draws: {draws} ({pct(draws)})")
    print(f"Decided by:  Raw: {tb0} ({pct(tb0)})  TB1: {tb1} ({pct(tb1)})  TB2: {decided_tb2} ({pct(decided_tb2)})  Draw: {draws} ({pct(draws)})")
    print(f"Tiebreak reached:  TB1: {tb1 + tb2} ({pct(tb1 + tb2)})  TB2: {tb2} ({pct(tb2)})")
    print("-" * 50)
    print(f"Mean regret per move:     {metrics['mean_regret']:.4f}")
    print(f"Catastrophic error rate:  {metrics['catastrophic_error_rate']:.2%}")
    if metrics["draw_preservation_rate"] is not None:
        d, n = metrics["draw_preservation_n"]
        print(f"Draw preservation:        {d}/{n} = {metrics['draw_preservation_rate']:.2%}")
    if metrics["conversion_rate"] is not None:
        c, n = metrics["conversion_n"]
        print(f"Conversion (win→win):     {c}/{n} = {metrics['conversion_rate']:.2%}")
    print(f"Win rate vs oracle:       {metrics['win_rate']:.2%}")


if __name__ == "__main__":
    main()
