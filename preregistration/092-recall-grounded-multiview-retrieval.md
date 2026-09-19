# Draft 092: grounded repository and engineering experience retrieval

Status: draft apparatus only. Execution is prohibited until preregistration 091 passes and this
document is frozen with exact commits and the admission selection SHA-256.

This is a local development experiment. It does not authorize an executable Task Solve cell, an
official AML Smoke or Full run, task routing, or a combined memory view.

## Dependency

The only admissible compiler is the source-grounded anchor compiler v2 from preregistration 091.
Before this protocol can be frozen, its immutable `selection.json` must report all of:

1. `selected_compiler` equal to `V2_anchor_raw`;
2. `admission_pass` equal to true;
3. `authorize_m2_m3_retrieval` equal to true.

The frozen revision will record the exact admission selection path and SHA-256. A failed admission
ends this lane. It does not authorize changing these views or their gates.

## Question

Does isolating source-grounded repository knowledge or source-grounded engineering experience add
useful retrieval signal beyond the same raw session memory, while preserving complete evidence,
source diversity, latency, and bounded returned context?

This is an independent view screen. M2 and M3 are each compared directly with M0. They are not
combined, routed, reranked, packed, or used by a coding agent in this protocol.

## Draft population

Use the committed present condition corpus assembled with seed 0 from the same historical session
manifest used by preregistration 091, and all 34 committed retrieval tasks. Each arm receives the
same session messages in manifest order. Each task is searched three times, for 102 requests per
arm and 306 requests total. Search receives only the committed task prompt, exact `user_id`, and
Top K 100. Fact terms and source labels are used only after Search for scoring.

All three arms reuse one run-specific namespace sequentially. Every arm starts by deleting that
namespace and then performs its own complete dense embedding pass. The raw projection SHA-256 must
be identical across all arms. Full corpus hashes are expected to differ because the typed views
differ.

## Arms

1. `M0_multiview_raw`: raw dense plus exact lexical retrieval. No compiled record is stored.
2. `M2_repository_raw`: M0 plus accepted anchor-v2 records whose exact kind is `architectural
   decision`, `constraint`, or `repository fact`.
3. `M3_experience_raw`: M0 plus accepted anchor-v2 records whose exact kind is `symptom`, `root
   cause`, `failed attempt`, `successful repair`, `procedure`, or `validation`.

M2 and M3 compile the same complete sessions independently and retain the identical raw path.
Records produced by the deterministic compiler fallback are not stored in either typed view because
their whole-session text duplicates raw memory and does not provide a grounded typed distinction.
A provider or compiler fallback therefore leaves the session's raw memory intact.

## Explicit exclusions

This screen excludes code-neighbour expansion, learned sparse retrieval, query facets, task-type
routing, reranking, context packing, graph expansion, post-search instructions, and any combination
of M2 with M3. Those mechanisms would prevent attribution of a measured change to one typed view.

## Draft identity checks

The mechanical selector must refuse:

1. a compiler admission selection that does not explicitly authorize M2 and M3 retrieval;
2. anything other than schema 5 artifacts for the exact three registered variants;
3. task, capture, request, namespace, manifest, query, scoring-label, or served-product drift;
4. a missing independent dense embedding pass for any arm;
5. a raw projection SHA-256 difference among arms;
6. compiled records in M0;
7. a compiled kind outside the exact view taxonomy;
8. any stored compiled record whose profile is not `anchor-v2`;
9. any returned Search item outside raw plus the arm's exact allowed kinds.

## Draft mechanism gates

Each candidate must pass every mechanism gate independently:

1. The preregistration 091 compiler admission dependency passes.
2. Its raw projection SHA-256 equals M0 exactly.
3. All stored compiled records use profile `anchor-v2`.
4. All stored and returned compiled records belong only to the candidate's exact view taxonomy.
5. Whole-session compiler fallback remains below 10 percent for this replay.
6. The typed view appears within the first 10 returned items for all three captures of at least 9
   of 34 tasks.

Nine tasks is the minimum useful activation boundary because it proves the mechanism affects more
than one quarter of the fixed retrieval population. A candidate that cannot reach this boundary
cannot be evaluated as a broad memory view even if a few tasks improve.

## Draft retrieval gates

Each candidate must pass every retrieval gate independently against M0:

1. mean reciprocal rank does not decline;
2. complete coverage at 10 does not decline;
3. complete coverage at 100 does not decline;
4. mean relevant source-session recall does not decline;
5. at least one of mean reciprocal rank or complete coverage at 10 improves strictly;
6. mean returned characters are no more than 1.25 times M0;
7. Search p95 is below 1,000 milliseconds and below two times M0.

Task-level metrics, hit rates, compiler record mix, fallback distribution, Add latency, cost, and
per-kind activation are descriptive. They cannot override a failed gate.

## Mechanical selection and next decision

Run `scripts/recall_multiview_select.py` on exactly one immutable artifact from every arm plus the
immutable compiler admission selection. The selector records SHA-256 for all inputs and evaluates
M2 and M3 independently.

A passing view becomes only a candidate for a new, separately frozen executable Task Solve
preregistration. This selector always writes `authorize_executable_run` as false. At most two views
may proceed, and neither may be combined with the other or with routing until it independently
improves executable Task Solve under that later protocol.

If neither view passes, retain M0 raw and stop this lane. Preserve all artifacts and diagnose the
failed mechanism or retrieval gate without changing thresholds or replaying into an existing path.

## Safety and immutable artifacts

Run only after this document is changed to frozen status in the exact AMB commit supplied to the
wrapper. Use a fresh condition corpus, fresh immutable result directory, exact RE-call and AMB
commits, privacy-safe service logs, and user-scoped systemd. Never print or copy provider keys.
Stop on identity drift, provider authentication failure, a new OOM event, unsafe host state, or a
response that cannot prove request identity.

The expected result root is `results/aml-grounded-multiview-retrieval/<run-id>/` and contains the
three replay JSON files, three service logs, the copied admission selection, `selection.json`,
`identity.json`, and `SHA256SUMS`. No artifact is overwritten, resumed, or repaired in place.

<!-- No run is authorized while this document remains draft. -->
