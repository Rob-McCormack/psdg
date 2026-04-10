# PSDG — Philosopher’s Stone Dice Game

**Canonical research site:** [https://psdg.pages.dev](https://psdg.pages.dev)

That site is the best place for **how PSDG is framed as a research project**: motivation, definitions, empirical snapshot (blunder vs static rows, protocols), FAQ, technical report summary, related work, and worked examples. It is maintained as a focused documentation site, not as a mirror of everything that might live in a full development tree.

---

## What this GitHub repository is for

This repo holds **public, reproducible artifacts**: the reference **solver**, **benchmark data** (or generators and specifications), and **short instructions** to run them—so others can clone, verify, and extend experiments **without** wading through a private monorepo or a full doc tree on GitHub.

It is **intentionally different** from the site’s long-form pages (for example [Technical report (summary)](https://psdg.pages.dev/technical-report-summary.html)). README + code + data here; narrative, tables in context, and caveats on **psdg.pages.dev**.

**Start with the site** if you want a complete understanding of PSDG; **use this repo** if you want to execute and inspect the oracle-facing pieces.

---

## Repository contents

As this repository is populated, expect roughly:

| Area | Role |
|------|------|
| Solver | Reference implementation(s) (e.g. Python minimax + exchange logic), with runnable entry points |
| Benchmarks | Published suite(s), seeds, and/or scripts to regenerate or verify JSON |
| Supporting docs | Minimal in-repo notes (rules snippet, protocol definitions) where they help reproducibility—**not** a second copy of the whole research site |

Layout and exact paths will be documented here as files land.

---

## License

See [LICENSE](LICENSE) (MIT).
