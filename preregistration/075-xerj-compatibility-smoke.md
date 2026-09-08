# XERJ compatibility smoke

Status: DRAFT until committed and timestamped. This is an integration preflight, not a
leaderboard result.

## Question

Can the XERJ release binary or a source build with a generic x86_64 target run a local node,
accept the documented memory API calls, and serve the documented MCP memory tools on this host?

## Frozen setup

The vendor source is pinned to the exact commit reviewed for this smoke. The released Windows
asset is pinned by its release tag and SHA256. The host CPU is recorded before execution. If the
released asset cannot execute because its x86_64 baseline is newer than this host, a source build
may be attempted with `RUSTFLAGS=-C target-cpu=x86-64`; that fallback is feasibility evidence only
and is not the vendor release binary.

The smoke uses one fresh local data directory and loopback HTTP only. It starts XERJ with
`--insecure`, waits for cluster health, stores one memory in a dedicated namespace, recalls it
through the REST API, starts the shipped `xerj mcp` stdio server, completes MCP initialize and
tools/list, and calls `xerj_memory_recall`. It then stops every process and checks the namespace
does not cross into a second dedicated namespace.

## Prediction

The pinned release binary will fail on this host if the documented x86_64-v3 requirement is real.
A generic source build, if compilation completes, will start the node and pass the REST and MCP
smoke without an external embedding key. The namespace isolation check will pass as a data path
check, while the product will not provide per-namespace credential authorization.

## Stop and publication rules

Stop before any benchmark model call if the node cannot start, health does not become ready, a
store or recall call fails, the MCP server does not expose both memory tools, or cleanup is not
clean. A passing source build does not authorize an official run on this host. An official run
requires the pinned released asset on a compatible runner, a reviewed adapter and frozen config,
an additive preregistration, and a committed setup record before model spend.

<!-- results are appended below this line; everything above is frozen -->
