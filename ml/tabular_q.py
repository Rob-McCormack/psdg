"""Tabular Q-learning for player A on the fixed opening.

Terminal-only reward in {-1, 0, +1} from A's perspective, gamma = 1 (finite
horizon). Off-policy Q-learning; the fixed opponent's responses are folded
into the (stochastic) transition dynamics. No solver labels are used.
"""

import random


def _greedy_value(Q, key, legal):
    q = Q.get(key)
    if not q:
        return 0.0
    return max((q.get(a, 0.0) for a in legal), default=0.0)


def greedy_action(Q, key, legal, rng=None):
    q = Q.get(key, {})
    best, best_v = [], None
    for a in legal:
        v = q.get(a, 0.0)
        if best_v is None or v > best_v:
            best, best_v = [a], v
        elif v == best_v:
            best.append(a)
    if rng is not None and len(best) > 1:
        return rng.choice(best)
    return best[0]


def train(env, episodes=20000, alpha=0.1, eps=0.2, seed=0):
    """Return Q-table {state_key: {action: value}}."""
    Q = {}
    rng = random.Random(seed)
    for _ in range(episodes):
        s = env.reset()
        traj = []
        while True:
            legal = env.legal_actions(s)
            key = env.state_key(s)
            if rng.random() < eps:
                a = rng.choice(legal)
            else:
                a = greedy_action(Q, key, legal, rng)
            ns, r, done = env.a_step(s, a, rng)
            traj.append((key, a, r, ns, done))
            if done:
                break
            s = ns
        for (key, a, r, ns, done) in traj:
            cell = Q.setdefault(key, {})
            old = cell.get(a, 0.0)
            if done:
                target = r
            else:
                target = r + _greedy_value(Q, env.state_key(ns), env.legal_actions(ns))
            cell[a] = old + alpha * (target - old)
    return Q
