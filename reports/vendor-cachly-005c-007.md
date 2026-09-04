## Vendor review: cachly on agent-memory-bench

We ran your four conditions on our own instances, with the adapter and the
pins frozen before the first cell, and a pre-registration written before the
first result. This is the whole report, including the part that does not
flatter us.

### Before the numbers: this is not your wiring

`adapters/cachly/VENDOR_REVIEW.md` says the review window has not opened and no
run has used the arm. That is correct, and everything below is a **private
rehearsal on our own instances**, not a run of yours. It differs from the
adapter as you checked it in, in three ways that all move the numbers:

| | your `config.frozen.json` | what we ran |
|---|---|---|
| pin | `0.10.145` | `0.10.151` (005c), `.157` (006), `.161` (007) |
| read tools | **6** — `smart_recall`, `recall_best_solution`, `recall_context`, `team_recall`, `brain_search`, `causal_trace` | **3** — `smart_recall`, `recall_best_solution`, `causal_trace` |
| session env | none | `CACHLY_PROFILE=recall`, `CACHLY_RECALL_COMPACT=1` |

The last two are not incidental: they are two of the three cost levers this
report is about. **A run on your wiring as checked in would produce our 005c
column, not our 007 column** — roughly 170k–210k input tokens per session
rather than 80k–90k. If you run the arm officially without changing anything,
please expect the expensive numbers, and read our cost sections as "what these
two levers do" rather than as a prediction of your result.

We would rather say that here than have you find our numbers irreproducible.

Answers to the three judgement calls in your file go in that file, not this
one.

### What we ran

Three runs, each with its adapter and pin frozen before the first cell and a
pre-registration written before the first result:

| Run | Pin | What it was for |
|---|---|---|
| 005c | `@cachly-dev/mcp-server@0.10.151` | the expensive baseline |
| 006 | `0.10.157` | three cost levers |
| 007 | `0.10.161` | recovering the wins 006 lost |

Common to all three:

- Ingest through the product's real MCP write path (`learn_from_attempts` per
  1600-character transcript chunk), not a reimplementation.
- One dedicated, freshly provisioned instance per condition.
- Three read tools granted (`smart_recall`, `recall_best_solution`,
  `causal_trace`), shared protocol text, instruction appendix 869 bytes,
  under your 33% cap on the base prompt.
- Model `deepseek-v4-flash` for every arm, 30 cells per condition, one seed.
- Acceptance before any session: semantic coverage ≥ 95% via the product's
  own `brain_doctor`, otherwise the loader refuses and the run does not start.

One correction we owe you about our own bookkeeping, found on 2026-09-04 while
preparing the next run: our file named `config.frozen.007.json` records pin
`0.10.157`, but 007 actually ran on `0.10.161`. The adapter reads
`config.frozen.json` and nothing else; the copies with a number in the name
are records, and that record was wrong. The three releases in between are
counting and logging fixes, so nothing in the numbers above moves — but the
file that carries the version in its name was not the file that ran, and you
should hear that from us rather than find it.

### Results

| Condition | cachly | bare | claude_md |
|---|---|---|---|
| present | **23/30** | 18/30 | 15/30 |
| absent | **21/30** | 16/30 | 15/30 |
| superseded | **25/30** | 16/30 | 16/30 |
| contradictory | **18/30** | 16/30 | 16/30 |

Contradictory after your admission gate: 17/28 vs 15/28 vs 15/28 — two cells
discarded because the MCP server reported `status: "failed"` at session init
(more on that below).

### The cost, which is the part that matters

| Condition | cachly tokens/session | bare | cachly wins/Mtok | bare wins/Mtok |
|---|---|---|---|---|
| present | 169,822 | 28,152 | 4.5 | 21.3 |
| absent | 158,647 | 37,529 | 4.4 | 14.2 |
| superseded | 210,257 | 40,354 | 4.0 | 13.2 |
| contradictory | 182,198 | 48,860 | 3.3 | 10.9 |

We win every condition and we are four to five times more expensive per
session. Per win: about 253k tokens for cachly against 76k for bare in
superseded. If your headline metric is wins per million tokens, bare wins
and we lose, in all four conditions. We are not going to argue that away.

