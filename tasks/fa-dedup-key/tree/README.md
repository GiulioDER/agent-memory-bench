# order intake

`orders/` holds one JSON Lines file per supplier, named for the supplier. Each line is an
order: `order_id`, `sku`, `qty`, and `received_at`, the moment the file was ingested.

Suppliers redeliver a file when an upload is interrupted, so an order can arrive again in a
later file with a newer `received_at`.
