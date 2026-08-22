# Task candidates

24 candidates for a target of 15 or more pilot survivors (the ancestor benchmark lost ~35% to
qualification, ceiling and floor; building the attrition in is measured, not pessimism).

Every task follows one shape. The **prompt** asks for real work and never names the hazard. The
**governing fact** is a project decision or environment gotcha that is arbitrary by
construction: not derivable from the fixture, the CLAUDE.md bundle, or world knowledge, and
established in exactly one precursor session in the corpus. The **naive** solution is the
competent answer of an agent without that fact, and it must fail **silently** in-sandbox (an
error the agent can see lets it self-correct, and the fact stops discriminating). The
**checker** is executable, runs against oracle inputs the sandbox never contained, and a
do-nothing session scores 0. Both reference solutions are committed and CI asserts
naive-fails / informed-passes for every implemented task.

Fixtures are small, purpose-built projects, runnable with the standard library so checkers run
in CI. That is a deliberate trade, stated openly: the realism this benchmark buys is in the
task-plus-experience loop, not in repository scale; repo-scale fixtures are a follow-up axis.

Status: `exemplar` = implemented first as the pattern; `batch-A`/`batch-B` = implementation
batches; `risk:` notes what might kill the candidate at implementation or pilot.

| id | the work asked | governing fact (established in the precursor) | naive failure (silent) | checker |
|---|---|---|---|---|
| `ts-dedup-order` (exemplar) | write `dedupe.py` collapsing `events.jsonl` by `event_id` | duplicates keep the **first** occurrence: the earliest report is authoritative, later ones are enriched-but-wrong re-sends | dict overwrite keeps the last occurrence; output is well-formed and wrong | run produced script on oracle events file, byte-compare output to expected |
| `ts-round-money` (exemplar) | write `invoice.py` totalling line items | money is `Decimal` with **ROUND_HALF_UP** at each line, never float, never banker's rounding | float arithmetic and `round()` (half-even) drift on .5 boundaries | run produced script on oracle items hitting 2.675-style and 2.5-boundary cases, compare totals |
| `ts-nfc-count` (exemplar) | write `count_words.py` over `docs/*.txt` | inputs mix composed and decomposed accents; counts are over **NFC-normalised** text (post-incident decision) | plain counting treats `é` and `e`+combining accent as two words | run on oracle docs with mixed normalisation, compare counts |
| `ts-mig-name` (batch-A) | add a migration creating an index on `users.email` | migration filenames are truncated to **30 chars** by `scripts/new_migration.py` because the staging DB rejects longer identifiers | a descriptive long filename works locally, dies only in staging | oracle "staging loader" validates filename length and the SQL body |
| `ts-crlf-export` (batch-A) | add a field to the export and regenerate `export.csv` | the downstream consumer requires **CRLF** line endings (incident: a LF export was silently dropped) | python text-mode write emits LF | oracle reader asserts CRLF bytes and the new field |
| `ts-base36-id` (batch-A) | write `gen_id.py` producing the next order id | order ids are base36 uppercase over a **restricted alphabet without 0/O/1/I** (support-call incident) | sequential integer or full base36 id | oracle validator checks alphabet and successor value |
| `ts-stable-sort` (batch-A) | generate the monthly report from `data/*.csv` | report rows sort by **(date, id)**, because date-only ties churn the downstream diff | date-only sort is stable-looking and nondeterministic across input order | byte-compare against oracle expected report |
| `ts-legacy-hash` (batch-A) | add response caching to `fetch.py` | `fast_hash()` collides for keys longer than 8 chars; caching must key on `hash_key()` (the README still recommends `fast_hash`) | `fast_hash` works on every short key the fixture shows | oracle drives produced cache with two colliding long keys, asserts distinct entries |
| `ts-tz-utc` (batch-A) | write `rotate.py` archiving logs older than 7 days | log timestamps are **UTC** despite having no suffix (post-DST-incident decision) | local-time parsing misfiles entries near the boundary | oracle log set spanning a DST change, compare archived set |
| `ts-golden-regen` (batch-A) | make the formatter emit a trailing newline and get tests green | `tests/golden/*.out` are regenerated only via `scripts/regen_golden.py`, which appends a checksum footer | hand-editing the goldens passes the visible tests | oracle validates checksum footers and the formatter change |
| `ts-config-layer` (batch-A) | add setting `max_retries` (default 3), overridable | precedence is **env over `config.local.ini` over `config.ini`** (decided; the fixture shows no local file) | reading only `config.ini` | oracle harness sets env and local overrides, asserts effective value |
| `ts-quote-shell` (batch-A) | extend `deploy.sh` to also copy the assets directory | every path in deploy scripts is quoted: prod hosts have **spaces in directory names** | unquoted `$VAR` paths pass on the fixture's clean paths | run script against an oracle tree containing a spaced path |
| `ts-bom-merge` (batch-A) | write `merge.py` combining `data/*.csv` into `all.csv` | partner CSVs may carry a **UTF-8 BOM**; the first header cell must be BOM-stripped (Excel incident) | naive read leaves `﻿id` as a column name; join silently drops rows | oracle includes a BOM file, compare merged output |
| `ts-atomic-write` (batch-B) | add `save()` to `store.py` | state writes are **atomic**: temp file in the same dir, then rename (corruption incident) | direct `open(target, "w")` works every time in-sandbox | oracle harness monkeypatches io/os to record the call pattern and asserts write-then-rename with no direct truncation |
| `ts-first-dedup-keep-order` is folded into `ts-dedup-order` | | | | |
| `ts-schema-additive` (batch-B) | add a `priority` field to the task schema and validator | schema evolution is **additive**: new fields optional with a default, never required (old clients) | marking the field required validates every new record | oracle validates an old-format record against the produced schema |
| `ts-log-mask` (batch-B) | add request logging to `api.py` | the `token` field is never logged; mask to **last 4** (compliance decision) | logging the whole request payload | oracle drives a request with a known token, greps the produced log |
| `ts-casefold-sort` (batch-B) | write `roster.py` printing attendees sorted | name ordering is **casefold, accent-insensitive** (incident: lowercase names sorted after Z) | default `sorted()` is codepoint order | compare output on oracle roster with mixed case and accents |
| `ts-glob-hidden` (batch-B) | write `backup.py` copying the project dir to `backups/` | backups must include **dotfiles** (incident: `.env.production` was missed) | `glob('*')` and bare `iterdir` filters skip them | oracle tree contains a dotfile, assert it lands in the backup |
| `ts-manifest-rel` (batch-B) | write the release manifest generator | manifest paths are **relative to the repo root, POSIX-slashed**, regardless of how the tree is walked | absolute paths from `os.walk` are well-formed and wrong | oracle validates every path key |
| `ts-append-only` (batch-B) | append today's metrics entry to `metrics.log` | the metrics file is **append-only**; rewriting or normalising past lines is forbidden (audit trail) | "tidying" the file while adding the entry | assert the prior content is a byte-identical prefix, entry appended |
| `ts-semver-pin` (batch-B) | add dependency `textutils` to the requirements | internal packages are pinned **exactly** (`==`), never ranged, after a breakage | `>=` is the ecosystem default | parse produced requirements for the pin |
| `ts-ignore-gen` (batch-B) | ignore the new `dist2/` build output | `.gitignore` is maintained only via `scripts/update_ignore.py` (sorted, deduped, headered) | hand-appending an unsorted line | validate header, ordering, and the entry |
| `ts-empty-input` (batch-B) | run the weekly report over `inbox/` | on an empty inbox the report must **exit 0 and write the "no data" marker** (ops decision: red pages) | naive code crashes on the empty case, which the fixture never shows | oracle runs the produced report on an empty inbox |
| `ts-retry-cap` (batch-B) | add retry to `client.py` | retries use exponential backoff **capped at 30s with jitter**, never a fixed sleep (thundering-herd incident) | fixed `sleep(1)` loops pass every fixture path | oracle drives produced code with a fake clock, asserts cap and non-constant delays. risk: checker complexity |

## Risks flagged at design time

- `ts-atomic-write` and `ts-retry-cap` carry the two hardest checkers; if implementation makes
  them brittle they are the first cuts (24 candidates exist so that cutting is cheap).
- `ts-semver-pin` and `ts-ignore-gen` have the weakest silent-failure property (the checker is
  close to a style check); pilot screening decides.
- Ceiling risk concentrates in `ts-empty-input` and `ts-glob-hidden`, where a defensive-minded
  model may do the right thing from priors; the `bare` floor check at the pilot decides.

## Implementation status, 2026-08-22

All 24 candidates implemented, none dropped; 72 discrimination assertions green in CI
(do-nothing fails, naive fails silently, informed passes, for every task). Deviations from
the table, each stated in the task's checker docstring: ts-stable-sort compares parsed row
order rather than bytes; ts-tz-utc uses a fixed-offset boundary set rather than a DST span;
ts-glob-hidden's naive uses glob.glob (pathlib's glob matches dotfiles); ts-retry-cap's
prompt pins an injectable structure so the cap region is reachable. Exemplar precursor
sessions are recorded for the three exemplar tasks; the remaining precursor stagings are the
next work item.
