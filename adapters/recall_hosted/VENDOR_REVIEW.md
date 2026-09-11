# RE-call Hosted 1.0 adapter review

This adapter uses the product's public synchronous Add and Search endpoints. It does not import
RE-call internals. Corpus transcripts are sent as ordered messages with their timestamps and tool
evidence preserved. The benchmark namespace is the exact hosted `user_id`; the transcript path is
the exact `session_id` used to join retrieval results to the gold corpus.

The generated MCP bridge exposes one read-only `recall_search` tool to the coding agent. Its only
job is transport conversion between MCP over stdio and the frozen hosted HTTPS Search contract.
