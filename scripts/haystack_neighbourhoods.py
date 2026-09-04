"""Semantic neighbourhoods, one per task: the second-generation hard negative.

Why this file exists, in one measurement
-----------------------------------------

`preregistration/015-corpus-scale-retrieval-difficulty.md` measured two rankers over the same
corpora. Near-misses built from a task's own prompt WORDS cost BM25 thirty points of `hit@1` and
`voyage-4` only six, and supplied 72.5% of BM25's competitors against 33.0% of Voyage's. An
embedder is not much fooled by borrowed vocabulary.

The tier that hurt `voyage-4` most was `topical`, which shares **no** query terms at all and
merely sits in the same subject area: 123 competitors from 936 documents, its largest single
source, while costing BM25 literally zero. That is the signal this file acts on. The second
generation hard negative is built the other way round: **same meaning neighbourhood,
deliberately different words.**

Three rules hold every entry
-----------------------------

1. **No term appears in its own task's prompt.** A term that does is lexical overlap wearing a
   semantic label, and would make this tier a slower copy of the other one. Enforced by
   `tests/test_haystack_and_retrieval.py`, not trusted.
2. **Nothing states any task's ``fact_terms``.** The same containment rule as the rest of the
   corpus, checked on every emitted file by the generator.
3. **The decision sits on an ORTHOGONAL axis**, and concerns the generated repository's own
   artefacts.

Rule 3 is the one that took the most care and it is the one with teeth. A document that is
semantically adjacent **and** answers the task's question in the wrong direction is not a hard
negative, it is a `contradictory` plant: a different experiment, with a different
preregistration, that would corrupt task-success runs rather than test retrieval. So every entry
below settles a neighbouring question the task does not ask. Retention rather than mutation.
Permissions rather than durability. Allocation rather than alphabet. Locale rather than
timezone.

Why these were authored rather than mined
------------------------------------------

Mining hard negatives with the embedder itself is the standard technique and was rejected here.
Selecting the documents `voyage-4` ranks closest and then scoring difficulty with `voyage-4`
measures the selection, not the corpus, and the corpus would stop being hard the moment anybody
changed embedder. Authored neighbourhoods are model-independent: they are a claim about meaning
that any retriever can be tested against, including ones that do not exist yet.
"""

from __future__ import annotations

