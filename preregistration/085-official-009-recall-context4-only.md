# official-009-recall-context4-only: RE-call Voyage Context 4 condition evaluation

This run evaluates the latest RE-call checkout as a standalone arm across all five AMB corpus
conditions. It is not a paired vendor comparison: no `bare` reference arm is run, so paired harm,
benefit, and usefulness endpoints are intentionally not interpreted.

## Frozen treatment

- Run ID: `official-009-recall-context4-only`
- Namespace prefix: `amb-recall-context4-official-008` (the already verified `present` tenant is
  reused read-only; the other conditions receive their own suffix tenants)
- Arm: `recall` only
- Conditions: `present`, `contradictory`, `adjacent`, `absent`, `superseded`
- Seeds: 5
- Model: `deepseek/deepseek-v4-flash`
- Memory instruction: `protocol`, held constant with official-008's RE-call treatment
- RE-call source: commit `5366770ea96a8ee4438a3bc8a749f521a20e4335`
- Embedder: `voyage-context:voyage-context-4`
- Corpus grouping: `voyage-context-document-v1`
- Reranking: disabled

Each condition is assembled and ingested into its own tenant from the frozen AMB feed. The pilot
uses the rootless participant and checker containers, the signed memory relay, and the same
admission and artifact rules as the paired benchmark. A condition is counted only when its
participant records, checker results, raw streams, and signed adjudication receipt are complete.

## Command

```text
python -m scripts.abstention \
  --run-id official-009-recall-context4-only \
  --namespace amb-recall-context4-official-008 \
  --conditions present,contradictory,adjacent,absent,superseded \
  --arms recall --recall-only --seeds 5 \
  --model deepseek/deepseek-v4-flash \
  --memory-instruction protocol --resume
```

The result reports per-condition solved/outcome and recall search rates, plus standalone wrong-fact
and abstention classifications where those conditions define them. It must not be presented as a
claim that RE-call beats another arm, because no reference arm is present in this run.
