# VOID: 8 sessions run with the MCP server dead for a second reason

The first void run (`-VOID-dead-mcp-server`) was the wrong interpreter. This one is what was
underneath it: the pinned venv had `recall-rag[fastembed]` but not the `mcp` extra, so the server
died at import.

    ModuleNotFoundError: No module named 'mcp'

Same signature as before, and that is the point: `error` null, ordinary turn counts,
`memory_call_count = 0` on every recall cell. Two different causes, one indistinguishable record.

Do not analyse these. `harness/mcp_probe.py` now refuses a run whose server does not answer.