NEIGHBOURHOODS: dict[str, dict[str, object]] = {
    "ts-append-only": {
        "subject": "how long the nightly tally file is kept before it is archived",
        "terms": (
            "ledger", "chronological", "retention", "archive", "rollup", "quarter",
            "historical", "journal",
        ),
        "decision": (
            "the tally is kept for four quarters and then moved into the archive directory "
            "under its quarter name"
        ),
    },
    "ts-atomic-write": {
        "subject": "what permissions the saved state gets and who may read it",
        "terms": (
            "permissions", "umask", "ownership", "group", "readable", "filesystem", "mount",
            "quota",
        ),
        "decision": (
            "state is created readable by the service group only, and the mount it lives on "
            "carries its own quota"
        ),
    },
    "ts-base36-id": {
        "subject": "how customer references are allocated and how long an unused one stays "
                   "reserved",
        "terms": (
            "allocation", "reserved", "sequence", "counter", "namespace", "reuse",
            "exhaustion", "block",
        ),
        "decision": (
            "references are allocated in blocks of fifty, and an unused one returns to the "
            "pool after thirty days"
        ),
    },
    "ts-bom-merge": {
        "subject": "which decimal separator and grouping the finance extracts use",
        "terms": (
            "decimal", "separator", "locale", "grouping", "workbook", "semicolon", "currency",
            "thousands",
        ),
        "decision": (
            "a full stop for the decimal, no thousands grouping, and a semicolon between "
            "fields for the workbook the finance team opens"
        ),
    },
    "ts-bool-env": {
        "subject": "who may change a feature toggle and how the change is recorded",
        "terms": (
            "toggle", "rollout", "owner", "approval", "staged", "audience", "revert", "record",
        ),
        "decision": (
            "a toggle change needs the owner approval and one line in the change record, and a "
            "staged rollout is reverted the same way"
        ),
    },
    "ts-casefold-sort": {
        "subject": "how member records are matched when two spellings of a person arrive",
        "terms": (
            "matching", "transliteration", "nickname", "initials", "surname", "given",
            "register", "reconciliation",
        ),
        "decision": (
            "records are matched on the whole string after trimming, never on initials and "
            "never on a nickname"
        ),
    },
    "ts-cli-exitcode": {
        "subject": "where the validation summary is delivered and who reads it",
        "terms": (
            "notification", "recipient", "digest", "dashboard", "escalation", "rota",
            "subscription", "channel",
        ),
        "decision": (
            "the summary goes to the team channel each morning, with no dashboard and no "
            "escalation to the rota"
        ),
    },
    "ts-config-layer": {
        "subject": "which options are safe to change without a deploy",
        "terms": (
            "tunable", "restart", "promotion", "credential", "reload", "ownership", "audience",
            "inventory",
        ),
        "decision": (
            "a tunable may change without a restart, a credential never may, and promotion "
            "between the two needs the owner"
        ),
    },
    "ts-crlf-export": {
        "subject": "who consumes the outbound extract and on what schedule",
        "terms": (
            "consumer", "schedule", "nightly", "handoff", "downstream", "cadence",
            "acknowledgement", "window",
        ),
        "decision": (
            "the extract is handed off at 02:00 nightly and the downstream consumer "
            "acknowledges inside a two hour window"
        ),
    },
    "ts-csv-quote": {
        "subject": "how long a remark may be and what is stripped from it before storage",
        "terms": (
            "remark", "truncation", "limit", "trimming", "sanitised", "storage", "width",
            "moderation",
        ),
        "decision": (
            "a remark is limited to 500 characters and trimmed at both ends; anything longer "
            "goes to moderation rather than to storage"
        ),
    },
    "ts-dedup-order": {
        "subject": "how long a record stays in the stream before it is expired",
        "terms": (
            "retention", "expiry", "stream", "replay", "backlog", "window", "compaction",
            "lifetime",
        ),
        "decision": (
            "a record has a fourteen day lifetime in the stream and is compacted away after "
            "that, with replay served from the backlog"
        ),
    },
    "ts-empty-input": {
        "subject": "which units the readings are recorded in and how they are converted",
        "terms": (
            "unit", "conversion", "calibration", "precision", "instrument", "scale", "reading",
            "tolerance",
        ),
        "decision": (
            "a reading is stored in the unit its instrument reports, converted only for "
            "display, with the calibration scale kept beside it"
        ),
    },
    "ts-glob-hidden": {
        "subject": "where the offsite snapshots are stored and how long they are kept",
        "terms": (
            "offsite", "retention", "restore", "rotation", "storage", "encryption",
            "verification", "snapshot",
        ),
        "decision": (
            "a snapshot goes offsite nightly, encrypted, is kept thirty days, and one restore "
            "is verified each month"
        ),
    },
    "ts-golden-regen": {
        "subject": "who reviews an amendment to the expected outputs before it lands",
        "terms": (
            "reviewer", "approval", "ownership", "checklist", "branch", "merge", "gate",
            "sign",
        ),
        "decision": (
            "an amendment to the expected outputs needs a second reviewer and passes the same "
            "merge gate as everything else"
        ),
    },
    "ts-idempotent-run": {
        "subject": "how a failed rollout is reversed and who decides",
        "terms": (
            "rollback", "incident", "freeze", "approval", "revert", "owner", "window",
            "decision",
        ),
        "decision": (
            "a rollback is the standby engineer decision and does not wait for the owner, even "
            "inside a change freeze"
        ),
    },
    "ts-ignore-gen": {
        "subject": "who owns the pipeline configuration and where its outputs go",
        "terms": (
            "ownership", "artefact", "workspace", "cache", "cleanup", "pipeline", "stage",
            "publish",
        ),
        "decision": (
            "pipeline artefacts land in a workspace owned by the platform group and are "
            "cleaned up after any stage that does not publish"
        ),
    },
    "ts-json-sorted": {
        "subject": "how the exported document is versioned and where old versions live",
        "terms": (
            "revision", "snapshot", "history", "archive", "publication", "retention",
            "supersede", "label",
        ),
        "decision": (
            "each publication is snapshotted under its own label, and the previous revision is "
            "retained until the next one supersedes it"
        ),
    },
    "ts-legacy-hash": {
        "subject": "how long a stored answer stays valid and when it is evicted",
        "terms": (
            "expiry", "eviction", "staleness", "invalidation", "capacity", "warmup",
            "lifetime", "pressure",
        ),
        "decision": (
            "a stored answer has a six hour lifetime, the store is capped at five thousand, "
            "and eviction under capacity pressure takes the oldest"
        ),
    },
    "ts-log-mask": {
        "subject": "how long the access records are kept and who may read them",
        "terms": (
            "retention", "access", "rotation", "archival", "permission", "reviewer",
            "compression", "custody",
        ),
        "decision": (
            "access records rotate daily, are retained ninety days compressed, and only the "
            "platform group has permission to read them"
        ),
    },
    "ts-manifest-rel": {
        "subject": "how a shipment is named and what belongs in it",
        "terms": (
            "naming", "shipment", "tag", "bundle", "inclusion", "exclusion", "packaging",
            "contents",
        ),
        "decision": (
            "a shipment is named for the date it was cut, and its contents are whatever the "
            "packaging stage included at that moment"
        ),
    },
    "ts-mig-name": {
        "subject": "who reviews a schema change and when it may be run",
        "terms": (
            "review", "approval", "rehearsal", "downtime", "coordination", "freeze", "window",
            "sequence",
        ),
        "decision": (
            "a schema change runs in the Tuesday window after a rehearsal, and needs one "
            "approval from whoever owns the affected area"
        ),
    },
    "ts-natural-order": {
        "subject": "who receives the daily digest and in what format",
        "terms": (
            "recipient", "digest", "distribution", "subscription", "format", "delivery",
            "mailing", "cadence",
        ),
        "decision": (
            "the digest is delivered at 07:00 as plain text to the mailing list, and "
            "subscription is opt in"
        ),
    },
    "ts-nfc-count": {
        "subject": "which documents are in scope for the terminology review",
        "terms": (
            "terminology", "scope", "review", "inclusion", "language", "translation", "editor",
            "style",
        ),
        "decision": (
            "the terminology review covers the handbook and the published guides, and nothing "
            "that is still a draft"
        ),
    },
    "ts-quote-shell": {
        "subject": "which host the staging script runs on and with what privileges",
        "terms": (
            "privilege", "host", "account", "runner", "credentials", "hardening", "isolation",
            "elevation",
        ),
        "decision": (
            "the script runs on the shared runner under the service account, with no elevation "
            "and no credentials in its environment"
        ),
    },
    "ts-retry-cap": {
        "subject": "which upstream failures are worth reporting and to whom",
        "terms": (
            "upstream", "classification", "severity", "reporting", "incident", "threshold",
            "alert", "ownership",
        ),
        "decision": (
            "an upstream failure that clears by itself is recorded at low severity and not "
            "reported; anything over the threshold opens an incident"
        ),
    },
    "ts-round-money": {
        "subject": "which currency the statements are issued in and how exchange rates are "
                   "fixed",
        "terms": (
            "currency", "exchange", "issuance", "tax", "jurisdiction", "billing", "statement",
            "rate",
        ),
        "decision": (
            "statements are issued in euro at the exchange rate fixed on the first of the "
            "month, whatever the jurisdiction of the account"
        ),
    },
    "ts-schema-additive": {
        "subject": "who owns each work queue and how items are routed to it",
        "terms": (
            "routing", "queue", "ownership", "assignment", "triage", "workload", "capacity",
            "escalation",
        ),
        "decision": (
            "an item is routed to a queue by its owner during triage and never by whoever "
            "raised it, whatever the workload"
        ),
    },
    "ts-semver-pin": {
        "subject": "how a dependency is chosen and who approves adding one",
        "terms": (
            "dependency", "approval", "licence", "vendor", "inventory", "supplier",
            "procurement", "review",
        ),
        "decision": (
            "a new dependency needs a licence review and one approver, and the vendor goes "
            "into the supplier inventory"
        ),
    },
    "ts-stable-sort": {
        "subject": "which periods the consolidated figures cover and when a period is closed",
        "terms": (
            "period", "closing", "cutoff", "reconciliation", "adjustment", "accrual",
            "restatement", "ledger",
        ),
        "decision": (
            "a period closes on the fifth working day after its cutoff and is not reopened; a "
            "later correction becomes an adjustment in the next one"
        ),
    },
    "ts-tz-utc": {
        "subject": "which locale the operator interface displays dates in",
        "terms": (
            "locale", "display", "presentation", "calendar", "weekday", "language", "region",
            "interface",
        ),
        "decision": (
            "the operator interface presents dates in the locale of whoever is looking, and "
            "stores nothing about the region they chose"
        ),
    },
    "xs-evolve-lease": {
        "subject": "how a stalled consumer is detected and what happens to its items",
        "terms": (
            "stall", "detection", "reassignment", "orphan", "supervisor", "takeover", "health",
            "quarantine",
        ),
        "decision": (
            "a consumer that stops reporting health has its items reassigned by the "
            "supervisor, and the orphan is quarantined rather than restarted"
        ),
    },
    "xs-join-batch": {
        "subject": "how a downstream outage is handled and how long items wait",
        "terms": (
            "outage", "backlog", "queueing", "resumption", "throttling", "contract",
            "availability", "degradation",
        ),
        "decision": (
            "items wait in the backlog for the length of an outage and resume when "
            "availability returns, with throttling on the way back up"
        ),
    },
    "xs-widen-manifest": {
        "subject": "who signs off a handover and where the signature is kept",
        "terms": (
            "signature", "handover", "custody", "approval", "countersign", "recipient",
            "evidence", "retention",
        ),
        "decision": (
            "a handover is countersigned by the recipient, and the signature is filed with the "
            "custody evidence for seven years"
        ),
    },
}
