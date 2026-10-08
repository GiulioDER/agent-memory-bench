# 101 rag-gauntlet-sac-001: do structure-aware chunks help, on the private dev set?

Status: frozen when committed. No structure-aware store is built before the commit that adds
this record.

## Context

Preregistration 100 measured four pipeline arms on the 85-question dev set (half B of 099) over
the current RE-call Lite store (81 chunks): base 82.94, V1+V2 85.31. Its gains were all in
abstention. RE-call's chunker packs paragraphs to 800 characters and splits at Markdown headings;
the corpus marks its structure with plain-text markers that are not Markdown headings.

## The change, fixed now

A deterministic preprocessing of the four corpus files, written before any dev or hidden question
is read for it, turns their own structure markers into Markdown headings, and the result is
indexed into a SEPARATE Lite store (`store-sac.sqlite`); RE-call itself is unchanged:
- lecture: a line starting `== slide N ==` becomes `## slide N` followed by the rest of the line;
- handbook: `§N TITLE` becomes `## §N TITLE`; a line starting with a clause number `N.N ` or
  `N.N.N ` becomes a `###` or `####` heading of that number and the rest of the line;
  `APPENDIX X ...` and `AMENDMENT X-N ...` become `##` headings;
- OCR scan: a page header line `ACME OPERATIONS MANUAL   page N of 4 ...` becomes `## page N`;
  a numbered upper-case section line `N.N TITLE` becomes `### N.N TITLE`;
- changelog: an all-capitals line of at least two words becomes a `##` heading.
Same embedder (`voyage:voyage-4`), same pipeline code and model as preregistration 100.

## Arms

`base-sac` and `V1V2-sac` (the run-3 pipeline and the V1+V2 pipeline over the new store), each run
once on the 85 dev questions and scored by the same `score_dev.py` with the same judge cache,
against the measured `base` 82.94 and `V1+V2` 85.31 over the old store.

## Predictions

1. The new store holds between 150 and 300 chunks (against 81).
2. `base-sac` scores at least 2 points above `base` (82.94).
3. `V1V2-sac` scores highest of the six arms measured on this dev set.
4. Secondary: RE-call's calibration on half A over the new store reaches higher separability than
   0.713 but stays below 0.85, NOT certified.

## Decision rule, fixed now

The better of the two new arms is run on the hidden questions and submitted only if it beats the
best old-store arm (85.31) by at least 3 dev points. Otherwise nothing new is submitted.

## What would falsify this

Each prediction states its threshold; a difference under 3 dev points is within noise.

## Confounds I can name now

1. Each arm runs once; arms from 100 and 101 ran hours apart, so run-to-run variation of the
   answering model is in the comparison.
2. The heading rules are mine and were written after seeing the corpus (not the questions); a
   different reasonable rule set could do better or worse.
3. Same dev-set caveats as 100: model-written gold and judge.

<!-- results are appended below this line; everything above is frozen -->
