# PSDG — Philosopher’s Stone Dice Game

**Canonical research site:** [https://psdg.pages.dev](https://psdg.pages.dev)

That site is the best place for **how PSDG is framed as a research project**: motivation, definitions, empirical snapshot (blunder vs static rows, protocols), FAQ, technical report summary, related work, and worked examples.

---

## What this GitHub repository is for

This repo holds **public, reproducible artifacts** in **Python only** (no JavaScript solver in-tree): the reference **solver**, **benchmark JSON**, and scripts to **generate, verify, and experiment**—without a private monorepo.

It is **intentionally different** from the site’s long-form pages—for example [Technical report (summary)](https://psdg.pages.dev/technical-report-summary.html). Narrative and caveats live on **psdg.pages.dev**; this repo is for **clone-and-run** use.

---

## Layout

```
psdg/
├── README.md
├── LICENSE
├── solvers/python/     # solver.py, oracle.py, helpers, small blunder JSON fixtures
└── benchmark/          # *.json suites, Python scripts, output/ logs
```

See [benchmark/README.md](benchmark/README.md) for script roles and quick commands.

---

## Quick start

From the repository root:

```bash
python3 solvers/python/solver.py -r -s 42
python3 benchmark/verify_benchmark.py benchmark/benchmark_4d.json
```

---

## License

See [LICENSE](LICENSE) (MIT).
