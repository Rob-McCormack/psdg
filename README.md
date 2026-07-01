# PSDG — Philosopher's Stone Dice Game

**A small, exactly solved game where two AI failure modes are measurable against ground truth — and one is provably unfixable by more training.**

PSDG is a two-player dice game. The board setup is random; after that there is no randomness and no hidden information, so every position can be solved exactly. The solver is a *ruler*, not an opponent — in a solved game nobody beats it.

The simplest way to put it: PSDG creates positions that look identical if you track only the obvious current features (the dice tops), yet require opposite optimal moves. The missing information was never secret — a player created it with an earlier choice, which was then dropped from the agent's representation. Because the game has an exact solver, I can measure exactly when that blind spot turns a provable win into a loss.

## The game

![PSDG board](images/homepage-board-1200.jpg)

A tabletop dice game for ages 8 and up. Learn basic play in about 3 minutes — [Watch on YouTube](https://youtu.be/N3j1XJp2ZsI). The tiebreak / Immortal rule takes a few more minutes — [demo & script](https://psdg.pages.dev/youtube-demo.html).

### Rules in brief

Six dice are rolled onto a shared board; each player holds a Red Crystal value. Players alternately draft dice — locking a *facing* value distinct from the current *top* — then each gifts one eligible die to the opponent (the Exchange). Phase 1 scores the tops; all dice *Tumble* (facing becomes top); Phase 2 scores again. A die scores if its top is 6 or matches the holder's Crystal. Ties resolve by a fixed deterministic procedure.

The load-bearing mechanism: **a choice locked early becomes payoff-relevant later, after ownership and orientation have changed** — so the current tops are not a sufficient description of the state.

Full rules: [`RULES.md`](RULES.md) (v1.13) · Playable intro: [two-minute game](https://psdg.pages.dev/game-in-two-minutes.html)

## What it measures

PSDG is a benchmark for two failure modes, each measured against the solver's exact ground truth:

1. **Representation failure.** A tabular learner solves the game from the full state, but fails when it observes only the dice tops. The dropped information (committed *facings*) makes distinct states *alias* — identical observations, opposite optimal moves. The resulting regret is **enumerable from the rules before any training**: a floor no memoryless tops-only policy can beat, regardless of learner, opponent, or compute.
2. **Deployment failure.** An oracle-derived plan becomes exploitable when it is frozen instead of re-solved after the opponent leaves the expected line. A *deliberately worse* move can beat a frozen exact-oracle policy.

## Verify the core claim in ~30 seconds

No dependencies. Python 3.9+ standard library only.

```bash
git clone https://github.com/Rob-McCormack/psdg.git
cd psdg
python3 ml/aliasing_exchange.py
# Enumerates 45,056 Exchange states on the demo opening — no training:
#   tops-only policy floor : 0.0210
#   full-state policy floor: 0.000
```

That number is the anchor of the project: a property of the **input**, not of any training run.

---

## Result 1 — representation: the failure lives in the input, not the learner

Train the same tabular Q-learner two ways, changing only what it observes. Terminal reward only; the solver never labels moves during training — it grades afterward. Player A vs the solver, demo opening, 5 seeds:

| observation | learns optimal play? | loss vs solver | more training helps? |
|---|---|---|---|
| **full** (tops + facings) | yes — 0 regret, 100% win, every seed & budget | 0% | already optimal |
| **tops-only** (facings dropped) | no | 2–6% (budget-sensitive) | no — **0/5 seeds solved at 8× budget** |

The loss percentage is budget-sensitive and is *not* the headline; the stable number is the enumerated floor (Exchange **0.021**, Draft **0.0097** on the demo opening, in oracle win/loss units). We tested the "just undertrained?" objection directly, to 8× the converged budget: the raw loss shrinks, but the gap to full-state never closes and never stabilises. Across a seeded suite of A-win openings, the full-state learner wins **100% on every opening**; tops-only converts wins into losses on **15 of 16** openings carrying a floor — and control openings with *no* Exchange floor still lose, through draft-stage aliasing.

Two findings worth knowing before you object:

- **A trained aliased agent pays *more* than the floor** (mean excess regret ~0.13 vs structural floor ~0.05). The floor is a lower bound; optimizing around a lossy representation makes it worse.
- **A stronger learner would not help — and MCTS would cheat.** Any memoryless function of the tops-only observation is bound by the floor: the facings are not in the input. And a planner with a true simulator (AlphaZero-style) would *de-alias itself through the search tree*, quietly smuggling back the removed information — making it a worse instrument for this question, not a better one. A history-conditioned agent *could* reconstruct the facings, which is the point: the deciding information has to enter somewhere. [Full argument →](https://psdg.pages.dev/learning-the-wrong-state.html#undertraining)

## Result 2 — deployment: a frozen exact plan loses to a worse opponent

Let opponent B blunder its last draft pick, and compare an A that **re-solves** the realised position against an A that replays a **static** principal-line plan. 5,000-game suite, six dice, seeds 42–5041:

| Setup | B wins |
|---|---|
| Optimal vs optimal (baseline) | 399 / 5000 (8.0%) |
| B blunders; A **re-solves** at the Exchange | 284 / 5000 (5.7%) |
| B blunders; A plays a **static** line (sequential) | 426 / 5000 (8.5%) |
| B blunders; A plays a **static** line (simultaneous) | 346 / 5000 (6.9%) |

The comparison that matters is static (8.5% / 6.9%) versus re-solving (5.7%) *on the same seeds*: the cost of freezing an ex-ante plan instead of re-optimising once the opponent deviates. The draw-independent existence result: **320 of 3,663 A-win openings are beatable by at least one deliberately worse B move under static deployment.** The net inversion (426 > 399) is exact within the suite but borderline as a generalisation (paired McNemar, p ≈ 0.068) — we report it as a within-suite fact, and the enumerated expectation (424.7) confirms the sampled draw was not lucky. [Method and counts →](https://psdg.pages.dev/faq.html#inversion-significance)

A noise baseline (10,000 games): a uniformly-random-legal B beats the re-solving oracle in only 4 games — all openings already valued as B-wins. Noise essentially never wins; the exploitation is specific to **structured deviation against a frozen policy**.

## Why you can trust these numbers

- **Everything above regenerates from this tree.** Seeded suites, exact solver, verification scripts, published outputs. `verify_benchmark.py` re-solves stored entries against the solver.
- **We found and disclosed a bug.** A line-extraction artifact (alpha-beta pruning could store a non-subgame-perfect principal line) affected 39/5000 seeds; it never moved a root value. It was fixed, all deployment figures were regenerated, and the before/after counts are published (427→426, 287→284, 330→320; rounded headline rates unchanged). [Details →](https://psdg.pages.dev/faq.html#reference-solver-and-benchmark-integrity)
- **Root values are independently verified**: re-solving every game from the opening reproduces the stored value on all 5,000 seeds (3663 A-win / 938 draw / 399 B-win). Run it yourself: `python3 benchmark/diag_solver_consistency.py`.

## Reproduce

```bash
# Solve a seeded game end-to-end (4 dice, ~10s):
python3 solvers/python/solver.py -d 4 -s 42

# Verify a published benchmark against the solver:
python3 benchmark/verify_benchmark.py benchmark/benchmark_4d.json

# --- Representation result ---
python3 ml/aliasing_exchange.py                          # enumerated Exchange floor, no training (~10s)
python3 ml/sweep_matrix.py 500000 0,1,2,3,4 400          # full vs tops-only × weak vs solver opponent (minutes)
python3 ml/robustness_budget.py 500000,1000000,2000000,4000000 0,1,2,3,4 400 tops_only
                                                         # "did we just undertrain?" — out to 8× (long)
python3 ml/structural_floors_cross.py                    # draft floors on control openings (minutes)
python3 ml/step3_cross_opening.py                        # full-vs-tops across the opening suite

# --- Deployment result ---
python3 benchmark/blunder_test_benchmark.py --print-outcomes            # re-solving
python3 benchmark/blunder_test_benchmark.py --print-outcomes --static   # static, sequential
python3 benchmark/enumerate_blunder_static_vs_optimal.py                # draw-independent counts
python3 benchmark/mcnemar_static_vs_optimal.py                          # paired significance test
```

Requirements: Python 3.9+, standard library only. All scripts run from the repository root.

## Repository map

This repo is the **clone-and-run artifact**: Python-only (the JavaScript solver and Node parity harnesses are intentionally out-of-tree), no third-party dependencies, everything needed to regenerate the numbers above. Narrative, definitions, worked exhibits, and audience-specific framing live on the site.

```
psdg/
├── RULES.md            # canonical rules, v1.13 (same text as the site's Rules page)
├── solvers/python/     # solver.py (the oracle), oracle.py, helpers, JSON fixtures
├── ml/                 # tabular learner + oracle-graded audit (representation result)
├── benchmark/          # seeded suites, verification, blunder protocols (deployment result)
├── CITATION.cff        # citation metadata
├── llms.txt            # machine-readable map for LLMs
├── LICENSE             # MIT
└── README.md
```

Direct links (for readers, and for automated tools that only parse this page):

- Canonical rules — [RULES.md](https://github.com/Rob-McCormack/psdg/blob/main/RULES.md)
- Representation result (code) — [ml/](https://github.com/Rob-McCormack/psdg/tree/main/ml) · [ml/README.md](https://github.com/Rob-McCormack/psdg/blob/main/ml/README.md)
- Deployment result (code + data) — [benchmark/](https://github.com/Rob-McCormack/psdg/tree/main/benchmark)
- Exact solver — [solver.py](https://github.com/Rob-McCormack/psdg/blob/main/solvers/python/solver.py) · [oracle.py](https://github.com/Rob-McCormack/psdg/blob/main/solvers/python/oracle.py)
- Machine-readable map — [llms.txt](https://psdg.pages.dev/llms.txt)

### Feed this repo to an LLM

The results live in `ml/` and `benchmark/`, not just this page. To hand a model the whole repo at once, download the always-current archive and upload it to ChatGPT or Claude — GitHub regenerates it on every download:

- Repo ZIP (latest `main`): <https://github.com/Rob-McCormack/psdg/archive/refs/heads/main.zip>

## Going deeper

Start with the at-a-glance pages for your field, then the worked exhibits:

- **ML:** [at a glance](https://psdg.pages.dev/ml-at-a-glance.html) · [learning the wrong state (trained)](https://psdg.pages.dev/learning-the-wrong-state.html) · [full page](https://psdg.pages.dev/ml.html)
- **AI safety:** [at a glance](https://psdg.pages.dev/aisafety-at-a-glance.html) · [full page](https://psdg.pages.dev/aisafety.html)
- **Game theory:** [at a glance](https://psdg.pages.dev/gametheory-at-a-glance.html) · [pinned definitions](https://psdg.pages.dev/gametheory.html#pinned-definitions)
- **Worked exhibits:** [tops-only aliasing](https://psdg.pages.dev/aliasing-exchange-example.html) · [blunder wins](https://psdg.pages.dev/blunder-wins-example.html) · [FAQ](https://psdg.pages.dev/faq.html)

## Scope

PSDG isolates two structural patterns in one small solved setting; it does not claim to prove anything directly about large or deployed systems. The extrapolation is only that gaps which are measurable and lower-bounded here are plausible — and usually far harder to detect — where noise and incomplete specifications dominate. All numbers are specific to this embedding (the fixed conventions under which "optimal" is defined). The representation result is tabular, on a seeded opening family with fixed crystals; function approximation and history-conditioned agents are named, open extensions, not claims made here.

## Citing

> PSDG (Philosopher's Stone Dice Game): a small, exactly solved game where (1) a learner that solves the full-state game fails under a lossy tops-only observation — a representation insufficiency enumerable from the rules, not recoverable by more training on the same input — and (2) a frozen oracle-derived plan is exploitable once the opponent leaves the expected line.

Rob McCormack, independent researcher. Canonical site: <https://psdg.pages.dev>

## License

MIT — see [`LICENSE`](LICENSE).

---

For the deep dive — full derivations, FAQs, and worked exhibits — see the technical site: <https://psdg.pages.dev/>