Decomposition (superseded, 90 sessions): cachly took 15.3 model turns
against bare's 10.5, made 5.6 memory calls per session, and carried 24,059
characters of tool-catalogue text against bare's 4,116. Every turn resends
the whole context, so the 27-tool catalogue alone (~8,860 tokens) accounts
for roughly 133k of the 210k.

### What we did about it

We pre-registered three levers and ran them as a separate run (006), same
corpus, same model, fresh instances, pin 0.10.157:

- a `recall` tool profile that lists exactly the three granted read tools
  (3,470 bytes instead of 32,806),
- an appendix rule "recall once before you act",
- a compact recall rendering (five hits, no score prose, no feedback ask).

| Condition | 005c wins | 006 wins | 005c tokens | 006 tokens |
|---|---|---|---|---|
| present | 23/30 | 20/29 | 169,822 | 68,329 |
| absent | 21/30 | 19/28 | 158,647 | 76,896 |
| superseded | 25/30 | 20/30 | 210,257 | 69,077 |

Cost fell by a factor of 2.1 to 3.0. Wins fell too, and in superseded they
fell hard: five cells. We wrote the win floors into the pre-registration
before the run, and superseded missed its floor by four. So this is a
failed run against its own stated bar, and we are reporting it as one.

We then compared the flipped cells one by one (present and superseded). The
cause is the same in 8 of 8 real losses: the deciding sentence sits in the
last chunk of a long session, and a single, generic query does not surface
it. In 005c the second, third or fourth query did — often through
`brain_search` or `recall_best_solution`, tools the lean profile removes.
The compact rendering was the cause in none of them.

Run 007 (pre-registered before the run) tested exactly that: one extra lesson
per session whose text begins with the session's last turn, plus an appendix
that asks for the task's own wording as the query.

### Run 007: the cheap configuration holds, and the planted cells still do not move

| Condition | cachly | bare | claude_md | cachly in-tok/session | memory calls |
|---|---|---|---|---|---|
| present | **22/30** | 15/30 | 16/30 | 82,939 | 2.87 |
| absent | **21/30** | 17/30 | 14/30 | 78,524 | 2.73 |
| superseded | **22/30** | 18/30 | 14/30 | 89,906 | 3.10 |
| contradictory | **20/30** | 16/30 | 14/30 | 107,271 | 3.23 |
| **total** | **85/120** | 66/120 | 58/120 | | |

On your headline metric we still lose, and by less than before but clearly:

| Arm | wins | in-tok/session (mean) | wins/Mtok |
|---|---|---|---|
| claude_md | 58/120 | 38,407 | **12.6** |
| bare | 66/120 | 50,208 | **11.0** |
| cachly | **85/120** | 89,660 | 7.9 |

We solve 29 % more cells than `bare` and cost 79 % more tokens to do it. In
005c the same comparison was 4.0–4.5 against 13–21; the gap has closed by
roughly a factor of two, and it has not closed enough. We are not going to
argue that away either.

Against 005c that is close to the same wins at roughly half the price
(superseded: 22 against 25, 89,906 against 210,257 input tokens per session).
We wrote win floors into the pre-registration before the run and 007 does not
clear them, so by our own stated bar this is not a pass — it is the best point
on the price/wins curve we have measured, and both halves of that sentence
belong in the record.

One disclosure about `contradictory`: our model account ran out of credit on
the first attempt, after 43 of 90 sessions. The remaining 46 returned
`api_error (HTTP 402)`, your pilot discarded the affected cells, and the
summary printed 11/13 for cachly — a number that looks like a good result and
stands on a run that stopped halfway. We re-ran the condition on a fresh
instance rather than report that figure. The row above is the re-run: 90
sessions, 30 cells admitted, zero errors. **This is the same failure shape as
the `'claude' is not on PATH` case below: a tool failure that survives into
the summary looking like a measurement.**

### The planted/untouched split, measured a second time

We repeated the split from 005c across all four of 007's conditions:

