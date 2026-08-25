# I Gave Claude Code a Placebo Brain. The 13.9-Point Loss Disappeared.

*Part II of the coding-agent memory benchmark*

Disclosure first: I build RE-call, a memory layer for coding agents, so I am not a
disinterested observer here. That is exactly why I preregister the experiments, publish
the losing runs, and keep the admission gate strict.

In the first article, the most surprising result was not the memory layer winning. It
was the static `CLAUDE.md` arm losing to bare Claude Code by 13.9 percentage points.

That result suggested two very different explanations:

1. A long static file dilutes the context even when its content is harmless.
2. The specific instructions are actively distracting the model.

Those explanations lead to different advice. The first says trim the file. The second
says rewrite it.

So I added a placebo arm.

## The placebo test

The benchmark ran 24 executable coding tasks, three seeds, and four arms:

- bare Claude Code
- a neutral placebo file
- the original task-specific `CLAUDE.md` bundle
- RE-call with the static bundle and retrieval skill

The placebo was generated separately for every task. It matched the corresponding
`CLAUDE.md` file exactly on line count and whitespace-delimited token count. It kept the
shape of the Markdown, but replaced the content with neutral project prose. It contained
no task facts, commands, repository paths, or instructions that could solve the task.

The plan was 288 sessions in 72 paired cells. The agent had to produce a working artifact
in the repository, and deterministic checkers graded the result. There was no LLM judge
deciding whether an answer sounded good.

## The result

| Arm | Successful cells |
|---|---:|
| Bare | 26/63, 41.3% |
| Placebo | 30/63, 47.6% |
| `CLAUDE.md` | 27/63, 42.9% |
| RE-call | 39/63, 61.9% |

The placebo did not lose to bare. It was slightly higher.

The original `CLAUDE.md` bundle did not lose to the placebo either. It was slightly
lower, but the difference was not statistically reliable.

The preregistered paired results were:

- placebo minus bare: `+5.56` points, 95% cluster interval `[-2.78, +15.28]`, `p=.219`
- `CLAUDE.md` minus placebo: `-4.86` points, 95% cluster interval `[-18.75, +9.03]`, `p=.453`

Both intervals cross zero. Neither explanation survives this ablation as a confirmed
mechanism.

The honest conclusion is less dramatic than the first headline: the 13.9-point loss did
not replicate. It may have been task composition, model variance, or ordinary noise. This
run does not justify telling people that static project instructions are harmful, and it
does not justify telling them that file length is the culprit.

That is why placebo controls matter. A compelling number can still be the wrong story.

## The memory result did replicate

The RE-call arm was a secondary continuity check, not the placebo experiment's primary
endpoint. It still outperformed the static bundle:

- RE-call: 61.9%
- `CLAUDE.md`: 42.9%
- paired per-task delta: `+17.36` points
- 95% cluster interval: `[+4.86, +31.25]`
- McNemar `p=.001831`

RE-call searched in 54 of 63 admitted cells. When it searched, it reached the governing
task evidence in 50 of 54 cells. Overall, it reached that evidence in 50 of 63 cells.

That pattern is consistent with the production intuition behind retrieval memory: useful
project facts do not need to be present in every prompt. They need to be available when
the task calls for them.

There is a cost. The recall arm used 5.26 million metered tokens and cost an estimated
`$0.3196`, compared with `$0.0842` for the `CLAUDE.md` arm. It also took longer. A memory
layer is not free simply because retrieval is selective. The benchmark has to measure
the success gain, token overhead, latency, and operational reliability together.

## The operational footnote is part of the result

The full run completed all 288 sessions, but the admission gate retained 63 paired cells
and discarded 9. Eight discards were recall MCP startup failures, and one involved the
placebo arm. The run passed the preregistered limit of fewer than 10 discarded cells, but
only by one cell.

That matters. A memory benchmark that quietly treats a missing memory server as a failed
agent would confuse infrastructure with intelligence. The gate discarded those cells
instead. The discarded cells are published, not hidden.

Before this valid run, I also had to replace a stale database connection, create an
isolated VPS2 database, apply the schema migrations, index the 721-chunk corpus, and run
a no-surprise MCP preflight. The invalid attempts remain archived separately and are not
part of the statistics.

## What I am changing next

The next version needs to answer questions that a single success rate cannot answer.

First, I want to split retrieval failures into four classes:

- the agent did not search
- it searched but found nothing useful
- it found the wrong memory
- it found the right memory and ignored it

Each class implies a different fix. Combining them into one failure bucket hides the
engineering decision.

Second, I am adding known-bad repository twins for every task. A checker that cannot go
red on a deliberately wrong repository is decoration. The agent-side admission gate
proves that the treatment was present. The known-bad twin proves that the judge can reject
the wrong result.

Third, I want a `wrong_memory` arm. It will inject plausible but stale evidence and measure
the downside of retrieval. A well-calibrated memory system should refuse or discount bad
memory. If wrong memory merely makes the agent confidently worse than bare, that is a
production failure even if the average retrieval score looks good.

## The larger goal

The goal is no longer just to show that one memory layer can improve one coding-agent
benchmark. I want to build a reproducible industry benchmark for coding agents and memory
systems, measuring task success, retrieval behavior, stale-memory risk, checker validity,
cost, latency, and operational reliability.

The most valuable result in this run was not a clean victory. It was a clean refusal to
overinterpret the original 13.9-point number.

If you are building a memory layer, a coding agent, or an evaluation harness and want to
help shape the benchmark, I am open to collaboration. The benchmark is more useful if the
people being measured can challenge the controls before the leaderboard exists.
