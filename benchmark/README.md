# PSDG benchmark (Python)

This directory contains **Python-only** tooling: benchmark JSON files, generators, verification, blunder sweeps, and agent evaluation.

**Narrative and full methodology:** [https://psdg.pages.dev](https://psdg.pages.dev) (technical summary, FAQ, related work).

## Layout

| Script | Purpose |
|--------|---------|
| `generate_benchmark.py` | Build a seeded benchmark JSON from the solver |
| `verify_benchmark.py` | Re-solve entries and check stored values |
| `run_benchmark_500_6d.py` | Regenerate the canonical 5000×6d suite (writes `benchmark_5000_6d.json`) |
| `blunder_test_benchmark.py` | Blunder robustness protocols on the suite |
| `verify_blunder_root_value_crossjoin.py` | Cross-check blunder outcomes vs stored root values |
| `verify_sequential_parity.py` | Exchange sequential vs simultaneous consistency on benchmark samples |
| `run_hard_benchmark.py` | Harder-game stats JSON (random boards + crystals) |
| `evaluate_agent.py` | Run random / greedy / oracle policies against a benchmark |
| `time_solvers.py` | Simple timing helper |
| `curated_boards.py` | Supporting data for generation |

Precomputed artifacts live in `*.json`, verification logs under `output/`.

**Not shipped in this repository:** JavaScript solver and `node`-based parity harnesses; those remain optional in the full development tree.

## Quick checks

From the **repository root** (`psdg/`):

```bash
# Smoke: re-verify a small benchmark
python3 benchmark/verify_benchmark.py benchmark/benchmark_4d.json

# Run reference solver demo
python3 solvers/python/solver.py -r -s 42
```
