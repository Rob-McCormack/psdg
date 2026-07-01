"""Solver-as-examiner audit of a learned A policy.

Metrics (oracle-grounded, computed AFTER training):
  * root first-move optimality
  * optimal-move rate (overall, and split draft vs exchange)
  * mean per-decision regret (draft: oracle delta; exchange: security regret)
  * win / draw / loss rate of greedy A vs the fixed opponent
  * where regret lives (draft vs exchange)

Draft regret uses the oracle's delta (assumes optimal continuation). Exchange
regret is the security-value gap: v* minus the value A's gift guarantees
against B's best reply -- the right notion at a simultaneous node.
"""

import os
import random
import sys

_SOLVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "solvers", "python")
_SOLVER_DIR = os.path.normpath(_SOLVER_DIR)
if _SOLVER_DIR not in sys.path:
    sys.path.insert(0, _SOLVER_DIR)

import oracle  # noqa: E402
from solver import (  # noqa: E402
    PLAYER_A,
    apply_exchange,
    evaluate,
    forced_gift_indices,
    side_faces,
    solve_exchange,
)

from env import DRAFT, EXCHANGE  # noqa: E402
from tabular_q import greedy_action  # noqa: E402


def _exchange_security_regret(s, a_gift, env):
    """v* - min over B's legal replies of value(apply_exchange(...))."""
    v_star, _ = solve_exchange(s.a, s.b, env.a_crystal, env.b_crystal)
    b_legal = [
        (bi, bf)
        for bi in forced_gift_indices(s.b, env.b_crystal)
        for bf in side_faces(s.b[bi][0])
    ]
    guaranteed = min(
        evaluate(*apply_exchange(s.a, s.b, a_gift, b_resp), env.a_crystal, env.b_crystal)
        for b_resp in b_legal
    )
    return v_star - guaranteed


def audit(env, Q, episodes=400, seed=12345):
    rng = random.Random(seed)
    regret_cache = {}

    def regret_of(s, a, key):
        # Cache by the TRUE full state (not the observation key): in tops-only
        # mode several true states share one observation key but have different
        # true regret, so caching by the obs key would be wrong.
        ck = ((s.board, s.a, s.b, s.phase), a)
        if ck in regret_cache:
            return regret_cache[ck]
        if s.phase == DRAFT:
            full = (s.board, s.a, s.b, env.a_crystal, env.b_crystal, PLAYER_A)
            reg = oracle.delta(full, a)
        else:
            reg = _exchange_security_regret(s, a, env)
        regret_cache[ck] = reg
        return reg

    # Root first-move optimality.
    root = env.reset()
    root_full = (root.board, root.a, root.b, env.a_crystal, env.b_crystal, PLAYER_A)
    root_legal = env.legal_actions(root)
    root_action = greedy_action(Q, env.state_key(root), root_legal)
    root_best = set(oracle.best_actions(root_full))
    root_optimal = root_action in root_best

    n_dec = n_opt = 0
    n_draft = n_draft_opt = 0
    n_exch = n_exch_opt = 0
    sum_reg = sum_reg_draft = sum_reg_exch = 0.0
    outcomes = {1: 0, 0: 0, -1: 0}

    for _ in range(episodes):
        s = env.reset()
        while True:
            legal = env.legal_actions(s)
            key = env.state_key(s)
            a = greedy_action(Q, key, legal)
            reg = regret_of(s, a, key)
            n_dec += 1
            sum_reg += reg
            opt = reg == 0
            n_opt += opt
            if s.phase == DRAFT:
                n_draft += 1
                n_draft_opt += opt
                sum_reg_draft += reg
            else:
                n_exch += 1
                n_exch_opt += opt
                sum_reg_exch += reg
            ns, r, done = env.a_step(s, a, rng)
            if done:
                outcomes[int(r)] += 1
                break
            s = ns

    return {
        "root_action": root_action,
        "root_optimal": root_optimal,
        "n_root_best": len(root_best),
        "decisions": n_dec,
        "optimal_move_rate": n_opt / n_dec,
        "mean_regret": sum_reg / n_dec,
        "draft_optimal_rate": n_draft_opt / n_draft if n_draft else None,
        "draft_mean_regret": sum_reg_draft / n_draft if n_draft else None,
        "exchange_optimal_rate": n_exch_opt / n_exch if n_exch else None,
        "exchange_mean_regret": sum_reg_exch / n_exch if n_exch else None,
        "episodes": episodes,
        "win_rate": outcomes[1] / episodes,
        "draw_rate": outcomes[0] / episodes,
        "loss_rate": outcomes[-1] / episodes,
        "q_states": len(Q),
    }
