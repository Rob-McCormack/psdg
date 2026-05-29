# PSDG — Philosopher’s Stone Dice Game

A tiny, exactly solved two-player dice game, used as a measurement instrument for one
structural failure: a policy can be optimal on what it sees and still lose, because the
rules fix consequences *before* those consequences become legible.

After a random setup the game is deterministic and perfect-information — small enough to
solve exactly. That exact solver (the “oracle”) is the ruler. The research question is not
“can anyone beat the oracle” (in a solved game, no) but “how far do real policies fall
short, and what makes a frozen optimal plan exploitable when play leaves the expected line?”

Full narrative, definitions, and audience-specific framing live on the site:
**<https://psdg.pages.dev>**. This repository is the clone-and-run artifact: Python reference
solver, seeded benchmark data, and scripts to reproduce the numbers.

-----

## The result in one table

Five-thousand-game suite, six board dice, random crystals, seeds 42–5041.

| Setup                                                          | Exchange protocol          | B wins            |
|----------------------------------------------------------------|----------------------------|-------------------|
| Optimal vs optimal (baseline)                                  | —                          | 399 / 5000 (8.0%) |
| B blunders last draft pick; A **re-solves** at the Exchange    | simultaneous or sequential | 287 / 5000 (5.7%) |
| B blunders last draft pick; A plays a **static** principal line | sequential                 | 427 / 5000 (8.5%) |
| B blunders last draft pick; A plays a **static** principal line | simultaneous               | 347 / 5000 (6.9%) |

Optimal-vs-optimal full split: A 3663 (73.3%), draws 938 (18.8%), B 399 (8.0%).

**How to read it.** The load-bearing comparison is static (8.5% / 6.9%) versus re-solving
(5.7%) on the *same* seeds: that gap is the cost of freezing an ex-ante plan instead of
re-optimising once the opponent deviates. The re-solving row sits *below* the
optimal-vs-optimal baseline — a forced last-pick blunder mostly *costs* B wins
(287 of those B wins are a near-subset of the 399), so that row is not “minimax beaten.”

The static-sequential row is the one where a blundering B can win *more* often (427) than an
optimal B (399) against a frozen A. That **net** excess (427 > 399) is an **exact
within-suite fact** but **borderline as a generalization** — a *paired* analysis on the
same seeds gives McNemar exact two-sided p ≈ 0.058. The robust, draw-independent fact is the
**existence** result: **330 of 3663** A-win openings are beatable by **at least one** worse B
move under static deployment (a single sampled blunder draw catches 116 of them; enumerating
all suboptimal last twists confirms 427 is the expectation, ≈ 427.7, not a lucky draw). The
A-side traps are narrow (most sprung by only a minority of B’s possible wrong moves) and are
nearly offset by B’s mostly-harmless blunders, which is why the net stays small. Method and
counts: <https://psdg.pages.dev/faq.html#inversion-significance>.

A separate noise baseline (10,000 games, seeds 42–10041, six dice): optimal A vs
uniformly-random-legal B gives A 9965 (99.65%), draws 31 (0.31%), B 4 (0.04%) — and all
four B wins come from openings already valued as B-wins. Pure noise essentially never
beats the oracle; the exploitation above is specific to *structured* deviation against a
*frozen* policy.

-----

## The game in 60 seconds

Two players, six gray board dice, one Red Crystal die each. Only the setup is random;
after that, every move follows the rules with no further rolls and nothing hidden.

1. **Draft** — players alternate (A first) taking board dice. On each pick you *Twist* the
   die to choose its facing value. That facing is a Phase-2 commitment: it becomes the die’s
   top after the Tumble. You build a sorted Crucible of three dice.
1. **Poisoned Gift (Exchange)** — each player gives the opponent one Crucible die and sets
   the facing it arrives on. Eligibility can force the choice: if any top value repeats
   among your three Crucible dice plus your Crystal, you must gift from the lowest repeated
   value. You never gift the Crystal. In v1.13 the reveal is simultaneous.
1. **Score (Phase 1)** — a die scores 1 if its top is 6 or equals your Red Crystal’s top,
   else 0. Max 3.
1. **Tumble** — rotate each Crucible die 90° forward; its facing becomes the new top.
1. **Score (Phase 2)** — score again under the new tops. Higher two-phase total wins.
1. **Immortal tiebreaker** — if tied, a scripted sequence of Crystal tumbles/flips rescores
   the frozen Crucibles until a verdict or a draw.

The point: two boards with identical *tops* can require opposite optimal play, because the
*facings* committed during the draft encode Phase 2 and are not visible in a “tops now”
summary. Any policy whose state is the board snapshot aliases positions the rules keep
distinct.

Canonical rules: [`RULES.md`](RULES.md) (v1.13; identical to the site’s Rules page).

-----

## Reproduce

