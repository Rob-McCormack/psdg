# Structural draft-floor distribution — 6-dice openings

Learner-independent distribution of the tops-only **draft** aliasing floor across
random 6-dice openings. Generalizes the curated `structural_floors_cross.py` set
to a random sample, to show prevalence + magnitude rather than hand-picked cases.

- **Command:** `python3 floor_distribution.py --n 200 --seed 2026`
- **Seed:** 2026 (per-board seed = `"2026:<index>"`; recorded per JSONL line)
- **N:** 200 random boards × 2 crystal conditions (paired on the same board)
- **Data:** `output/floor_distribution_6d.jsonl` (one line per board×condition)
- **Compute:** ~504 s (8.4 min) for 380 jobs, multiprocessing pool
- **Floor units:** oracle regret (win/loss units), same convention as the demo draft floor 0.009686

## Calibration gate (demo opening, `draft_floor`) — PASS

| quantity | value | expected |
|---|---|---|
| states   | 13009 | 13009 |
| groups   | 76 | 76 |
| aliased  | 75 | 75 |
| conflict | 13 | 13 |
| floor    | 0.009686 | 0.009686 (±1e-6) |

## Condition: FIXED — A=(2,6), B=(1,2)

Root value dist: A-win 139, draw 29, B-win 32 (of 200).

| metric | value |
|---|---|
| floor > 0 | 197 / 200 (98%) |
| exact zero | 3 / 200 |
| mean | 0.0260 |
| median | 0.0235 |
| max | 0.0798 |
| p50 / p75 / p90 / p99 | 0.0235 / 0.0315 / 0.0454 / 0.0798 |
| among A-win openings, floor > 0 | 138 / 139 (99%) |

Bucketed histogram: `0`:3 · `(0–0.01]`:13 · `(0.01–0.05]`:171 · `(0.05–0.1]`:13 · `>0.1`:0

## Condition: RANDOM — crystals drawn per board (top ∈ 1..5)

Crystal sampling mirrors `run_cross_opening.random_opening` exactly. Root value
dist: A-win 148, draw 23, B-win 29 (of 200).

| metric | value |
|---|---|
| floor > 0 | 193 / 200 (96%) |
| exact zero | 7 / 200 |
| mean | 0.0277 |
| median | 0.0243 |
| max | 0.1085 |
| p50 / p75 / p90 / p99 | 0.0243 / 0.0362 / 0.0542 / 0.1035 |
| among A-win openings, floor > 0 | 143 / 148 (97%) |

Bucketed histogram: `0`:7 · `(0–0.01]`:27 · `(0.01–0.05]`:143 · `(0.05–0.1]`:21 · `>0.1`:2

## Notes

- Zero-floor boards are a first-class outcome, reported, not discarded (3 fixed, 7 random).
- The two conditions are reported separately and never pooled.
- Draft floors are **not** compared here to Exchange floors or to trained-regret numbers.
- Reproduce (deterministic): `python3 floor_distribution.py --n 200 --seed 2026`
- Re-print tables from the checkpoint only: `python3 floor_distribution.py --aggregate-only`
