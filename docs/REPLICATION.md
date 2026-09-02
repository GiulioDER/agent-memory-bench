# Replicate, verify, or break this benchmark

The benchmark's own rule is that reproduction is the product: if a published number cannot be
regenerated from the pinned versions, the frozen configs, the sha256-pinned corpus and the
committed preregistration, that is a defect and should be filed as one.

This file is the other half of that rule. It is the **outside runner's path**: what to run, what a
report has to contain to be comparable with anything, and what happens to it afterwards.

It deliberately does not restate what reproduces and what does not. That lives in
[`README.md`](../README.md), under *Checking a published run* and *What a third party can
reproduce today, and what they cannot*, and duplicating it here is how two documents drift apart
and one of them starts lying. Read those two sections before spending money.

## Start free. Two commands, no credentials, no model calls.

```bash
git clone https://github.com/GiulioDER/agent-memory-bench && cd agent-memory-bench
pip install -r requirements-dev.txt
python -m pytest tests/ -q          # is the instrument what it claims to be?
python -m scripts.verify_run --all  # did the published numbers come from the published sessions?
```

The first asserts the properties every result rests on: that each **naive** reference solution
fails its checker and each **informed** one passes, so a task cannot be solved without the fact
the corpus carries; that the leaderboard on the site is byte-identical to a regeneration from
`results/<run_id>/leaderboard_summary.json`, so no number can be typed onto the page; and that a
live run refuses to start without explicit prices and a clean `preregistration/`.

The second re-derives the cost ledger, the endpoints and the discard set from each run's own
per-session records and fails if they disagree with what was committed.

⚠️ **`verify_run --all` reports eight failures today, and none of them is a bug in your
checkout.** Every one is a run whose per-session **streams** were never captured, so its records
can be checked against each other but not against the sessions that produced them. Each prints a
`note` line naming the reason. Those streams do not exist in any checkout or on the run host and
are not recoverable, so the honest state is annotated rather than repaired, and the failures still
count against the verified total rather than being silenced. The list is in
[`docs/STATUS.md`](STATUS.md).

If you find a failure that carries **no** `note`, that is a new finding and worth reporting.

Neither command tells you the benchmark is well designed. They tell you the arithmetic is honest
and the instrument discriminates. Whether the tasks measure memory is what the preregistrations
and the vendor reviews are for, and it is the more interesting thing to argue with.

**A test that fails on a clean clone is the highest-value report this project can receive**, and
it costs you nothing to find. File it as a benchmark defect.

## Then, if you want to spend money

The static control arms need only the Claude Code CLI and a model key, and the README puts the
full grid across them at roughly the price of a coffee. That is not a consolation prize: the
headline of `official-003` is a **null**. No arm's confidence interval excludes zero, and the
inert `placebo` arm, which carries no memory content whatsoever, scored highest of any arm on the
board. Re-running the controls is re-running most of what the published run actually concluded.

Two requirements that are easy to miss:

- **Claude Code CLI 2.1.221 or later.** Below that, a pending MCP server runs a session without
  its tools while reporting success. The admission gate exists because that happened.
- **Prices are required and have no defaults anywhere.** `--price-in`, `--price-out` and
  `--price-as-of` must be passed to any live run, because three runners once carried three
  different sets and none matched the frozen rates. Dry runs need none.

## What a replication report must contain

Report through the **replication report** issue template. Five things, and a report missing any of
them cannot be compared with anything:

| field | why |
|---|---|
| the run id you targeted | the published runs are not interchangeable, and two of them are explicitly not poolable |
| the commit sha you ran at | the instrument changed on 2026-08-29; a result measured across that boundary is not comparable with one measured before it |
| model, provider and CLI version | the published runs are `deepseek-v4-flash` through OpenRouter. A different model is an extension, which is welcome, but it is not a replication |
| arms, seeds, admitted **and discarded** cells | a discard count is not a footnote. A cell is admitted only when every arm produced a record, so each added arm is another way to lose a whole cell, and discards are the largest single threat to a comparison |
| the prices you passed | two published runs of this project were priced on different bases and neither artifact said so. Where you can, compare on tokens instead |

**Direction and significance are what replicate. An exact rate will not, and is not expected to.**
A different admitted set is a different set, not the same one with noise on it.

## What happens to your report

**It does not enter the leaderboard, and there is no way to submit a score to it.** That board
carries one preregistered official run at a time, pointed at by
`site/data/leaderboard.config.json`, and numbers reach it exclusively through a generated file
that CI checks against its own regeneration. This is not a ranking of contributors.

What an independent report gets instead is the thing a leaderboard cannot give: **standing to
contradict**. A replication that comes out the other way, on the record, against a committed
preregistration, is evidence about the benchmark itself. Reports are answered in the open, and a
report that falsifies a published claim gets that claim corrected the way this project corrects
everything, by appending to the preregistration and never by editing a published number.

Results here publish in full, win or lose, including the authors' own. That rule is worth exactly
as much as the first time it costs something, so a report that makes it cost something is doing
the project a favour.

## Entering a product

A different path, with its own eight rules: see
[Submit & reproduce](https://giulioder.github.io/agent-memory-bench/submit.html). In short, a
product competes as its own shipped Claude Code integration, enters through a pull request adding
one hash-pinned `adapters/<name>/` directory, and every vendor is invited to review its adapter
and frozen config before any measured run.
