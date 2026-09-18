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

## Encrypted connections

Every connection to a non loopback destination must use TLS or SSH. Plain HTTP is permitted only
for an explicitly named loopback service. The participant session must not inherit generic proxy
variables such as `HTTP_PROXY`, `HTTPS_PROXY`, or `NO_PROXY`; a connection may use only the
explicit broker endpoint and the controller supplied egress proxy.

The egress proxy is an enforced allowlist, checked by destination host and port. Direct outbound
connections and destinations outside that allowlist fail closed. When an integration uses SSH,
the client must enable strict host key checking and use the pinned `known_hosts` data supplied for
that integration. A changed, missing, or unverified host key is a connection failure.

Each attempted connection must append a connection receipt before the run can be accepted. The
receipt records the session identity, destination host and port, transport, proxy identity, result,
and peer identity. For TLS, peer identity is the SHA 256 fingerprint of the verified certificate.
For SSH, it is the SHA 256 fingerprint of the verified host key. Receipt creation, identity
verification, allowlist enforcement, and transport enforcement are all fail closed. A run without
complete receipts cannot be promoted or used as a benchmark result.

`run_claude_case()` and `run_checker(..., isolated=False)` remain available for unit fixtures and
reference tests. Production launchers use `run_isolated_claude_case()` and
`run_checker(..., isolated=True)`; missing Docker, a non-rootless daemon, missing image digest,
missing capability, malformed archive, or missing checker infrastructure fails closed.

The provenance fields in `environment.json` and session metadata attest the execution mode,
image and policy digests, archive digests, isolation proof, exit status, and cleanup status. They
do not contain capability values, provider credentials, host paths, or Docker inspect output.

## Trusted adjudication receipt

The ordinary verifier proves arithmetic and artifact consistency. A live run also requires a
trusted adjudication receipt. Before sessions start, the controller writes `challenge.json` with a
fresh nonce, the challenge version, runner image digest, participant agent digest, and oracle
version. During execution it writes `execution-events.jsonl`, a controller owned hash chain that
records participant completion, checker completion, oracle isolation, and the admission signal
digest. The participant container cannot write either file.

After `records.final.jsonl`, `admission.json`, `costs.json`, `environment.json`, and `streams/` are
complete, `harness.adjudication` hashes those artifacts and signs
`adjudication.receipt.json` with an Ed25519 key held by the adjudicator. The receipt binds the
challenge nonce, runner and participant digests, oracle version, event log hash, checker outcomes,
admission signals, artifact digests, and timestamps. Reusing a challenge or receipt is refused, and
an external ledger records consumed nonces across run directories. Production refuses to run
without that ledger path.

Generate a key, finalize a completed run, and verify it as follows:

```bash
python -m scripts.adjudicate_run keygen adjudicator.key --public-out adjudicator.pub
python -m scripts.adjudicate_run finalize results/<run-condition> --key-file adjudicator.key
python -m scripts.adjudicate_run verify results/<run-condition> --public-key-file adjudicator.pub
python -m scripts.verify_run results/<run-condition> --adjudicator-public-key-file adjudicator.pub
```

The receipt proves what the trusted controller observed. It does not make an unmeasured local
process trustworthy. Production configuration therefore supplies explicit
`AMB_RUNNER_IMAGE_DIGEST`, `AMB_PARTICIPANT_AGENT_DIGEST`, and
`AMB_ADJUDICATOR_SIGNING_KEY_FILE`, and `AMB_ADJUDICATOR_LEDGER_FILE` values, and the production
launcher refuses to start without them.
