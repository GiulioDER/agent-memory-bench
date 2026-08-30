"""Vocabulary and project templates for the synthetic haystack.

Kept apart from ``scripts/generate_haystack.py`` so the generator reads as mechanism and this
reads as data. Everything here is authored for this repository: no third-party text is copied
in, so the haystack carries no licence obligation and no provenance question.

The design constraint that shapes every list below is **containment**. A synthetic session may
never state any task's governing fact, and the cheapest way to guarantee that is to build the
vocabulary out of subjects the task suite does not legislate: berth allocation, hive
inspections, grant cycles. ``scripts/generate_haystack.py`` re-checks every emitted file against
every task's ``fact_terms`` anyway, because a guarantee nobody tests is a hope.
"""

from __future__ import annotations

#: One entry becomes a family of generated repositories. ``entities`` and ``fields`` are the
#: lexical spine: they appear in the README, in the data file, in the tool results and in the
#: agent's prose, which is what makes a generated session read as being ABOUT something rather
#: than as filler with a domain word stapled on.
DOMAINS: tuple[dict[str, tuple[str, ...] | str], ...] = (
    {
        "slug": "fieldpipe",
        "title": "field report intake",
        "entities": ("event", "site", "reporter", "dispatch"),
        "fields": ("event_id", "site", "status", "reported_at", "severity"),
        "verbs": ("intake", "triage", "route", "acknowledge"),
    },
    {
        "slug": "stockroom",
        "title": "warehouse stock levels",
        "entities": ("pallet", "bin", "shipment", "reorder"),
        "fields": ("sku", "bin_code", "on_hand", "reorder_point", "counted_at"),
        "verbs": ("count", "replenish", "reserve", "pick"),
    },
    {
        "slug": "rosterly",
        "title": "shift rostering",
        "entities": ("shift", "crew", "swap", "coverage"),
        "fields": ("shift_id", "crew", "starts_at", "hours", "role"),
        "verbs": ("assign", "publish", "swap", "backfill"),
    },
    {
        "slug": "meterloop",
        "title": "utility meter telemetry",
        "entities": ("meter", "reading", "route", "anomaly"),
        "fields": ("meter_id", "reading", "route", "taken_at", "unit"),
        "verbs": ("poll", "aggregate", "flag", "backfill"),
    },
    {
        "slug": "grantdesk",
        "title": "grant application tracking",
        "entities": ("application", "reviewer", "award", "cycle"),
        "fields": ("application_id", "applicant", "stage", "submitted_at", "amount"),
        "verbs": ("screen", "score", "award", "decline"),
    },
    {
        "slug": "trailhead",
        "title": "park trail condition reports",
        "entities": ("trail", "segment", "closure", "survey"),
        "fields": ("trail_id", "segment", "condition", "surveyed_at", "length_km"),
        "verbs": ("survey", "close", "reopen", "grade"),
    },
    {
        "slug": "clinicq",
        "title": "clinic appointment queueing",
        "entities": ("appointment", "clinician", "slot", "referral"),
        "fields": ("appointment_id", "clinician", "slot", "booked_at", "duration_min"),
        "verbs": ("book", "reschedule", "release", "confirm"),
    },
    {
        "slug": "freightbook",
        "title": "freight booking ledger",
        "entities": ("consignment", "carrier", "leg", "manifest"),
        "fields": ("consignment_id", "carrier", "origin", "booked_at", "weight_kg"),
        "verbs": ("book", "consolidate", "dispatch", "settle"),
    },
    {
        "slug": "libcirc",
        "title": "library circulation",
        "entities": ("loan", "title", "hold", "branch"),
        "fields": ("loan_id", "branch", "due_on", "issued_at", "renewals"),
        "verbs": ("issue", "renew", "recall", "shelve"),
    },
    {
        "slug": "beehive",
        "title": "apiary hive inspections",
        "entities": ("hive", "inspection", "queen", "yard"),
        "fields": ("hive_id", "yard", "frames", "inspected_at", "temper"),
        "verbs": ("inspect", "requeen", "split", "feed"),
    },
    {
        "slug": "tollgate",
        "title": "toll plaza transactions",
        "entities": ("transit", "plaza", "tag", "rebill"),
        "fields": ("transit_id", "plaza", "lane", "passed_at", "vehicle_class"),
        "verbs": ("capture", "rate", "rebill", "void"),
    },
    {
        "slug": "seedvault",
        "title": "seed accession catalogue",
        "entities": ("accession", "lot", "germination", "collection"),
        "fields": ("accession_id", "species", "lot", "collected_at", "viability"),
        "verbs": ("accession", "test", "regenerate", "distribute"),
    },
    {
        "slug": "quaydesk",
        "title": "harbour berth allocation",
        "entities": ("berth", "vessel", "window", "pilotage"),
        "fields": ("berth_id", "vessel", "window", "arrived_at", "draft_m"),
        "verbs": ("allocate", "shift", "release", "pilot"),
    },
    {
        "slug": "kilnwatch",
        "title": "ceramics kiln firing logs",
        "entities": ("firing", "kiln", "cone", "batch"),
        "fields": ("firing_id", "kiln", "cone", "started_at", "peak_c"),
        "verbs": ("load", "fire", "soak", "unload"),
    },
    {
        "slug": "plotmap",
        "title": "allotment plot tenancy",
        "entities": ("plot", "tenant", "waitlist", "inspection"),
        "fields": ("plot_id", "tenant", "status", "let_at", "area_m2"),
        "verbs": ("let", "inspect", "terminate", "offer"),
    },
    {
        "slug": "chorale",
        "title": "choir attendance and parts",
        "entities": ("rehearsal", "singer", "part", "concert"),
        "fields": ("rehearsal_id", "singer", "part", "held_at", "present"),
        "verbs": ("register", "assign", "excuse", "call"),
    },
    {
        "slug": "windfarm",
        "title": "turbine maintenance windows",
        "entities": ("turbine", "outage", "technician", "curtailment"),
        "fields": ("turbine_id", "outage", "technician", "opened_at", "mwh_lost"),
        "verbs": ("schedule", "curtail", "restore", "defer"),
    },
    {
        "slug": "boxoffice",
        "title": "venue seat allocation",
        "entities": ("booking", "seat", "performance", "release"),
        "fields": ("booking_id", "performance", "seat", "sold_at", "tier"),
        "verbs": ("hold", "release", "exchange", "comp"),
    },
    {
        "slug": "assayline",
        "title": "laboratory sample assays",
        "entities": ("sample", "assay", "batch", "control"),
        "fields": ("sample_id", "assay", "batch", "received_at", "result"),
        "verbs": ("receive", "run", "repeat", "release"),
    },
    {
        "slug": "permitmill",
        "title": "building permit workflow",
        "entities": ("permit", "inspection", "objection", "zone"),
        "fields": ("permit_id", "zone", "stage", "lodged_at", "storeys"),
        "verbs": ("lodge", "refer", "grant", "refuse"),
    },
    {
        "slug": "riverwatch",
        "title": "river gauge observations",
        "entities": ("gauge", "observation", "catchment", "alert"),
        "fields": ("gauge_id", "catchment", "level_m", "observed_at", "trend"),
        "verbs": ("observe", "alert", "stand down", "calibrate"),
    },
    {
        "slug": "fleetcare",
        "title": "vehicle servicing history",
        "entities": ("vehicle", "service", "part", "depot"),
        "fields": ("vehicle_id", "depot", "service", "serviced_at", "odometer"),
        "verbs": ("service", "defer", "condemn", "return"),
    },
    {
        "slug": "cellarbook",
        "title": "cellar stock rotation",
        "entities": ("bottle", "rack", "vintage", "tasting"),
        "fields": ("bottle_id", "rack", "vintage", "laid_down_at", "drink_by"),
        "verbs": ("rotate", "pull", "taste", "restock"),
    },
    {
        "slug": "signalbox",
        "title": "level crossing fault reports",
        "entities": ("crossing", "fault", "patrol", "restriction"),
        "fields": ("crossing_id", "fault", "patrol", "raised_at", "severity"),
        "verbs": ("raise", "attend", "restrict", "clear"),
    },
)