Requirements: **Python 3.9+, standard library only** (no third-party dependencies).

```bash
git clone https://github.com/Rob-McCormack/psdg.git
cd psdg

# Solve a single seeded game from the opening roll
python3 solvers/python/solver.py -r -s 42

# Verify a published benchmark JSON against the solver
python3 benchmark/verify_benchmark.py benchmark/benchmark_4d.json
```

Reproduce the headline blunder split:

```bash
# B-win counts and oracle-root-value -> realized-outcome breakdown
python3 benchmark/blunder_test_benchmark.py --print-outcomes                          # re-solving
python3 benchmark/blunder_test_benchmark.py --print-outcomes --static                 # static, sequential
python3 benchmark/blunder_test_benchmark.py --print-outcomes --static --static-simultaneous-exchange  # static, simultaneous
```

Cross-check the 5.7% re-solving row against stored root values:

```bash
python3 benchmark/verify_blunder_root_value_crossjoin.py
# expected: 284/287 B wins pair with value == -1
```

Paired static-vs-optimal analysis (the 427 > 399 inversion):

```bash
# Sampled single blunder draw: 2x2, discordant cells, McNemar exact p
python3 benchmark/mcnemar_static_vs_optimal.py
# expected: c=116 (to B-win, all A-win roots), b=88 (away), net +28, p ~ 0.058

# Draw-independent: enumerate ALL suboptimal last twists per seed
python3 benchmark/enumerate_blunder_static_vs_optimal.py
# expected: expected static B-wins ~427.7; 330/3663 A-win openings beatable by >=1 worse move
```

-----

## What is in this repository

```
psdg/
├── RULES.md            # canonical rules, v1.13
├── solvers/python/     # solver.py, oracle.py, helpers, small blunder JSON fixtures
├── benchmark/          # *.json suites, Python scripts, output/ logs
├── LICENSE             # MIT
└── README.md
```

Reference Python solver, the seeded benchmark JSON (e.g. `benchmark_4d.json`,
`benchmark_5000_6d.json`), verification and blunder scripts (including
`mcnemar_static_vs_optimal.py` and `enumerate_blunder_static_vs_optimal.py`), and the output
logs they produce. The numbers above are reproducible from this tree.

## What is not in this repository

Some drivers used to generate auxiliary results live only in a private development tree
under `private/psdg/` and are **not** shipped here:

- the random-legal baseline driver (`optimal_vs_random_legal.js`, Node)
- the worked-example harness (`blunder_test_random_crystals.js`, Node)
- the hand-authored heuristic pilot (`pilot_heuristic_facing6_vs_oracle.py`)
- the JavaScript cross-check solver (`solver.js`)

Where the site cites those, the *output logs* may be included here but the generating
script is not. Porting the random-legal driver to Python is the most useful gap to close,
since that baseline anchors the “noise doesn’t win” contrast.

-----

## Terms

- **Oracle / solver** — same artifact, two names: it returns exact value, legal moves,
  the principal line, and per-move regret under the published embedding.
- **Principal line** — the optimal continuation the solver returns from a given roll.
- **Blunder** — a move that is suboptimal under that embedding (in the suite, B’s last
  draft pick is off the principal line).
- **Static vs re-solving** — at the Exchange, A either replays the principal-line gift
  (“static”) or recomputes the gift on the realised position (“re-solving”). This is a
  deployment choice, not a change to the game.
- **Embedding / protocol (P)** — the fixed conventions under which “optimal” is defined:
  the solution concept, the Exchange timing, and the static-vs-re-solving rule. Realised
  “optimal” outcomes are joint with P.

-----

## Known issues

Three seeds (4167, 4359, 4402) record a B win in the re-solving trial despite a stored root
value of +1: on those openings the principal line from `solve_from_roll` disagrees with
`solve_from_position` at B’s last draft node. This is a reference-solver consistency item
(principal-line witness selection) under review — about 0.06% of the suite — not benchmark
noise and not a refutation of draft minimax. See
`benchmark/output/blunder_resolving_vs_root_value_5000_*.txt`.

-----

## Scope

PSDG isolates a structural pattern in one small exact setting. It does not claim to prove
anything directly about large or deployed systems; the extrapolation is that gaps which are
exactly measurable here are plausible, and usually harder to detect, where noise and
incomplete specifications dominate. Numbers are specific to this embedding.

-----

## Citing

> PSDG (Philosopher’s Stone Dice Game): a small, exactly solved game where a frozen
> oracle-derived plan can lose to a blundering opponent. Misspecification is “optimally
> wrong”; deployment is fragile when the wrong commitments are frozen.

Rob McCormack, independent researcher. Canonical site: <https://psdg.pages.dev>

*(Consider adding a `CITATION.cff` so GitHub renders a “Cite this repository” button.)*

## License

MIT — see [`LICENSE`](LICENSE).
