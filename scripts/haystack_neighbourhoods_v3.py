"""Third-generation neighbourhoods: same REGISTER as the task prompts, orthogonal axis.

What the second generation got wrong, measured
-----------------------------------------------

`preregistration/016-semantic-hard-negatives.md`. The v2 neighbourhoods in
`scripts/haystack_neighbourhoods.py` obeyed two rules: no word shared with the task's prompt, and
a decision on an axis the task does not ask about. Both were necessary. Together they moved the
documents out of the neighbourhood entirely, because what was left was **business-process prose**
(retention windows, approval workflows, currency and jurisdiction) against task prompts that are
**technical-convention prose about files**.

Competitor yield per document against `voyage-4` on the 25x corpus, where above 1.0 means a tier
is pulling its weight:

| tier | share of corpus | share of competitors | concentration |
|---|---:|---:|---:|
| `near_miss`, from prompt WORDS | 9.6% | 33.3% | 3.47x |
| `topical`, generic convention prose | 14.4% | 27.4% | 1.90x |
| `semantic` v2, authored neighbourhoods | 14.4% | 8.3% | **0.57x** |

Generic `topical` beat bespoke `semantic` by 3.3x per document while knowing nothing about any
task, because it is written in the same register: encodings, ordering, configuration, logs,
retries, paths. **Semantic adjacency for an embedder is dominated by register and genre, not by
which artefact a document is about.** Two documents can concern the same file and sit far apart
in embedding space if one is a technical decision and the other is a policy decision.

What this generation changes, and what it keeps
------------------------------------------------

Kept: rule 1 (no word from the task's own prompt, enforced) and rule 3 (the decision sits on an
axis the task does not legislate, which is what keeps a hard negative from becoming a
`contradictory` plant that would corrupt task-success runs).

Changed: the register. Every entry below is a technical decision about a file, a format, a field
or a path, of the same kind a task prompt is about. For `ts-crlf-export` that is the order the
columns are written in, not who consumes the extract and on what schedule.

⚠️ One hazard rule 3 does not cover and no test can. A neighbourhood must not drift onto ANOTHER
task's governing fact: writing about key ordering near `ts-atomic-write` would land on
`ts-json-sorted`'s convention. The fact-term check catches the phrase and cannot catch the
meaning, so the axes below are chosen to sit away from every task's subject, not only from their
own task's.
"""

from __future__ import annotations

