#!/usr/bin/env python3
"""
Play PSDG (4-dice) with Grok over chat. Human = A, Grok = B.

Run: python3 play_with_grok.py [--seed N]

For each turn:
  - A's turn: you enter your move at the prompt.
  - B's turn: script prints a prompt to paste into Grok; you paste Grok's response back.

Exchange is done sequentially (A commits first, B responds) for chat feasibility.
Slightly favors B but still tests Grok's understanding.

At game end, run the solver to compare Grok's play vs optimal.
"""

import argparse
import json
import os
import re
import sys

_here = os.path.dirname(os.path.abspath(__file__))
if _here not in sys.path:
    sys.path.insert(0, _here)

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
)
from oracle import best_actions, delta, value

BENCHMARK_PATH = os.path.join(_here, "..", "benchmark", "benchmark_4d.json")


def format_board(board):
    parts = []
    for t in range(1, 7):
        c = board[t - 1]
        if c > 0:
            parts.append(f"{c}×{t}" if c > 1 else f"1×{t}")
    return ", ".join(parts) if parts else "(empty)"


def format_crucible(crucible, label="Crucible"):
    if not crucible:
        return f"{label}: (empty)"
    lines = [f"{label}:"]
    for i, (top, facing) in enumerate(crucible):
        lines.append(f"  die {i}: top={top}, facing={facing} (bottom={7-top})")
    return "\n".join(lines)


def format_state_for_grok(board, a_crucible, b_crucible, a_crystal, b_crystal, turn):
    """Human-readable state for Grok (Grok plays B)."""
    lines = [
        "=== PSDG STATE (you are Player B) ===",
        "",
        "Board (available dice): " + format_board(board),
        "",
        format_crucible(a_crucible, "Opponent (A) crucible"),
        "",
        format_crucible(b_crucible, "Your (B) crucible"),
        "",
        f"Red Crystals: A has top={a_crystal[0]}, facing={a_crystal[1]}; B has top={b_crystal[0]}, facing={b_crystal[1]}",
        "",
    ]
    return "\n".join(lines)


def parse_draft_response(text):
    """Extract (top, facing) from Grok's response. Accepts (4,6) or 4,6 or 'top 4 facing 6' etc."""
    # Try (top, facing) or (top,facing)
    m = re.search(r"\(?\s*(\d)\s*[,]\s*(\d)\s*\)?", text)
    if m:
        top, facing = int(m.group(1)), int(m.group(2))
        if 1 <= top <= 6 and 1 <= facing <= 6:
            return (top, facing)
    # Try "top X facing Y"
    m = re.search(r"top\s*[=:]?\s*(\d).*facing\s*[=:]?\s*(\d)", text, re.I)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def parse_exchange_response(text):
    """Extract (crucible_index, facing) from Grok's response. Index 0-3."""
    m = re.search(r"\(?\s*(\d)\s*[,]\s*(\d)\s*\)?", text)
    if m:
        idx, facing = int(m.group(1)), int(m.group(2))
        if 0 <= idx <= 3 and 1 <= facing <= 6:
            return (idx, facing)
    m = re.search(r"die\s*(\d).*facing\s*[=:]?\s*(\d)", text, re.I)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    return None


def legal_draft_for_state(board):
    return legal_draft_actions(board)


