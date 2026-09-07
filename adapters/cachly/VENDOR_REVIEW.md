# Vendor review: cachly (`cachly`)

Status: **adapter landed 2026-09-02; vendor review answered 2026-09-04. No run
of this harness has used the arm — the vendor rehearsed privately on its own
instances and reported the result in `reports/vendor-cachly-005c-007.md`.**

This file records the wiring that cachly is invited to review before any preregistered run.

## How the arm is wired

| surface | what it is |
|---|---|
| **Retrieval** | the published stdio MCP server, `npx -y @cachly-dev/mcp-server@0.10.145` |
| **Ingest** | a vendor supplied bulk loader, selected by `AMB_CACHLY_BULK_INGEST_COMMAND` |
| **Isolation** | one dedicated Brain instance supplied by `CACHLY_BRAIN_INSTANCE_ID` per corpus load |
| **Instruction** | the shared memory protocol, one sentence naming `smart_recall`, plus the capped result schema appendix |
| **Admission** | the `mcp__cachly__` prefix must appear in the session tool list |

The frozen config is `config.frozen.json`, and its sha256 is published in every session record.
The bulk loader receives the corpus root, manifest path, namespace and expected session count in
environment variables. It must print a JSON object with positive `sessions_offered` and
`items_stored` values, and the adapter refuses any mismatch.

## Judgement calls for review

1. The graded session receives six read tools: `smart_recall`, `recall_best_solution`,
   `recall_context`, `team_recall`, `brain_search` and `causal_trace`. Session learning,
   ambient hooks, cache writes and administrative tools are withheld because the corpus is frozen
   after ingest and the runner does not yet restore the Brain between seeds.
2. `smart_recall` is the primary search sentence because it is the product's natural language
   retrieval surface. Cachly's confidence threshold is preserved, so abstentions are observed as
   product behavior rather than bypassed by a lower level endpoint.
3. The bulk loader is an explicit prerequisite. The adapter refuses a missing loader instead of
   silently issuing thousands of public one-at-a-time writes with a different rate and cost shape.

## Cost accounting

The bulk loader owns Cachly's extraction and embedding accounting. The adapter reports the loader's
stored item count and wall time, while hosted token counts remain unknown until the vendor documents
the loader's metering fields. The run must not interpret unknown counts as zero.

## Reproducing the wiring

Set `CACHLY_BRAIN_INSTANCE_ID`, either `CACHLY_API_KEY` or `CACHLY_JWT`, and
`AMB_CACHLY_BULK_INGEST_COMMAND` from the vendor's private loader. The loader must accept the
environment contract documented above and print its JSON report. Then select `cachly` explicitly:

```text
python -m scripts.pilot --run-id cachly-probe --arms bare,claude_md,cachly --memory-instruction protocol
```

## Record

| date | event |
|---|---|
| 2026-09-02 | adapter request received in GitHub issue #61 |
| 2026-09-04 | vendor review response below; private rehearsal reported in `reports/vendor-cachly-005c-007.md` |

### Vendor response, verbatim

We have read the wiring and agree with it. Below are the three judgement calls
answered in order, one correction to the pin, and one answer to the open cost
question. Nothing here asks for a change that would favour us; where we ran
something different in our own rehearsal, we say so and say which way it moves
the numbers.

**1. Six read tools, writes withheld.**

Correct, and we would not narrow it. Those six are the product's read surface,
and withholding session learning, ambient hooks, cache writes and admin tools
is right for a frozen corpus — a graded session that can write is measuring a
different product.

One thing you should know before you read our rehearsal numbers: **we ran
three of the six**, not six, in every run reported in
`reports/vendor-cachly-005c-007.md` — `smart_recall`, `recall_best_solution`,
`causal_trace` — together with two session switches (`CACHLY_PROFILE=recall`,
`CACHLY_RECALL_COMPACT=1`) that are not in your config. That combination is a
cost lever we were testing, and it is worth about half the input tokens per
session. **Run the arm as you have it checked in.** Our expensive column
(005c, 170k–210k input tokens per session) is the honest prediction for your
wiring; our cheap column is what those two levers do, and it belongs in the
report as a finding rather than in your config as a default.

**2. `smart_recall` as the primary sentence, abstention preserved.**

Both correct, and the second one especially. Abstention is a product decision:
below its confidence threshold the server answers "nothing relevant found"
rather than returning a best-effort top-k. Bypassing it through a lower-level
endpoint would measure a system we do not ship.

One question back, because it decides what `absent` and `adjacent` actually
measure: does the checker treat an empty answer as a miss? In those two
conditions an empty answer can be the *correct* one. If it grades as a miss,
the two conditions reward a system that always answers something, which is the
opposite of the behaviour they exist to test. We have not read the checker
closely enough to claim it does — we are asking.

**3. The bulk loader as a hard prerequisite.**

Agreed, and for a second reason beyond rate and cost shape. The loader also
enforces acceptance: it refuses unless semantic coverage reaches 95 % after
the load. We added that after measuring the failure it prevents — under rate
limiting, entries get stored without their vectors, the store answers by key
and returns nothing by similarity, and every layer above reports success. A
run against a half-embedded store produces numbers that look like a weak
product rather than a broken load. Your gate should not have to detect that,
and with the loader it does not.

**One correction to the pin.** Your `config.frozen.json` pins `0.10.145`. That
version is fine to run, but three things relevant to this arm landed after it:
the compact recall rendering and the lean tool profile (both switches, both
off by default), and — as of `0.10.165` — a fix to the confidence field that
matters for grading: until then, *reading* an entry stamped it as verified and
reset its staleness clock. If you re-pin, `0.10.165` or later is the version
whose age badge means what it says. Either choice is defensible; pinning
`0.10.145` and citing this file is fully reproducible, which is what matters.

**The open cost question.** Your file says hosted token counts remain unknown
until we document the loader's metering fields. The loader prints, on success:

```json
{ "refused": false, "sessions": N, "items_stored": N, "baseline_lessons": N,
  "coverage_percent": N, "duration_seconds": N, "notes": [...] }
```

`baseline_lessons` is the count of starter entries a fresh instance seeds by
itself before any corpus write — disclosed because it is product-as-shipped
onboarding, not bench preparation. What the loader does **not** report is a
hosted token count, and we should not pretend otherwise: embedding happens
server-side and is billed per instance, not per call, so there is no per-load
token figure to hand you that would mean anything. `duration_seconds` and
`items_stored` are the two honest cost figures we can give. Treating the token
count as unknown rather than zero, as your file already says, is the right
call.

**One request, and it is the only one.** In `reports/vendor-cachly-005c-007.md`
we report that on the cells your conditions actually plant, a model with no
memory solves about as many as ours does — twice measured, once slightly for
us and once slightly against. If that reading is wrong, we would rather hear it
from you than keep repeating it.
