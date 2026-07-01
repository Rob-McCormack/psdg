# PSDG — Philosopher’s Stone Dice Game

PSDG is a small deterministic dice game with an exact solver. The board setup is random; after
that there is no randomness and no hidden information, so every position can be solved exactly.

The simplest way to put it: PSDG creates positions that look identical if you track only the
obvious current features (the dice tops), yet require opposite optimal moves. The missing
information was never secret — a player created it with an earlier choice, which was then dropped
from the agent’s representation. Because the game has an exact solver, I can measure exactly when
that blind spot can turn a provable win into a loss.

It is a benchmark for two failure modes, each measured against that exact ground truth (the
solver is a ruler, not an opponent — in a solved game nobody beats it):

1. **Representation failure.** A tabular learner solves the game from the full state, but fails
   when it sees only the dice tops. The dropped information (the committed *facings*) makes some
   positions *alias* — distinct states that look identical yet need different optimal moves —
   which appears as an enumerable regret floor, not a training artifact.
2. **Deployment failure.** An oracle-derived plan becomes exploitable when it is frozen instead
   of re-solved after the opponent leaves the expected line.

The point is not that PSDG is hard. The point is that, in a solved game, we can say exactly when
a failure comes from the learner, from the observation, or from the deployment protocol.

-----

## Representation failure: solving the full state, failing on a lossy one

Train the same tabular agent two ways, changing only what it observes.

- With the full state (tops and the committed facings) it converges to optimal play: zero regret
  against the solver, on every seed and every training budget.
- With tops only (facings dropped) it does not. Trained to 8× past convergence, 0 of 5 seeds
  reach optimal play, and the shortfall does not fall to zero — it moves between the draft and
  exchange stages.

This is not just undertraining. A policy that observes only the tops has lost the information
needed to distinguish some optimal actions; more training on the same observation cannot recover
facings that are absent from the input. (A learner that instead conditioned on the move *history*
could reconstruct them — which is the point: the deciding information has to enter somewhere.)
The limit is enumerable from the rules, before any learning — a regret floor that no memoryless
tops-only policy can beat (deterministic or stochastic; a history-conditioned policy is a
different class, per the parenthetical above):

> Exchange floor 0.021, Draft floor 0.0097 (oracle win/loss units) on the demo opening — a
> property of the input, independent of learner, opponent, or compute.

Trained tabular Q-learning, player A against the solver, demo opening, 5 seeds. Terminal reward
only; the solver never labels moves during training, it grades afterward.

| observation | learns optimal play? | loss vs the solver | more training helps? |
|-------------|----------------------|--------------------|----------------------|
| full (tops + facings) | yes — 0 regret, 100% win, every seed and budget | 0% | already optimal |
| tops-only (facings dropped) | no | 2–6% (budget-dependent) | no — 0/5 seeds solved at 8× |

The loss percentage is not the headline; it is budget-sensitive, and we say so. The stable
number is the enumerated floor. The pattern generalises: across a seeded suite of A-win openings
the full-state learner wins 100% on every opening, while the tops-only learner turns wins into
losses on 15 of 16 openings that carry a floor — and control openings with no exchange floor
still lose, through aliasing at the draft stage.

For an RL or AI-safety reader, PSDG separates two things a single win-rate blurs together:
whether the method can learn the game (it can), and whether the agent can observe what governs
the outcome (it cannot). The first yields to a stronger training signal; the second does not,
and the only remedy is a sufficient state. Measured against ground truth, and bounded below by
enumeration.

-----

## Deployment failure: a frozen plan off the expected line

Take optimal play, let the opponent B deviate, and compare an A that re-solves the realised
position against an A that replays a static principal-line plan. Five-thousand-game suite, six
board dice, random crystals, seeds 42–5041.

| Setup | Exchange protocol | B wins |
|-------|-------------------|--------|
| Optimal vs optimal (baseline) | — | 399 / 5000 (8.0%) |
| B blunders last draft pick; A re-solves at the Exchange | simultaneous or sequential | 284 / 5000 (5.7%) |
| B blunders last draft pick; A plays a static principal line | sequential | 426 / 5000 (8.5%) |
| B blunders last draft pick; A plays a static principal line | simultaneous | 346 / 5000 (6.9%) |

The comparison that matters is static (8.5% / 6.9%) versus re-solving (5.7%) on the same seeds:
that gap is the cost of freezing an ex-ante plan instead of re-optimising once the opponent
deviates. A blundering B beats a frozen A more often (426) than an optimal B does (399) — a fact
within this suite, though borderline as a generalisation (paired McNemar exact two-sided
p ≈ 0.068). The draw-independent statement is the existence result: 320 of 3663 A-win openings
are beatable by at least one worse B move under static deployment. Method and counts:
<https://psdg.pages.dev/faq.html#inversion-significance>.

A noise baseline (10,000 games): optimal A vs uniformly-random-legal B gives A 99.65%, and the
four B wins are openings already valued as B-wins. Noise essentially never beats the solver; the
exploitation is specific to structured deviation against a frozen policy.

-----

## Reproduce

Requirements: Python 3.9+, standard library only (no third-party dependencies).

```bash
git clone https://github.com/Rob-McCormack/psdg.git
cd psdg

# Solve a seeded game end-to-end (4 dice, a few seconds):
python3 solvers/python/solver.py -d 4 -s 42

# Verify a published benchmark against the solver:
python3 benchmark/verify_benchmark.py benchmark/benchmark_4d.json
```

