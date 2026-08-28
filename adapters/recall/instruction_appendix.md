## Reading a `recall_search` result

This store returns a verdict per hit rather than a ranked list.

- **`ok`**: the store considers this claim live.
- **`superseded`**: the store has recorded that this claim was later retracted, and carries a
  pointer to the document that replaced it.
- **`low_confidence`**, or an **abstention** with no hits: nothing cleared the store's threshold for
  this query.
- **`DEGRADED:INDEX_NOT_READY`** on every result: no calibration is fitted to this corpus, so the
  threshold is a placeholder rather than a measurement.
