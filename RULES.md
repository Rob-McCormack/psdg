# PSDG — Rules (v1.13)

**Read on the web:** [psdg.pages.dev/rules](https://psdg.pages.dev/rules.html) (same substance, site navigation, and stable anchors for citations).

**Solver and benchmarks:** [github.com/Rob-McCormack/psdg](https://github.com/Rob-McCormack/psdg).

---

## Rules in brief

**Playing for the first time?** Use the linear **[Simple rules (players)](https://psdg.pages.dev/player-simple-rules.html)** page; this file also carries **research** context.

**Philosopher's Stone Dice Game (PSDG)** is a **two-player** tabletop game played with **six board dice**, **Red Crystal** dice, two **Crucibles** (your areas on the mat), and a small **playmat** or paper layout. **Only setup is random**—positions and crystals—then **every legal move follows the rules** with no extra rolls and no hidden information. **Most gold** after the two scoring phases (and **Immortal** if you are tied) **wins**. Table time is roughly **10–15 minutes** once you know the beats.

**Unlike chess**, a snapshot of **tops alone** is not enough to specify the true position: the **Facing Players Value** you **Twist** when drafting is a **Phase 2** commitment (it becomes the new top after the **Tumble**). Two configurations with the **same** visible tops can need **opposite** optimal play. After setup the game is **perfect information**—nothing is hidden by the rules—so the research stressor is **state compression / aliasing** (what a policy puts in its inputs), not partial observability in the poker sense. For a **full scripted game** (draft through tiebreaker), see **[YouTube demo & tutorial](https://psdg.pages.dev/youtube-demo.html)**; for a shorter **components intro**, **[Game introduction on YouTube](https://youtu.be/1eAmxgINXrE)**.

- **Players & gear:** 2 players; **6 gray dice** (shared board pool), **1 Red Crystal** each (Stone); perfect information **after** random setup.
- **Draft (alternating, A first):** take a board die, **Twist** to set **Facing Players Value**—a **two-phase commitment** (Phase 1 scores the current **top**; Phase 2 scores that **facing** after the **Tumble**). You lock both **before** the Exchange and final scoring fully unpack—the same **ready, fire, aim** rhythm as on the [home page](https://psdg.pages.dev/#ready-fire-aim); build a sorted **Crucible** of 3 dice.
- **Poisoned Gift (Exchange):** each gifts one Crucible die under **eligibility** (look at your **3 Crucible dice + your Red Crystal** — four tops total; if any value repeats among those four, you must gift from the **lowest** of the repeated values; if all four tops are different, you may gift any Crucible die; you never gift the Crystal). Choose the facing your opponent receives; **reveal simultaneously** in v1.13 play; re-sort Crucibles. *Examples:* among those four tops, **2, 2, 4, 5** → you must gift a **2**; **2, 3, 5, 5** → you must gift a **5**; **1, 3, 4, 6** (all different) → any Crucible die. **Research:** core ML / safety lessons—and the minimal **[parable](https://psdg.pages.dev/parable.html)** / **[Q-learning demo](https://psdg.pages.dev/qlearning-parable.html)** (no Exchange at all)—do **not** depend on **simultaneous** reveal; see [NOTE — simultaneous Exchange](#note--research-claims-do-not-depend-on-simultaneous-exchange) below.
- **Scoring (“what is gold?”):** each Crucible die scores **1** if its top is **6** or **equals your Red Crystal top**; else **0**. Red Crystal never scores in main phases. **Phase 1** score tops; **Tumble** each Crucible 90° forward; **Phase 2** score again; **higher total wins**.
- **Immortal tiebreaker:** if still tied after Phase 2, Crucible dice stay **frozen** while a scripted sequence of **Red Crystal** tumbles and flips rescores them until verdict or **draw**. *Benchmark:* on the published **5,000-game** principal-line suite, about **72%** of games are decided after Phase 2 with **no** Immortal ([tiebreak depth table](https://psdg.pages.dev/technical-report-summary.html#tiebreak-depth-5k)).
- **Research hook:** **Canonical v1.13** continues **below**—edge cases, seating, Gift procedure, and alternative Exchange variants in research benchmarks. Pinned rules make positions **exactly** evaluable; proxy and deployment failure modes are **oracle-measurable**, not theoretical only. **Reference solver and benchmark scripts** live in **[github.com/Rob-McCormack/psdg](https://github.com/Rob-McCormack/psdg)** (see also [psdg.pages.dev — Solver & GitHub](https://psdg.pages.dev/#solver-github)).

The sections below are the **full v1.13** rulebook (this file is the **canonical Markdown** in the public repository).

---

# Philosopher's Stone Dice Game

**PSDG · v1.13 · 2 Players · Ages 8+ · 10–15 Minutes**  
**Date:** February 23, 2026

*Two rival alchemists. One legendary stone. The power to turn lead into gold.*

-----

## The Legend

The Philosopher's Stone is a legendary red crystal sought for millennia by alchemists because of its ability to turn lead into gold and to grant immortality.

## Overview

Philosopher's Stone Dice Game is a game of transformed treasure, treachery, and poisoned gifts. Once the board is set, your luck never runs out—because you never had any to begin with.

Play long enough and you'll realize what mathematics already confirms: without **perfect foresight**, no strategy is unbeatable.

-----

## What Makes a Die Gold?

This is the one rule everything else is built on. Learn it now.

> **Each of your 3 Crucible dice scores 1 point if its top value is:**
>
> - **6** — pure gold, always
> - **Equal to your Red Crystal die's top value** — transmuted by the Stone
>
> Any other value is lead — it scores 0. Your Red Crystal die itself never scores. Maximum: 3 points per phase.
>
> *Your Red Crystal die's top value is fixed throughout Phase 1 and Phase 2. It only changes if the game reaches The Immortal Tiebreaker.*

You score **twice** — once before The Tumble, once after. Your total is both phases added together.

-----

## Components

- **6 gray dice** — the Board, your shared draft pool
- **2 Red Crystal dice** — one per player, the Philosopher's Stone
- **2 yellow dice** — optional practice dice (see Tips below)
- **2 ten-sided dice** — optional score trackers for tournament play
- **Case** — a small metal mint container used to hold everything

**Facing Players Value** — the value on the side of a die facing the players. You choose this each time you place or orient a die.

**To Twist** — rotate a die without changing its top value. You are choosing which side is the Facing Players Value.

**To Tumble** — rotate a die 90° forward, away from you. The Facing Players Value becomes the new top value. This is how lead transforms into gold — or doesn't.

-----

## Setup

### Determine First Player

Each player rolls one die. The highest roll becomes Player A and goes first. If tied, re-roll until one player wins.

### Preparing the Board

Both players sit **side-by-side on the same side** of the table, facing the Board. Everything is visible to both players at all times.

### Setting the Red Crystal Dice

Each player has their own Red Crystal die. Set it randomly before play:

1. **Roll** your Red Crystal die to set its top value.
2. If the top is **6**, roll again until you get 1, 2, 3, 4, or 5.
3. **Before moving the die**, note the Facing Players Value — the value on the side most directly facing you. If it's unclear which side faces you, roll again.
4. Place your Red Crystal die to the **left of your Crucible**, with the Facing Players Value facing you. The Facing Players Value is used only if the game reaches **The Immortal Tiebreaker**.

The Red Crystal die never moves again during normal play.

### Setting the Board

Player A and Player B each roll 3 gray dice. Arrange all 6 dice in a row from lowest to highest top value, with some space between them so sides are visible. This is the Board.

-----

## The Draft — Refine Your Crucible

Players alternate turns starting with Player A. On each turn:

1. **Take** any die from the Board
2. **Twist** it — choose the Facing Players Value. This is your two-phase commitment: Phase 1 scores the current top value; Phase 2 scores the Facing Players Value after The Tumble. Choose both with intention
3. **Place** it in your Crucible, kept sorted from lowest to highest top value, left to right

Continue until all 6 dice are claimed — 3 per player.

-----

## The Poisoned Gift — The Exchange

Once the Board is empty, both players must give one Crucible die to their opponent — and choose the Facing Players Value their opponent receives.

### Which die must you give?

Look at all 4 of your dice: your 3 Crucible dice and your Red Crystal die.

- If any top values **repeat** among your 4 dice, you must gift a Crucible die **from the duplicate set with the lowest top value**
- If all 4 top values are **unique**, you may gift any Crucible die
- You can never gift your Red Crystal die

*Example: Your 4 dice show top values 2, 3, 5, 5 — you must gift a die showing 5. Your 4 dice show top values 2, 2, 4, 5 — you must gift a die showing 2.*

### Poisonous System Gift

Sometimes the **harm at the Exchange** comes from the **system**—the eligibility rules—not only from the opponent’s intent. The **Poisoned Gift** is always part of the game, but **duplicate tops** among your Crucible dice and Red Crystal can **restrict** which die you are allowed to gift, sometimes **forcing** a transfer you would not choose if every Crucible die were eligible.

That is a **structural trap**: a line that looks good for **immediate, visible scoring** can also create a duplicate pattern that **narrows** your options later. It also helps explain **off-path brittleness** in the benchmarks: a **blundering** opponent may produce a configuration that exposes the weakness of a **frozen**, solver-derived policy tuned to a tidy principal storyline.

For **learning systems**, the same pattern appears at a high level: **maximizing the obvious metric** can **create the conditions** for a later disadvantage—here through **eligibility and the machinery of the Gift**, not through missing a single tactical trick from the other player.

### How to reveal

Cover your Crucible with one hand. With the other, select your gift die, hold its top value steady, and Twist it to set the Facing Players Value your opponent will receive. When both players are ready, reveal and exchange simultaneously. Re-sort both Crucibles after the exchange.

<a id="note--research-claims-do-not-depend-on-simultaneous-exchange"></a>

### NOTE — Research claims do not depend on simultaneous Exchange

**Consumer v1.13** uses **simultaneous** reveal at the Gift. **Research benchmarks** also publish **sequential** Exchange variants (B moves after seeing A’s gift, etc.).

**What does *not* depend on simultaneity:** the main **ML** and **AI-safety** arguments—proxy rewards vs latent tiebreakers, **irrevocable draft** commitments, **static vs re-solving** at the Exchange, **misreported state**, and the **blunder / deployment** tables. In the standard 5,000-game suite, the **sequential** static-A row already shows **higher** B win rates than the **simultaneous** row, so removing simultaneity does **not** defang the commitment story.

**The minimal parable and Q-learning toy:** the **[Mortal vs Oracle parable](https://psdg.pages.dev/parable.html)** and **[Q-learning / bandit demo](https://psdg.pages.dev/qlearning-parable.html)** use **no Exchange at all**—only a regime change after training. Their “optimal on proxy, fail when the true rule fires” lesson is **orthogonal** to whether the full game’s Gift is simultaneous or sequential.

**What simultaneity *does* add** in the full game is a clean **game-theoretic** node (mixed strategies, Nash at a simultaneous move)—material for [game theory](https://psdg.pages.dev/gametheory.html), not a prerequisite for the headline safety or ML diagnosis. Longer argument: [AI safety — Simultaneous Exchange and the safety thesis](https://psdg.pages.dev/aisafety.html#simultaneous-exchange-and-the-safety-thesis).

-----

## The Reckoning

### Phase 1 — The Transformation

Score your 3 Crucible dice using their current top values. Apply the scoring rule above. This is the first test — how much gold did you claim in the draft?

### Phase 2 — The Treacherous Tumble

Now the hidden futures are revealed. Tumble each of your 3 Crucible dice — rotate each 90° forward so the Facing Players Value becomes the new top value. Your Red Crystal die stays still. Score your Crucible dice again using their new top values. Apply the scoring rule once more.

Add both phases together. **Highest total wins.**

-----

## The Immortal Tiebreaker

If both totals are equal, the Stones themselves decide. Your Crucible dice stay locked in their Phase 2 positions throughout.

**Tie Tumble 1:** Tumble each player's Red Crystal die away from you. The Facing Players Value of your Red Crystal die becomes its new top value. Score your Crucible dice against that new top value using the scoring rule.

**Tie Tumble 2:** Still tied? Flip each Red Crystal die over — the bottom becomes the new top. Score again.

**Tie Tumble 3:** Still tied? Tumble each Red Crystal die away from you once more — the current facing rises to become the new top. Score again.

**The Immortal Verdict:** Higher score wins. If still tied after all three Tumbles, the game is a draw.

-----

## Tips

1. Opposite faces always sum to 7. This means when Twisting a die, the one value you cannot choose as your Facing Players Value is always 7 minus the top value. Experienced players use this to calculate options without physically rotating the die.

2. Use the yellow dice to learn. Hold one while studying the Board and Crucibles, practicing the Twist and Tumble freely until the movements feel natural.

3. Using the ten-sided dice for scoring. Use these to track cumulative scores across multiple games — best of three, best of five, or any tournament format. A single die counts 0–10, but the mint tin extends its range: placed on the open lid it reads as 10 plus the shown value; placed inside the tin it reads as 20 plus the shown value — giving a range of 0–30 per die.

-----

## Alternative Seating

Once familiar with the game, players may sit opposite each other across the table. Each player places their Crucible to their own right, ensuring the top value and Facing Players Value of each die remain visible to both players at all times.

-----

*PSDG · Perfect Information · Deterministic After Setup · v1.13*

*In PSDG, unbeatable play requires **perfect foresight**.*
