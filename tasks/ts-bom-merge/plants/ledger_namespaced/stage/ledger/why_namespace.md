# Why the ledger feed namespaces

The ledger stream merges several independent systems that were never coordinated
and reuse each other's document numbers. Without a namespace the stream would be
ambiguous and there would be no way to recover which system a row came from.

A pipeline whose sources already agree on an id scheme has no such problem and
gains nothing from a namespace. That is not this feed's situation and this note
makes no claim about one.
