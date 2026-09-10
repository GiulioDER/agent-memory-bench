# Data safety boundary

The default challenge corpus is synthetic only. It is authored or generated for this repository,
and its declaration is checked by `python -m scripts.audit_data_safety`. That audit rejects a
manifest member that is missing, a credential shaped value, or a contact address outside the
reserved example domains. It cannot prove that an author has never copied proprietary material,
so the tracked declaration and human review remain required.

## What a participant can reach

Each participant gets one disposable workspace archive and a credentialless configuration. It does
not receive the repository, the corpus directory, an oracle, Git history, host mounts, a Docker
socket, or a provider credential. Its network is an internal broker network. The egress proxy is
reachable only by trusted brokers, accepts only the configured provider hostnames, and permits TLS
CONNECT only on port 443. The memory relay uses an explicit nonempty read allowlist. An empty
allowlist denies every memory tool call.

The model provider necessarily sees the task prompt and any memory result needed to answer it.
Therefore the enforceable claim is that a participant cannot send data to an arbitrary destination
or obtain a provider credential. The provider handling requirement below is what makes the required
hosted processing acceptable for the synthetic challenge corpus. This is not a claim that a model
provider cannot observe a request while serving it.

## Hosted provider requirement

Every live runner requires `AMB_DATA_POLICY_FILE`. The file is an operator supplied attestation
with schema version 1. It must declare `synthetic-only` data, zero retention, no training, and no
reuse, and it must name every hosted provider used by the model or an adapter. Start from
`docs/provider-policy.example.json`, replace the provider names and policy references, and keep the
completed file outside the repository if it contains operational details.

The runner records only the policy digest and its nonsecret declarations in `environment.json`.
The digest binds the run to the reviewed declaration, but it does not turn an operator attestation
into an independent audit of a vendor contract.

## Publication boundary

Raw streams and in progress records are stored under the external disposable work root. A result
directory receives public receipts only. A receipt preserves task and arm identity, outcome,
bounded counts, costs, timing, tool names, and digests of omitted text. It does not contain the
prompt, response, tool arguments, tool outputs, references, retrieved context, hook payload, raw
error, or host path. The writer rejects a receipt if one of those fields reappears.

The detached launcher writes its operational log outside the repository as well. This means a
publication cannot accidentally include a raw transcript by adding the result directory. If a
future release chooses to publish a log, it must pass through `harness.privacy.redact_log_text`
and a human review.

Run the local checks before a challenge release:

```text
python -m scripts.audit_data_safety
python -m pytest tests/test_privacy.py tests/test_isolation.py -q
```
