Graphiti exposes two read searches. Use `mcp__graphiti__search_memory_facts` for relationships and
facts, and `mcp__graphiti__search_nodes` for entities. Results are JSON under `facts` or `nodes` and
are scoped by the benchmark's graph group. Use `get_episodes` or `get_episode_entities` when the
source episode or provenance of a result matters.