#: The work a mundane session does. Each is a request no task in this suite legislates, so a
#: session that carries it out states a conclusion about ITS OWN repository and nothing else.
THEMES: tuple[dict[str, str], ...] = (
    {
        "key": "overview",
        "prompt": "Summarise what this project does and what each file is for, in OVERVIEW.md.",
        "target": "OVERVIEW.md",
        "closing": "that reads well, thanks.",
    },
    {
        "key": "getting-started",
        "prompt": "Add a Getting started section to the README explaining how to run the tools here.",
        "target": "README.md",
        "closing": "good, that is what a newcomer needs.",
    },
    {
        "key": "data-dictionary",
        "prompt": "List the data files and describe their columns or fields in DATA.md.",
        "target": "DATA.md",
        "closing": "thanks, that covers the fields.",
    },
    {
        "key": "todo-roundup",
        "prompt": "Collect the TODO comments here into a single TODO.md with file references.",
        "target": "TODO.md",
        "closing": "useful, we will work through those.",
    },
    {
        "key": "changelog",
        "prompt": "Start a CHANGELOG.md and record the change that is already in the working tree.",
        "target": "CHANGELOG.md",
        "closing": "fine, keep adding to it.",
    },
    {
        "key": "usage-help",
        "prompt": "The CLI has no usage text. Add a short help string describing each argument.",
        "target": "report.py",
        "closing": "that is clearer than before.",
    },
    {
        "key": "input-validation",
        "prompt": "Add a check that rejects a record missing a required field, with a clear message.",
        "target": "report.py",
        "closing": "good, that will catch it early.",
    },
    {
        "key": "docstrings",
        "prompt": "The functions here have no docstrings. Write one for each saying what it returns.",
        "target": "report.py",
        "closing": "thanks, much easier to follow now.",
    },
    # NOT "glossary": that word is one of `ts-nfc-count`'s fact_terms, so every session using it
    # was discarded by the containment filter and the theme vanished from the haystack entirely.
    # A generic English word owned as a fact term quietly removes a whole category of ordinary
    # sessions from the distractor pool; the filter reported a count, not the missing category.
    {
        "key": "domain-terms",
        "prompt": "Write TERMS.md defining the domain words this repository uses.",
        "target": "TERMS.md",
        "closing": "that is the vocabulary, yes.",
    },
    {
        "key": "smoke-notes",
        "prompt": "Write NOTES.md recording how you would check by hand that the tool still works.",
        "target": "NOTES.md",
        "closing": "noted, we will follow that.",
    },
    {
        "key": "field-rename",
        "prompt": "Rename the report headings so they read as words rather than as field names.",
        "target": "report.py",
        "closing": "much more readable in the report.",
    },
    {
        "key": "counts-summary",
        "prompt": "Print a one-line count summary at the end of the run so a person can check it.",
        "target": "report.py",
        "closing": "that is the number I wanted to see.",
    },
    {
        "key": "sample-data",
        "prompt": "Add a small sample data file and mention it in the README so the tool can be tried.",
        "target": "README.md",
        "closing": "good, that makes it runnable.",
    },
    {
        "key": "faq",
        "prompt": "Write a short FAQ.md answering the questions newcomers ask about this repository.",
        "target": "FAQ.md",
        "closing": "those are the right questions.",
    },
    {
        "key": "maintainers",
        "prompt": "Write MAINTAINERS.md saying who owns which part of this repository.",
        "target": "MAINTAINERS.md",
        "closing": "thanks, that settles the ownership question.",
    },
    {
        "key": "structure-review",
        "prompt": "Review the repository layout and write LAYOUT.md describing where new code should go.",
        "target": "LAYOUT.md",
        "closing": "agreed, that is where things belong.",
    },
)

