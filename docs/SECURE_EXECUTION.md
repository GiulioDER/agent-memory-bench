# Secure benchmark execution

Production runs use a native Linux host with rootless Docker. The controller restores a task
fixture in disposable storage, archives only that input, and passes the archive to a participant
container pinned by digest. The participant receives no repository bind mount, no Git history
outside the generated baseline, no oracle, and no controller environment inheritance.

The controller must set `AMB_PARTICIPANT_IMAGE_DIGEST`, `AMB_CHECKER_IMAGE_DIGEST`, and
`AMB_NETWORK_POLICY_DIGEST` before a production run. It also holds the broker signing secret and
issues a fresh short lived model capability, plus an MCP capability for memory arms, for every
participant session. The concrete grants are passed to `run_isolated_claude_case()` and never
stored in the run artifacts. Provider keys remain broker-only configuration. A provider key placed
in either capability variable is rejected.

The participant network is the broker network. Brokers use the trusted allowlist proxy for their
external connections. Checkers use Docker `network=none`, receive validated artifact and oracle
directories as read-only mounts, and start only after the participant container exits.

`run_claude_case()` and `run_checker(..., isolated=False)` remain available for unit fixtures and
reference tests. Production launchers use `run_isolated_claude_case()` and
`run_checker(..., isolated=True)`; missing Docker, a non-rootless daemon, missing image digest,
missing capability, malformed archive, or missing checker infrastructure fails closed.

The provenance fields in `environment.json` and session metadata attest the execution mode,
image and policy digests, archive digests, isolation proof, exit status, and cleanup status. They
do not contain capability values, provider credentials, host paths, or Docker inspect output.