The representation result. The floor is enumerated from the rules and needs no training; the
learning runs train first, then grade against the solver.

```bash
# The enumerated Exchange floor on the demo opening — no training (~10s):
python3 ml/aliasing_exchange.py
# -> tops-only floor 0.0210, full-state floor 0.000

# Full vs tops-only observation, weak and solver opponents — the 2x2 (minutes):
python3 ml/sweep_matrix.py 500000 0,1,2,3,4 400

# "Did we just undertrain?" — tops-only out to 8x the budget (many minutes;
# its header also prints the demo Draft floor, 0.0097):
python3 ml/robustness_budget.py 500000,1000000,2000000,4000000 0,1,2,3,4 400 tops_only

# Cross-opening: control openings with no Exchange floor still carry a Draft floor (minutes):
python3 ml/structural_floors_cross.py
```

The deployment result (the blunder / static-vs-re-solving split):

```bash
python3 benchmark/blunder_test_benchmark.py --print-outcomes            # re-solving
python3 benchmark/blunder_test_benchmark.py --print-outcomes --static   # static, sequential
python3 benchmark/enumerate_blunder_static_vs_optimal.py                # draw-independent count
# expected: ~424.7 expected static B-wins; 320/3663 A-win openings beatable by >=1 worse move
```

-----

## The game

![PSDG board](images/homepage-board-1200.jpg)

Learn basic play in about 3 minutes — [Watch on YouTube](https://youtu.be/N3j1XJp2ZsI). The
tiebreak / Immortal rule takes a few more minutes —
[demo & script](https://psdg.pages.dev/youtube-demo.html).

### Rules in brief

Six dice are rolled onto a shared board; each player also holds a Red Crystal value. After setup
the game is fully deterministic and fully observable.

- Players alternately draft dice into their Crucibles. On taking a die, a player locks its
  *facing* value (the side turned toward the players) — distinct from its current *top*.
- Players then gift one eligible Crucible die to the opponent (the Exchange). You never gift the
  Crystal; eligibility can force the choice.
- Phase 1 scores the current tops. All dice then Tumble — each die’s facing becomes its new top
  — and Phase 2 scores again. A tie is broken by a fixed deterministic procedure (the Immortal
  tiebreaker).
- A die scores if its top is 6 or matches the holder’s Red Crystal.

The mechanism the research turns on: a choice locked early (the facing) becomes payoff-relevant
later (after the Tumble), once ownership and orientation have changed — so the current tops alone
are not a sufficient description of the state. Full mechanics and the tiebreaker:
[`RULES.md`](RULES.md) (v1.13; identical to the site’s Rules page).

-----

## Repository map

```
psdg/
├── RULES.md            # canonical rules, v1.13
├── solvers/python/     # solver.py (the oracle), helpers, small JSON fixtures
├── ml/                 # tabular learner + oracle-graded audit (representation result)
├── benchmark/          # *.json suites, scripts, output/ logs (deployment result)
├── LICENSE             # MIT
└── README.md
```

The numbers on this page are reproducible from this tree. Narrative, definitions, worked
exhibits, and audience-specific framing live on the site (below).

Direct links (for readers, and for automated tools that only parse this page):

- Canonical rules — [RULES.md](https://github.com/Rob-McCormack/psdg/blob/main/RULES.md)
- Representation result (code) — [ml/](https://github.com/Rob-McCormack/psdg/tree/main/ml) · [ml/README.md](https://github.com/Rob-McCormack/psdg/blob/main/ml/README.md)
- Deployment result (code + data) — [benchmark/](https://github.com/Rob-McCormack/psdg/tree/main/benchmark)
- Exact solver — [solver.py](https://github.com/Rob-McCormack/psdg/blob/main/solvers/python/solver.py) · [oracle.py](https://github.com/Rob-McCormack/psdg/blob/main/solvers/python/oracle.py)
- Machine-readable map — [llms.txt](https://psdg.pages.dev/llms.txt)

### Feed this repo to an LLM

The results live in `ml/` and `benchmark/`, not just this page. To hand a model the whole repo at
once, download the always-current archive and upload it to ChatGPT or Claude — no maintenance,
GitHub regenerates it on every download:

- Repo ZIP (latest `main`): <https://github.com/Rob-McCormack/psdg/archive/refs/heads/main.zip>

-----

## Scope

PSDG isolates two structural patterns in one small solved setting; it does not claim to prove
anything directly about large or deployed systems. The extrapolation is only that gaps which are
measurable and lower-bounded here are plausible, and usually far harder to detect, where noise
and incomplete specifications dominate. All numbers are specific to this embedding (the fixed
conventions under which “optimal” is defined). The representation result is tabular, on a seeded
opening family with fixed crystals; function approximation and history-conditioned agents are
named, open extensions, not claims made here.

-----

## Citing

> PSDG (Philosopher’s Stone Dice Game): a small, exactly solved game where (1) a learner that
> solves the full-state game fails under a lossy tops-only state — a representation insufficiency
> enumerable from the rules, not recoverable by more training on the same input — and (2) a
> frozen oracle-derived plan is exploitable once the opponent leaves the expected line.

Rob McCormack, independent researcher. Canonical site: <https://psdg.pages.dev>

## License

MIT — see [`LICENSE`](LICENSE).

-----

For the deep dive — full derivations, FAQs, and worked exhibits — see the technical site:
<https://psdg.pages.dev/>
