# Session notes: p01

**user**: On Friday's incident call the on-call swore the payment webhook landed just after 16:00, but app.log says 14:03:11, and nothing on the line says which timezone that stamp is in (the provider's delivery receipt is in ops/webhook_receipt.txt). We hit the same confusion at the March clock change and never settled it (ops/march_rotation_note.txt). Establish what timezone app.log timestamps actually are, prove it against the receipt, and state the parsing rule every tool that reads or rotates app.log must follow.

**assistant [Read]**: 
> 1	2026-06-01 05:58:11 service started
2	2026-06-03 21:14:52 cache warmed
3	2026-06-05 14:03:11 payment webhook received order=O-2231
4	2026-06-08 09:30:00 nightly sync ok
5	2026-06-14 22:41:07 config reloaded
6	

**assistant [Read]**: 
> 1	Provider dashboard export, event evt_88412
2	order: O-2231
3	status: delivered
4	delivered_at: 2026-06-05T16:03:11+02:00 (Europe/Rome)
5	attempt: 1, response: 200
6	

**assistant [Read]**: 
> 1	Ops note, 2026-03-30
2	
3	The Sunday clock change bit us again: Saturday evening's entries were swept
4	into archive.log one rotation early, and during the outage call the timeline
5	built from app.log ran an hour off against the provider's dashboard. Root
6	cause never written up; parking the evidence here was supposed to be
7	temporary.
8	

**assistant**: ## Investigation: app.log Timezone

### Evidence

| Source | Timestamp | Offset |
|---|---|---|
| `app.log` line 3 | `2026-06-05 14:03:11` | *(none stated)* |
| `webhook_receipt.txt` | `2026-06-05T16:03:11+02:00` (Europe/Rome) | UTC+2 (CEST) |
| `march_rotation_note.txt` | "ran an hour off against the provider's dashboard" | March → UTC+1 (CET) |

### Analysis

The receipt explicitly gives `16:03:11+02:00`. The app log for the same event says `14:03:11`. That is **exactly two hours earlier** — which is the UTC equivalent of +02:00.

The March note confirms the pattern: in March, Italy was on CET (UTC+1), and the note says the timeline built from app.log "ran an hour off" against the provider's dashboard. An app.log in UTC would indeed be exactly 1 hour behind a CET-local dashboard — matching perfectly.

### Conclusion

**`app.log` timestamps are in UTC.** They carry no trailing `Z` or offset literal, but the actual timezone is UTC.

### Parsing rule

Every tool that reads, writes, or rotates `app.log` **must**:

1. **Parse every timestamp as UTC** — treat `2026-06-05 14:03:11` as `2026-06-05T14:03:11Z`.
2. **When correlating against provider dashboards or receipts** (which use `Europe/Rome`), always convert the app.log UTC timestamp to Rome local time (or vice versa) before comparing — never compare raw strings.
3. **When a rotation boundary is defined by local calendar date** (e.g., "archive the previous day at midnight local time"), compute the corresponding UTC instant using the `Europe/Rome` timezone so the cut-off aligns with the local day.

**user**: Settled, and that finally closes out the DST incident from March. Decision: app.log timestamps are UTC even though they carry no timezone suffix. Every tool that reads or rotates app.log must parse as UTC explicitly, never local time, and any cutoff computed from a wall-clock argument gets converted to UTC before comparing against log entries.