|  | cells | cachly | bare | difference |
|---|---|---|---|---|
| planted | 34 | 27 | 28 | **−1** |
| untouched | 86 | 58 | 38 | **+20** (23.3 pp) |

In 005c the same split gave +3 planted against +18 untouched. In 007 the
planted difference is **negative**: on the cells where your conditions plant
their manipulation, a model with no memory at all solves one more than we do.
Per condition, planted cells: absent 10 against 9 for bare, superseded 8
against 9, contradictory 9 against 10.

We are the vendor and this is the number that hurts most, so to be explicit
about what we think it means and what we do not: it does not say memory is
useless — the untouched cells are ordinary retrieval, we are 23 points ahead
there, and that has now been measured twice on two independent runs. It says
**the four conditions, as planted, do not currently separate a memory system
from a bare model**, and that any floor stated over the totals is mostly a
floor on ordinary retrieval wearing a condition's name.

Every number in this section was recomputed from `records.jsonl` with errored
sessions excluded, not read off the pilot summary.

### The noise floor, which we only found by running the same condition three times

We did not set out to measure this. Run 008 needed a restart, so condition
`present` ran three times with the identical task set. `bare` sees no memory,
no CLAUDE.md, and the same sandbox every time — whatever it does differently
between runs is the harness talking, not the product.

| run | cachly | bare | claude_md | cachly − bare |
|---|---|---|---|---|
| A | 22/30 | 15/30 | 16/30 | +7 |
| B | 21/30 | 15/30 | 13/30 | +6 |
| C | 25/30 | 19/30 | 18/30 | +6 |

`bare` moved by four cells across identical inputs. `claude_md` by five. Cell
by cell, two to five flip between any two runs — and in run C all three arms
rose together, which is a property of the run, not of any arm.

**The difference to the memory-less arm barely moves: +7, +6, +6.**

Two consequences we think are yours as much as ours:

- **A floor stated on an absolute cell count is not testable at one run per
  cell.** Our own pre-registrations say things like "≥ 82 of 117" and
  "superseded ≥ 23/30". Both sit inside ±4 per condition. We wrote them; they
  cannot be checked the way they are written.
- **The difference to `bare` in the same run is the number that survives.**
  It costs nothing extra — `bare` runs anyway — and it moved by one cell where
  the absolute counts moved by four.

This is the "one seed, one run per cell, no repeat-variance measurement" line
in our Limits section, with a number attached. If you take one thing from this
report for the harness itself, we would suggest it be this one.

### A finding about the harness that changed our reading of our own numbers

While preparing this we split every cell by whether its condition was
actually planted in it. We had not done that before, and it turned out to
matter more than anything else we measured.

Each condition plants its manipulation in 11 or 12 cells. The rest stay
untouched and are, across all four conditions, the same ordinary retrieval
cells. Over 120 cells that is **34 planted against 86 untouched.**

In 005c, our advantage over `bare` is +21 cells. **Eighteen of those 21 sit
in the untouched cells.** The lift is 8.8 percentage points on the planted
cells against 20.9 on the untouched. On the eleven `contradictory` poison
cells — where both stored memories are wrong — cachly and `bare` both solve
9. Exactly level. The memory neither helps nor hurts there.

Now the part that matters for the cost work. Our cheap run (006) against the
expensive one (005c), same split:

| Condition | 005c planted | 006 planted | 005c untouched | 006 untouched |
|---|---|---|---|---|
| present | – | – | 23/30 | 21/30 |
| absent | 10/12 | 10/12 | 11/18 | 10/18 |
| superseded | 10/11 | 10/11 | 15/19 | **10/19** |
| contradictory | 9/11 | **10/11** | 9/19 | 9/19 |
| **Total** | **29** | **30** | **58** | **50** |

    006 against 005c on PLANTED cells:   +1
    006 against 005c on UNTOUCHED cells: -8

The entire loss of the cheap configuration sits in cells where no condition
was planted. On the work the conditions were built to measure — a superseded
fact, a missing fact, two contradictory memories — the cheap run is level or
better, at half the price.

