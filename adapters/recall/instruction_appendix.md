## Reading a `recall_search` result

This store returns a verdict per hit rather than a ranked list.

- **`ok`**: the store considers this claim live.
- **`superseded`**: the store has recorded that this claim was later retracted, and carries a
  pointer to the document that replaced it.
- **`low_confidence`**, or an **abstention** with no hits: nothing cleared the store's threshold for
  this query.
- **`ok` with a calibrated confidence**: this corpus carries a certified calibration bound to an
  immutable generation, so the store's threshold is a measurement and its abstentions mean
  something.
