# 016: Recall table isolation amendment

Status: FROZEN before the amended Recall smoke measurement.

## Reason for amendment

The pinned Recall package is `recall-rag[fastembed,mcp]==0.10.0`, while the existing remote benchmark host
`amb_bench` database has a newer global migration ledger than that package understands. A fresh
database could not be created by the benchmark user. Running the pinned comparison against the
public `chunks` table would therefore either refuse at startup or risk touching data outside this
benchmark.

## Amended treatment

The Recall arm keeps its published CLI index command and published stdio MCP server. The remote benchmark host provides
`PGOPTIONS=-c search_path=<dedicated schema>,public`, with a dedicated schema and a fresh
`chunks` table initialized by the pinned package. This isolates the benchmark rows and the pinned
package's migration ledger from the live public table. The schema name, search path, package pin,
tenant, and row counts are recorded in the run environment and ingest artifacts.

No Recall code or public table is upgraded. The Supermemory amendment in preregistration 015 is
independent and remains labeled separately.

## Prediction and gates

Before the amended smoke measurement, I predict that the pinned Recall CLI will initialize and
populate the isolated table, the Recall MCP server will answer at least one search for the offered
transcript, both required hooks will pass admission, and the canonical smoke will remain under
600 seconds with a full-run projection under 18,000 seconds.

The amended smoke must satisfy every existing smoke and admission gate before the full benchmark.
If it fails, the Recall lane is reported as an infrastructure qualification failure and no Recall
score is pooled with other treatments.

<!-- results are appended below this line -->
