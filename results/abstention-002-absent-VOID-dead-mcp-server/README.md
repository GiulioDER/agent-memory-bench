# VOID: 14 sessions run with a dead recall MCP server

Kept rather than deleted, because it is the evidence for the defect and for what the failure looks
like from inside a record.

These sessions ran on 2026-08-29 before `abstention-002` was stopped. The `recall` arm had no
memory tools at all: the ingest wrote through the pinned `recall-rag==0.10.0`, which applied schema
migration 0015, while the MCP server started on a PATH `python` holding an editable install of a
development worktree, which refused the corpus outright:

    SchemaTooNew: table 'chunks' has unknown migration(s) ['0015']; upgrade the application

**Nothing in the records says so.** `error` is null in all fourteen, the turn counts are ordinary,
and the arm simply records `memory_call_count = 0`, which is exactly what an agent that chose not
to search would record. The search rate is the only thing that gave it away, on 4 of 4 recall
cells.

Do not analyse these. They are not a measurement of the recall arm; they are a measurement of an
arm that could not retrieve. The fix is `RecallAdapter._server_command`, and
`tests/test_adapters.py::test_the_mcp_server_runs_the_same_interpreter_the_ingest_ran` is what
stops it recurring.
