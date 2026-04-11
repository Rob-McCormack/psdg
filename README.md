# PSDG — Philosopher’s Stone Dice Game

**In one line:** A tiny exact benchmark where freezing an oracle’s principal-line continuation can lose to blunders.

**Canonical research site:** [https://psdg.pages.dev](https://psdg.pages.dev) — motivation, definitions, [empirical snapshot](https://psdg.pages.dev/#empirical-snapshot) (blunder vs static rows), FAQ, technical report summary, related work, and worked examples. **Game theory, ML evaluation, and alignment** are different routes into the **same benchmark** under the **same oracle** on that site; this repo is the **clone-and-run** artifact.

---

## What this GitHub repository is for

This repo holds **public, reproducible artifacts** in **Python only** (no JavaScript solver in-tree): the reference **solver**, **benchmark JSON**, and scripts to **generate, verify, and experiment**—without a private monorepo.

It is **intentionally different** from the site’s long-form pages—for example [Technical report (summary)](https://psdg.pages.dev/technical-report-summary.html). Narrative and caveats live on **psdg.pages.dev**; numbers and protocols you reproduce start here.

---

## Layout

```
psdg/
├── README.md
├── LICENSE
├── RULES.md            # canonical rules v1.13 (Markdown); site mirrors with HTML nav
├── solvers/python/     # solver.py, oracle.py, helpers, small blunder JSON fixtures
└── benchmark/          # *.json suites, Python scripts, output/ logs
```

- **Rules:** [RULES.md](RULES.md) — same v1.13 text as [psdg.pages.dev/rules](https://psdg.pages.dev/rules.html).
- **Benchmarks:** [benchmark/README.md](benchmark/README.md) for script roles and quick commands.

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
