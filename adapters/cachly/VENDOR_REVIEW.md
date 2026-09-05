# Vendor review: cachly (`cachly`)

Status: **adapter landed 2026-09-02, review window not opened. No run has used this arm.**

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
| pending | vendor review invitation and response |

### Vendor response, verbatim

(none received)
