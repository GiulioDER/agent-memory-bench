# RE-call Hosted deterministic retrieval replay

`scripts.recall_hosted_replay` executes one preregistered hosted variant over the checked-in corpus
and task prompts. It sends only the original task prompt to Search. The task `fact_terms` remain in
the harness and are applied after retrieval to calculate hit depth, complete evidence coverage,
reciprocal rank, item count, and character count.

Each variant must run against an isolated corpus and a service started with the matching
`RECALL_AML_VARIANT`. The runner reads `/version` before deleting or ingesting anything and refuses
when the served variant does not match `--variant`.

Set the harness credential and run one arm:

```powershell
$env:AMB_RECALL_HOSTED_API_KEY = "<dedicated-memory-system-key>"
python -m scripts.recall_hosted_replay `
  --variant A0_raw `
  --base-url https://variant-endpoint.example `
  --output results/aml-hosted-v1/A0_raw.json
```

Run the same command for `A1_compiler`, `A2_facets`, `A3_rerank`, `A4_pack_5000`,
`A4_pack_7000`, and `A4_pack_9000`. The output path is append-only in practice: the runner refuses
to overwrite an existing artifact. Preserve each endpoint's `/version` payload and the corpus and
task digests embedded in every result before comparing arms.

Every result also records compiler fallback counts from Add and request-local query planner and
reranker fallback counts from the hosted Search response headers. This keeps provider degradation
visible without changing the AML response body or placing benchmark content in logs. Missing or
nonbinary fallback headers invalidate the replay instead of being counted as successful primary
requests.

The replay is a retrieval screen, not the executable outcome. After selecting the smallest A4
context budget within the preregistered coverage margin, use `scripts.pilot` for the fixed
executable screen and final paired comparison.

After all seven immutable replay files exist, validate and select them mechanically:

```powershell
python -m scripts.recall_hosted_select `
  --input-dir results/aml-hosted-v1/replay `
  --output results/aml-hosted-v1/replay-selection.json
```

The selector requires exactly one artifact per registered variant and refuses population, corpus,
task, commit, model, or prompt identity drift. It preserves all attribution summaries and chooses
the smallest eligible A4 budget.
