# outbox

Records queued for the atlas feed (partner code `pt-118`). `client.send(batch)` posts one list
of records to the endpoint in `partner.ini` and returns the partner's HTTP status.

`outbox.jsonl` is one record per line, in the order the collector wrote them.
