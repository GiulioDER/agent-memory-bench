# Partial abstention-002 runs, kept as evidence

Three launches were aborted before the run that produced the reported result. All are kept.

| directory | why it is void |
|---|---|
| `abstention-002-absent-VOID-dead-mcp-server` | 14 sessions; MCP server started on the wrong interpreter and refused the corpus (`SchemaTooNew: unknown migration(s) ['0015']`) |
| `abstention-002-absent-VOID-missing-mcp-extra` | 8 sessions; pinned venv lacked the `mcp` extra, server died at import |
| `abstention-002-absent-PARTIAL-dirty-work-root` | 30 cells attempted, 22 admitted; the 8 discards were sandboxes surviving from the two runs above, not session failures |
| `abstention-002-superseded-PARTIAL-dirty-work-root` | 20 of 90 sessions when the run was stopped to restart cleanly |

The first two are measurements of an arm that could not retrieve. The third and fourth are valid
sessions, but the run was restarted so that all four conditions share one provenance rather than
one condition carrying a 27% self-inflicted discard rate.

Nothing here is analysed. `harness/mcp_probe.py` and `pilot._refuse_a_dirty_work_root` are the two
mechanisms that stop each cause recurring.