def main():
    ap = argparse.ArgumentParser(description="Play PSDG 4-dice with Grok over chat")
    ap.add_argument("--seed", type=int, default=42, help="Random seed for board")
    ap.add_argument("--board", type=str, help="Use specific board from benchmark by id (e.g. 0, 1)")
    args = ap.parse_args()

    # Load crystals from benchmark
    with open(BENCHMARK_PATH, encoding="utf-8") as f:
        data = json.load(f)
    a_crystal = tuple(data["crystals"]["a"])
    b_crystal = tuple(data["crystals"]["b"])

    if args.board is not None:
        bid = int(args.board)
        entries = [e for e in data["entries"] if sum(e.get("board", [0]*6)) == 4]
        entries = entries[:50]  # 4-dice subset
        if bid < len(entries):
            e = entries[bid]
            board = tuple(e["board"]) if "board" in e else random_board_n(4, e.get("seed", bid))
        else:
            board = random_board_n(4, args.seed)
    else:
        board = random_board_n(4, args.seed)

    a_crucible = ()
    b_crucible = ()
    turn = PLAYER_A
    initial_state = (board, (), (), a_crystal, b_crystal, PLAYER_A)

    print("PSDG 4-dice: You (A) vs Grok (B)")
    print("=" * 50)
    print("Initial board:", format_board(board))
    print("Crystals: A:", a_crystal, " B:", b_crystal)
    print()

    # Draft phase (4 moves: A, B, A, B)
    for move_num in range(4):
        if turn == PLAYER_A:
            legal = legal_draft_for_state(board)
            print("Legal moves (top, facing):", sorted(set(legal))[:20], "..." if len(legal) > 20 else "")
            inp = input("Your move (top, facing) e.g. 4,6: ").strip()
            try:
                top, facing = map(int, inp.replace("(", "").replace(")", "").split(","))
                action = (top, facing)
            except Exception:
                print("Invalid. Use: top,facing e.g. 4,6")
                continue
            if action not in legal:
                print("Illegal move. Legal:", legal[:15])
                continue
            board, a_crucible = apply_draft_action(board, a_crucible, action)
            turn = PLAYER_B
        else:
            # Grok's turn (B)
            legal = legal_draft_for_state(board)
            legal_str = ", ".join(f"({t},{f})" for t, f in sorted(legal)[:24])
            if len(legal) > 24:
                legal_str += " ..."
            prompt = f"""
{format_state_for_grok(board, a_crucible, b_crucible, a_crystal, b_crystal, turn)}

It is your turn (B). Draft one die from the board. Choose (top, facing).
Legal moves: {legal_str}
(Standard d6: facing cannot be top or 7-top.)

Reply with ONLY your move: (top, facing)
Example: (4, 6)
"""
            print("\n" + "=" * 50)
            print("COPY THE FOLLOWING INTO GROK:")
            print("=" * 50)
            print(prompt)
            print("=" * 50)
            inp = input("Paste Grok's response: ").strip()
            action = parse_draft_response(inp)
            if action is None:
                print("Could not parse. Assuming random legal move.")
                legal = legal_draft_for_state(board)
                import random
                action = random.choice(legal)
            else:
                legal = legal_draft_for_state(board)
                if action not in legal:
                    print("Grok's move illegal. Picking first legal move.")
                    action = legal[0]
            board, b_crucible = apply_draft_action(board, b_crucible, action)
            b_state = (board, a_crucible, b_crucible, a_crystal, b_crystal, turn)
            opt = best_actions(b_state)
            d = delta(b_state, action)
            print(f"Grok played {action}. Optimal: {opt[0] if opt else '?'}. Delta={d} (0=optimal, >0=Grok blundered)")
            turn = PLAYER_A
        print(f"After move {move_num+1}: A_crucible={a_crucible}, B_crucible={b_crucible}")

    # Exchange phase (sequential: A first, B second)
    state = (board, a_crucible, b_crucible, a_crystal, b_crystal, turn)
    a_legal_idx = forced_gift_indices(a_crucible, a_crystal)
    b_legal_idx = forced_gift_indices(b_crucible, b_crystal)

    print("\n=== EXCHANGE (The Poisoned Gift) ===")
    print("A must gift from:", a_legal_idx, "B must gift from:", b_legal_idx)
    print(format_crucible(a_crucible, "A crucible"))
    print(format_crucible(b_crucible, "B crucible"))

    # A commits first
    print("\nYour exchange: give die INDEX (0-3) and FACING for receiver.")
    inp = input("Your exchange (index, facing) e.g. 2,6: ").strip()
    try:
        ai, af = map(int, inp.replace("(", "").replace(")", "").split(","))
        a_act = (ai, af)
    except Exception:
        ai, af = a_legal_idx[0], side_faces(a_crucible[a_legal_idx[0]][0])[0]
        a_act = (ai, af)
        print("Defaulting to", a_act)
    if ai not in a_legal_idx:
        ai = a_legal_idx[0]
        a_act = (ai, side_faces(a_crucible[ai][0])[0])

    # Grok's exchange (sees A's choice)
    prompt = f"""
{format_state_for_grok(board, a_crucible, b_crucible, a_crystal, b_crystal, turn)}

EXCHANGE PHASE. A has committed: giving die {a_act[0]} with facing {a_act[1]} for you.

You (B) must choose which die to give and what facing to set for A.
Legal gift indices (lowest-pair rule): {list(b_legal_idx)}
Your crucible: {list(b_crucible)}

Reply with ONLY: (crucible_index, facing)
Example: (1, 5)
"""
    print("\n" + "=" * 50)
    print("COPY INTO GROK:")
    print("=" * 50)
    print(prompt)
    print("=" * 50)
    inp = input("Paste Grok's response: ").strip()
    b_act = parse_exchange_response(inp)
    if b_act is None or b_act[0] not in b_legal_idx:
        b_act = (b_legal_idx[0], side_faces(b_crucible[b_legal_idx[0]][0])[0])
        print("Parse failed, using", b_act)

    a_new, b_new = apply_exchange(a_crucible, b_crucible, a_act, b_act)
    result = evaluate(a_new, b_new, a_crystal, b_crystal)
    breakdown = evaluate_breakdown(a_new, b_new, a_crystal, b_crystal)

    print("\n" + "=" * 50)
    print("RESULT")
    print("=" * 50)
    print("Phase 1:", breakdown["phase1"], " Phase 2:", breakdown["phase2"])
    print("Total: A=%d B=%d" % breakdown["total"])
    if result == 1:
        print("A wins!")
    elif result == -1:
        print("B (Grok) wins!")
    else:
        print("Draw!")
    print()

    # Compare to optimal
    opt_val = value(initial_state)
    print("At start of game, oracle value was:", opt_val, "(+1 A wins, -1 B wins, 0 draw)")
    print("Actual result:", result)
    if result != opt_val:
        print("(Outcome differed from game-theoretic value—non-optimal play by one or both.)")


if __name__ == "__main__":
    main()
