# Official run audit: official-003

Status: **warn**.

| check | status | detail |
|---|---|---|
| `config_points_to_run` | **pass** | official_run='official-003' |
| `summary_run_id` | **pass** | summary run id='official-003' |
| `condition_artifacts` | **pass** | all required artifacts exist |
| `condition_rosters` | **pass** | required arms=('bare', 'placebo', 'claude_md', 'protocol', 'fs_grep', 'recall', 'mempalace', 'recall_prefetch') |
| `admitted_cell_integrity` | **pass** | one admitted record per arm and cell |
| `admission_rederives` | **pass** | admitted cells match the discarded set |
| `summary_matches_records` | **pass** | headline and condition counts rederive from records |
| `summary_matches_costs` | **pass** | published token totals match ledgers |
| `summary_matches_admission` | **pass** | discard counts match admission ledgers |
| `published_token_rate_denominator` | **warn** | recall: published 66337, observed-session rate 64133; mempalace: published 104451, observed-session rate 103649; fs_grep: published 43766, observed-session rate 45100; placebo: published 19189, observed-session rate 19218; claude_md: published 17954, observed-session rate 18328; bare: published 18457, observed-session rate 18939 |
| `preregistration_timing` | **warn** | the preregistration discloses that it was registered mid run |
| `write_path_scope` | **warn** | the leaderboard measures retrieval over a bulk-ingested corpus; write path is not measured |
| `replication_depth` | **warn** | one session per cell; uncertainty excludes run to run variance |

## Source artifacts

Summary: `results/official-003/leaderboard_summary.json`

Summary SHA256: `ac6f090bd6960146ad7a40abe44b94a607856eb80100daea6b1f2e6086c00c3c`

1. `results/official-003-present`
1. `results/official-003-absent`
1. `results/official-003-superseded`
1. `results/official-003-contradictory`
1. `results/official-003-adjacent`
