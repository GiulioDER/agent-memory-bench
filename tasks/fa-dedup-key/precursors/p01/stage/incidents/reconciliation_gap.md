# July reconciliation is short

Finance reconciled supplier statements against what the warehouse system holds and found a
gap. The statements say 48,306 orders for the month. We hold 47,092.

| supplier | on statement | in our system |
|---|---:|---:|
| ridge | 12,880 | 12,880 |
| delta | 11,415 | 10,201 |
| keld | 9,904 | 9,904 |
| harbour | 14,107 | 14,107 |

One supplier, and the shortfall is 1,214. The missing orders are not in any error log, any
quarantine table, or any retry queue. Nothing failed. They were never written.

Spot-checked eleven of the missing orders against delta's statement. All eleven are real
orders that were delivered and invoiced.