We had been reporting "three of four floors missed". That sentence is
accurate about the totals and misleading about the mechanism, because the
totals sum across two different kinds of cell. On the eleven planted
`superseded` cells we already solve 10 — a floor demanding +4 there cannot
be met by any product.

Two consequences we have already acted on:

1. Every floor in our pre-registrations is now stated separately for planted
   and untouched cells, next to the `bare` arm of the same run. A single
   number over both was measuring two things at once.
2. Our next lever is aimed at the untouched cells, because that is where the
   eight went.

**For your harness**, three suggestions, in the order we would rank them:

- Report planted and untouched separately by default. A reader of the totals
  cannot tell whether a product is good at the condition or good at ordinary
  retrieval, and those are different claims.
- On `contradictory`, consider whether 11 poison cells among 30 is enough
  signal. At 9 against 9 the condition currently separates nothing.
- `results/probelauf-005c-superseded` in our tree is unusable: 29 of 30 cells
  died with `'claude' is not on PATH` and the records still carry
  `success: false`, indistinguishable from a real miss without reading the
  `error` field. A tool failure should not be able to look like a result.
  We caught it because a number came out impossibly low; a smaller gap would
  have gone through.

### The pre-registered weakness, answered

In the adapter request we wrote this before any number existed:

> We expect the `superseded` condition to hurt us. Our store currently lets
> successes overwrite while corrections merely append — a defect we documented
> against ourselves last week. If your harness confirms it, you will have
> measured our backlog.

**It confirmed it.** On the 11 planted `superseded` cells in 007, the memory
arm solves 8 and the memory-less arm solves 9. We are one behind a model that
was given nothing at all, on the condition we named as our weak spot.

The 005c run had looked better there (10 of 11), which is why we are reporting
both: one run per cell and a noise floor of ±4 means neither number settles
it. What survives across both is the direction — `superseded` is the condition
where our advantage over `bare` is smallest, and it is the one we predicted.

Since then we went and measured the mechanism in our own store rather than
inferring it from your cells, and it is worse than we described:

- 735 stored entries. **Two** carry a supersession edge.
- Those two point at **each other** — A supersedes B and B supersedes A. Both
  cannot be current, and which one gets suppressed then depends on the read
  path.
- About **12 %** of entries contain an explicit correction word ("instead",
  "no longer", "turned out to be"). None of that 12 % was linked to what it
  corrected. The store had the evidence that it was contradicting itself and
  no field in which to write it down.

The suggestion mechanism that should have caught this was built and wired, and
it fires almost never for a structural reason: it only ever sees the five best
keyword hits as candidates, and keyword overlap is precisely what supersession
pairs do not have. Measured on the real pairs: 0.086 average overlap, against a
90th percentile of 0.104 across all pairs. The older entry is not on the
candidate list at all.

Two detectors we tried and dropped, both cheap to run and both reported here
so nobody repeats them:

- **Typed value collision** (same key, different value — addresses, ports,
  pins). 58 single-valued keys extracted from the store, 56 in agreement, 2
  collisions, and both collisions were false on inspection. The lesson is that
  the key has to be single-valued *by nature and scoped*: `port:<host>` is not
  a key, and the same environment variable name in two systems is two keys.
- **An NLI cross-encoder** on the pair, ~280M parameters, public. On 11 real
  supersession pairs the median contradiction score was 0.966. On a control of
  unrelated pairs from the same corpus it was 0.818, with 5 of 11 above 0.9 —
  62 % precision at that threshold, on a store where almost no pair is a
  supersession. Eleven pairs is not an eval; the overlap is wide enough that we
  are not building on it.

None of this changes a number in the tables above. We include it because the
issue that opened this collaboration promised a pre-registered weakness, and
"your harness confirmed it, and here is how far we got with the fix" is the
only honest way to close that loop.

### Five product defects your process found

Your step 1 said a private rehearsal would surface our backlog. It did:

1. A gate meant to protect against re-ingest blocked legitimate re-ingest
   into an instance that had ever been written to (0.10.150).