NEIGHBOURHOODS_V3: dict[str, dict[str, object]] = {
    "ts-append-only": {
        "subject": "the column order inside each record and what separates the fields",
        "terms": (
            "column", "separator", "delimiter", "alignment", "padding", "token", "field",
            "spacing",
        ),
        "decision": (
            "fields are separated by a single space in a fixed column order, and a value is "
            "never padded to align with the value above it"
        ),
    },
    "ts-atomic-write": {
        "subject": "how the persisted file is named and where it sits beside the module writing it",
        "terms": (
            "naming", "extension", "sibling", "directory", "module", "prefix", "location",
            "layout",
        ),
        "decision": (
            "the persisted file keeps the module name with a different extension and sits in "
            "the same directory as the module, never in a subdirectory of its own"
        ),
    },
    "ts-base36-id": {
        "subject": "how wide the counted part of a reference is and how it is padded",
        "terms": (
            "width", "padding", "zero", "digits", "monotonic", "increment", "casing",
            "truncation",
        ),
        "decision": (
            "the counted part is six digits, zero padded on the left, and widens rather than "
            "truncating when it overflows"
        ),
    },
    "ts-bom-merge": {
        "subject": "how large a combined output may grow before it is split into parts",
        "terms": (
            "size", "threshold", "split", "partition", "megabyte", "chunking", "shard", "part",
        ),
        "decision": (
            "a combined output is split into numbered parts once it passes fifty megabytes, and "
            "each part repeats the same leading row"
        ),
    },
    "ts-bool-env": {
        "subject": "how the settings file is laid out: headings, comments and blank lines",
        "terms": (
            "heading", "comment", "blank", "indentation", "casing", "duplicate", "ordering",
            "layout",
        ),
        "decision": (
            "headings are lowercase, a comment sits above what it describes rather than beside "
            "it, and one blank line separates blocks"
        ),
    },
    "ts-casefold-sort": {
        "subject": "how a display label is built from the parts of a person record",
        "terms": (
            "label", "display", "initials", "surname", "given", "abbreviation", "rendering",
            "template",
        ),
        "decision": (
            "a display label renders as given then surname with a single space, and an "
            "abbreviation is never substituted for a part that is present"
        ),
    },
    "ts-cli-exitcode": {
        "subject": "what a tool writes to standard error as against standard output",
        "terms": (
            "stderr", "stream", "diagnostic", "prefix", "verbosity", "quiet", "progress",
            "redirect",
        ),
        "decision": (
            "diagnostics go to the error stream with a fixed prefix and the result stream "
            "carries only the result, so a redirect captures one without the other"
        ),
    },
    "ts-config-layer": {
        "subject": "which units a duration or size option is expressed in and how it is parsed",
        "terms": (
            "duration", "unit", "milliseconds", "suffix", "parsing", "coercion", "bound",
            "magnitude",
        ),
        "decision": (
            "a duration option carries an explicit unit suffix and is parsed to milliseconds, "
            "and a bare number is refused rather than assumed to be seconds"
        ),
    },
    "ts-crlf-export": {
        "subject": "the order values appear in a written record and what an absent value looks like",
        "terms": (
            "ordering", "absent", "blank", "placeholder", "null", "layout", "position",
            "trailing",
        ),
        "decision": (
            "values appear in the order the schema declares and an absent one is left blank "
            "rather than filled with a placeholder word"
        ),
    },
    "ts-csv-quote": {
        "subject": "which encoding the exported table is written in and how it is declared",
        "terms": (
            "encoding", "codec", "declaration", "charset", "transcoding", "byte", "decoder",
            "latin",
        ),
        "decision": (
            "the exported table is written in a single declared codec and is never transcoded "
            "after writing, so the declaration and the bytes cannot drift apart"
        ),
    },
    "ts-dedup-order": {
        "subject": "how a line is framed in the stream file and what terminates it",
        "terms": (
            "framing", "terminator", "delimiter", "trailing", "parser", "boundary", "chunk",
            "stream",
        ),
        "decision": (
            "every line is a complete entry with nothing spanning a boundary, and the whole "
            "always ends with a terminator so a parser never sees a partial chunk"
        ),
    },
    "ts-empty-input": {
        "subject": "how numbers are formatted in the written summary",
        "terms": (
            "formatting", "precision", "fractional", "grouping", "padding", "width", "notation",
            "significant",
        ),
        "decision": (
            "a count is written with no fractional part and no grouping, and a computed average "
            "carries two places whatever its magnitude"
        ),
    },
    "ts-glob-hidden": {
        "subject": "how a copied tree records file modes and timestamps",
        "terms": (
            "mode", "timestamp", "metadata", "permission", "ownership", "preservation",
            "symlink", "attribute",
        ),
        "decision": (
            "a copied tree preserves modification timestamps and file modes, and a symlink is "
            "copied as a link rather than as the thing it points at"
        ),
    },
    "ts-golden-regen": {
        "subject": "how a failure is reported when a comparison does not match",
        "terms": (
            "diff", "reporting", "context", "truncation", "colour", "verbosity", "summary",
            "mismatch",
        ),
        "decision": (
            "a mismatch prints a unified diff with three lines of context, truncated at forty "
            "lines, and never colourised when the stream is not a terminal"
        ),
    },
    "ts-idempotent-run": {
        "subject": "how a tool signals what it changed as against what it left alone",
        "terms": (
            "signal", "summary", "counted", "unchanged", "verbosity", "reporting", "silence",
            "noop",
        ),
        "decision": (
            "the tool prints one summary line counting what it changed and what it left alone, "
            "and stays silent about individual items"
        ),
    },
    "ts-ignore-gen": {
        "subject": "where a tool reads its own configuration from and in what order",
        "terms": (
            "discovery", "lookup", "search", "ancestor", "override", "location", "resolution",
            "walk",
        ),
        "decision": (
            "configuration is looked up by walking upwards from the working location towards the "
            "ancestor that contains a marker, and the first one found wins outright"
        ),
    },
    "ts-json-sorted": {
        "subject": "how the emitted document is indented and whether it ends with a newline",
        "terms": (
            "indentation", "newline", "whitespace", "compact", "pretty", "spacing", "tab",
            "terminator",
        ),
        "decision": (
            "the emitted document is indented two spaces, never tabs, and ends with exactly one "
            "terminator so a text tool does not report it as truncated"
        ),
    },
    "ts-legacy-hash": {
        "subject": "how a stored artefact is laid out beneath its identifier",
        "terms": (
            "fanout", "nesting", "subdirectory", "layout", "sharding", "inode", "listing",
            "hierarchy",
        ),
        "decision": (
            "stored artefacts are nested two levels deep by the leading characters of their "
            "identifier, so no single level ever grows past a few thousand entries"
        ),
    },
    "ts-log-mask": {
        "subject": "what shape a written line takes and how its parts are ordered",
        "terms": (
            "shape", "ordering", "prefix", "separator", "structured", "parsing", "field",
            "quoting",
        ),
        "decision": (
            "a written line begins with a fixed prefix and carries its parts in a stable order, "
            "so a parser can split on the separator without counting fields"
        ),
    },
    "ts-manifest-rel": {
        "subject": "which algorithm a checksum uses and how the digest is encoded",
        "terms": (
            "algorithm", "digest", "encoding", "hexadecimal", "casing", "length", "prefixing",
            "verification",
        ),
        "decision": (
            "a checksum uses one algorithm across the whole tree and its digest is written in a "
            "single casing, so verification never has to guess which was used"
        ),
    },
    "ts-mig-name": {
        "subject": "how a schema change is written so a repeat does not break it",
        "terms": (
            "guard", "conditional", "existence", "reversible", "statement", "transaction",
            "concurrent", "lock",
        ),
        "decision": (
            "a schema change is guarded by an existence conditional and runs inside one "
            "transaction, so a partial attempt leaves nothing half done"
        ),
    },
    "ts-natural-order": {
        "subject": "which files a listing includes and which it passes over",
        "terms": (
            "inclusion", "exclusion", "extension", "filter", "recursion", "depth", "matching",
            "hidden",
        ),
        "decision": (
            "a listing includes only files with the expected extension, does not recurse past "
            "one level, and passes over anything a tool generated"
        ),
    },
    "ts-nfc-count": {
        "subject": "how a token boundary is decided when text is broken up",
        "terms": (
            "boundary", "tokenisation", "splitting", "hyphenation", "apostrophe", "segment",
            "delimiter", "contraction",
        ),
        "decision": (
            "a hyphenated compound is one token and a contraction is one token, so the "
            "boundary rule is about the delimiter rather than about the letters around it"
        ),
    },
    "ts-quote-shell": {
        "subject": "how a script reports and stops when a step it runs fails",
        "terms": (
            "failure", "propagation", "trap", "pipeline", "strict", "abort", "cleanup",
            "unset",
        ),
        "decision": (
            "the script aborts at the earliest failing step, propagates the failure out of a "
            "pipeline rather than swallowing it, and runs its cleanup on the way out"
        ),
    },
    "ts-retry-cap": {
        "subject": "how long a single call may run before it is abandoned",
        "terms": (
            "timeout", "deadline", "budget", "cancellation", "connect", "read", "elapsed",
            "abandon",
        ),
        "decision": (
            "one call carries a connect deadline and a read deadline separately, and the whole "
            "operation carries a budget that neither may exceed"
        ),
    },
    "ts-round-money": {
        "subject": "which currency a stored amount is in and how the unit travels with it",
        "terms": (
            "currency", "denomination", "minor", "scale", "storage", "conversion", "symbol",
            "pairing",
        ),
        "decision": (
            "an amount is stored in the minor denomination as an integer with its currency "
            "beside it, and the two are never separated in transit"
        ),
    },
    "ts-schema-additive": {
        "subject": "how a record declares which version of the shape it was written under",
        "terms": (
            "versioning", "declaration", "shape", "migration", "reader", "writer",
            "compatibility", "stamp",
        ),
        "decision": (
            "every record carries a version stamp written by the writer, and a reader that does "
            "not recognise a stamp stops rather than guessing the shape"
        ),
    },
    "ts-semver-pin": {
        "subject": "how a resolved dependency tree is recorded and where the record lives",
        "terms": (
            "lockfile", "resolution", "tree", "transitive", "reproducible", "hashes",
            "checked", "regeneration",
        ),
        "decision": (
            "the resolved tree including transitive entries is recorded with hashes in a "
            "lockfile beside the declaration, and the lockfile is checked in"
        ),
    },
    "ts-stable-sort": {
        "subject": "which records are excluded from a merged output before it is written",
        "terms": (
            "exclusion", "filtering", "blank", "malformed", "quarantine", "validation",
            "skipped", "counted",
        ),
        "decision": (
            "a blank or malformed record is excluded and counted rather than passed through, and "
            "the count is written beside the output so a silent drop is visible"
        ),
    },
    "ts-tz-utc": {
        "subject": "how a file is rotated and what the rotated pieces are called",
        "terms": (
            "rotation", "naming", "sequence", "compression", "retention", "generation",
            "suffix", "handover",
        ),
        "decision": (
            "rotation renames in place with a numeric generation suffix, compresses everything "
            "past the first generation, and never reuses a name it has used before"
        ),
    },
    "xs-evolve-lease": {
        "subject": "how a long running loop reports that it is still alive",
        "terms": (
            "liveness", "progress", "reporting", "counter", "quiet", "emission", "throttling",
            "observability",
        ),
        "decision": (
            "the loop emits one progress counter per completed unit, throttled so a fast loop "
            "does not flood the stream, and stays quiet when nothing has advanced"
        ),
    },
    "xs-join-batch": {
        "subject": "how a payload is serialised and compressed before it leaves the process",
        "terms": (
            "serialisation", "compression", "envelope", "encoding", "payload", "framing",
            "negotiation", "content",
        ),
        "decision": (
            "a payload is serialised into one envelope and compressed only when it passes a "
            "size threshold, with the encoding declared in the envelope rather than negotiated"
        ),
    },
    "xs-widen-manifest": {
        "subject": "how entries are separated and what happens to a name that contains the "
                   "separator",
        "terms": (
            "separator", "escaping", "quoting", "ambiguity", "parsing", "encoding", "record",
            "boundary",
        ),
        "decision": (
            "entries are separated by a newline and a name containing one is escaped rather "
            "than quoted, so a parser splitting on the separator cannot be misled"
        ),
    },
}