#: Prose the assistant uses to open a summary turn. Varied so the corpus does not collapse to
#: one sentence repeated five thousand times, which would make every document a near-duplicate
#: of every other and hand a retriever an artificially easy discrimination.
SUMMARY_OPENERS: tuple[str, ...] = (
    "Done. Here is what changed and why:",
    "That is in place now. What I did:",
    "Finished. The shape of the change:",
    "Written. A note on what it covers:",
    "Complete. Reading back what is now true:",
    "Landed. The reasoning, briefly:",
)

#: How a session closes when the work raised a small local convention. These are deliberately
#: about the GENERATED repository's own artefacts, never about a benchmark task's subject.
LOCAL_CONVENTIONS: tuple[str, ...] = (
    (
        "I kept the section order matching the order the files appear in the listing, so the "
        "two stay easy to compare."
    ),
    (
        "I referred to each file by its path from the repository root rather than by a "
        "nickname, since the nicknames are not written down anywhere."
    ),
    (
        "I left the existing wording alone where it was already accurate and only added the new "
        "material, to keep the diff readable."
    ),
    (
        "I put the new file beside the README rather than in a subdirectory, because everything "
        "else a reader needs is at the top level."
    ),
    (
        "I wrote the counts out rather than rounding them, since the point of the summary is to "
        "be checkable by hand."
    ),
    (
        "I used the field names exactly as they appear in the data file, so a reader can grep "
        "for them and land in the right place."
    ),
)