2. The embedding-gap healer took its marker out of the set before writing
   the vector; a process death in between lost the marker permanently —
   29 of 290 lessons in one instance were unhealable (0.10.151).
3. Factory starter lessons were written without vectors and without markers
   (0.10.153).
4. The autopilot guide wrote `cat >` where it meant `cat >>`, which would
   truncate an existing CLAUDE.md (0.10.152).
5. Instance-bound API keys were rejected with 403 on `/embed`, which is
   exactly the credential shape your run needs (PR #610).

All five are public releases. None of them would have been found by our own
test suite, because all five need a real corpus at scale.

### Three things we would change in the harness

1. **A cost-aware metric.** Wins per million raw tokens punishes any memory
   system that sends context, and rewards one that sends none. With prompt
   caching, a resent catalogue costs a fraction of a fresh one; the raw-token
   count cannot see that. We are not asking you to drop the raw count — we
   are asking for a second column that a buyer could act on.
2. **Retry a session whose MCP server failed at init.** Four cells across
   our runs were discarded because the server reported `status: "failed"`
   with an empty error list at startup, under load. Discarding is honest;
   it also costs cells that have nothing to do with the product under test.
   Your `harness/memory_startup.py` already probes and retries — it did not
   catch these.
3. **One checker looks inconsistent.** In `ts-round-money` the checker text
   asks for "5.67" while every arm's transcript computes "18.05". We did not
   resolve it and we are not claiming it is wrong; it looks like a fixed
   placeholder rather than a cell-specific value.

### Disclosures

- A fresh free instance auto-seeds 16 generic starter lessons at first tool
  contact. This is product-as-shipped onboarding, not bench preparation. We
  audited their effect: in contradictory, cachly won 9 of 13 cells where a
  starter lesson appeared in the session text and 9 of 17 where none did.
  They are present, and they do not decide.
- In condition `contradictory` your corpus sets `include_real: false`: both
  planted memories are wrong for all 11 planted cells. A memory system
  cannot win there, only avoid harm. Our +2 is "did not harm", and our one
  arm-specific loss (`ts-tz-utc`) is a case where the retrieved framing
  pulled the model away from the correct default that bare found without any
  memory at all. That is a real cost of retrieval and it belongs in the
  record.
- Run 006's `present` condition reused the instance from an aborted first
  attempt (same corpus, same topics, ingest re-run). Content-equivalent, not
  literally fresh. Written into our pre-registration the night it happened.

### Limits

One seed, one model, one run per cell — and, as the section above now shows
with a number, that is a real limit rather than a formality: the memory-less
arm alone moves by four cells of thirty between identical runs. The adapter is
ours; the corpus, the checkers and the admission gate are yours. Every number
above is reproducible from the raw records in the runs we will hand over with
the credentials.

### What is still running

Run 008 is in progress as we send this and is deliberately **not** in the
tables above. It tests a single pre-registered change — ten hits per recall
instead of five — on the same corpus and the same model.

We will publish that one the same way, whatever it says. Two things are worth
naming now, because both are the kind of detail a vendor is tempted to leave
out:

- Its first attempt is already discarded. It changed three things at once
  instead of one: an ingest switch was off that 007 had on, and the
  instruction appendix had been edited that afternoon — the line "recall once
  before you act" was missing, which is exactly the rule that bounds the
  number of recalls. What gave it away was `bare` moving by 68 % in tokens,
  and `bare` cannot see any of it. The run was thrown away and restarted with
  the appendix byte-identical to 007's.
- One of its pre-registered cost floors rests on our own arithmetic error. We
  wrote "one extra recall ≈ 19,000 tokens (every turn resends everything)"
  against "one extra hit ≈ 100 tokens" — and the clause in the brackets
  applies to both. Measured at 12.5 turns per session, an extra hit costs
  about 1,350 tokens. The true ratio is 14:1, not 190:1. We are reporting the
  floor as missed and correcting the number in the next pre-registration
  rather than the other way round.

If any of this is useful to the harness rather than only to us, take it. The
part we would most like to hear your view on is the planted/untouched split:
on the cells your conditions actually plant, twice measured, a model with no
memory solves as many as we do.
