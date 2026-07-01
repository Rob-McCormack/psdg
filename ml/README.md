# ml — learning against the exact solver

Solver-as-examiner discipline: the agent trains with terminal reward only (no solver labels
during training), and the solver grades afterward — regret, optimality, and win/loss, split by
decision stage (draft vs exchange). The question is not whether a learner can beat the solver
(in a solved game it cannot) but how, and how badly, a learner falls short of provably optimal
play under a given observation.

Scripts referenced by the top-level README:

- `aliasing_exchange.py` — the enumerated Exchange regret floor on the demo opening, no training
  (~10s): tops-only floor 0.0210, full-state floor 0.000. The lower bound no memoryless
  tops-only policy can beat.
- `sweep_matrix.py` — full vs tops-only observation × weak (random-legal) vs solver opponent
  (the 2×2; minutes).
- `robustness_budget.py` — tops-only trained to multiples of the converged budget (the
  "did we just undertrain?" check; many minutes). Its header also prints the demo Draft floor
  (0.0097).
- `structural_floors_cross.py` — the floor generalised: control openings with no Exchange floor
  still carry a Draft floor. Samples openings, so minutes.
- `step3_cross_opening.py` — the trained full-vs-tops contrast across a seeded suite of openings.

Support modules: `env.py` (game + observation encoders), `opponents.py` (random-legal and
solver-optimal B), `tabular_q.py` (the learner), `audit.py` (oracle-graded audit),
`run_cross_opening.py` (opening sampler + Exchange floor), `position.py` (the demo opening).

Requirements: Python 3.9+, standard library only. Run from the repository root, e.g.

```bash
python3 ml/aliasing_exchange.py                       # ~10s: the enumerated floor
python3 ml/sweep_matrix.py 500000 0,1,2,3,4 400       # minutes: the 2x2
```
