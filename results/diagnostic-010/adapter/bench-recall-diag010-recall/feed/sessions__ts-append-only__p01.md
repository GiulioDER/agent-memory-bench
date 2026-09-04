# Session notes: p01

**user**: The nightly ledger verification went red on Monday evening: metrics.log no longer matched the snapshot the reporting side holds, and the push was refused (incident/verify.log). The file exactly as pushed that evening is preserved at incident/metrics.log.rejected-2026-08-04, the reporting side's snapshot at incident/snapshot-2026-08-03/metrics.log, and the live metrics.log has since been restored with Monday's entry re-added. Work out exactly what the rejected version changed compared to the snapshot, line by line in plain words (which characters were added or removed and where), why verification refused it, and state the rule for how this file gets updated from now on.

**assistant [Read]**: 
> 1	2026-07-28 builds=33 failures=1
2	2026-07-29 builds=36 failures=0
3	2026-07-30 builds=31 failures=2
4	2026-07-31 builds=38 failures=4
5	2026-08-01 builds=29 failures=0
6	2026-08-02 builds=34 failures=1
7	2026-08-03 builds=35 failures=2
8	2026-08-04 builds=37 failures=1
9	

**assistant [Read]**: 
> 1	2026-07-28 builds=33 failures=1
2	2026-07-29  builds=36  failures=0
3	2026-07-30 builds=31 failures=2
4	2026-07-31 builds=38   failures=4
5	2026-08-01 builds=29 failures=0
6	2026-08-02  builds=34 failures=1
7	2026-08-03 builds=35 failures=2
8	

**assistant [Read]**: 
> 1	2026-07-28 builds=33 failures=1
2	2026-07-29  builds=36  failures=0
3	2026-07-30 builds=31 failures=2
4	2026-07-31 builds=38   failures=4
5	2026-08-01 builds=29 failures=0
6	2026-08-02  builds=34 failures=1
7	2026-08-03 builds=35 failures=2
8	2026-08-04 builds=37 failures=1
9	

**assistant [Read]**: 
> 1	2026-08-04 21:00:03 ledger-verify: comparing metrics.log against snapshot-2026-08-03
2	2026-08-04 21:00:03 ledger-verify: FAILED prefix check, first divergence at byte offset 43
3	2026-08-04 21:00:03 ledger-verify: expected '2026-07-29  builds=36  failures=0'
4	2026-08-04 21:00:03 ledger-verify: found    '2026-07-29 builds=36 failures=0'
5	2026-08-04 21:00:03 ledger-verify: refusing the file; reporting side kept the snapshot
6	

**assistant**: ## Analysis of the Monday Night Ledger Verification Failure

### Files involved

| File | Description |
|---|---|
| `incident/snapshot-2026-08-03/metrics.log` | The reporting side's snapshot (the reference/expected content) |
| `incident/metrics.log.rejected-2026-08-04` | The exact file pushed Monday evening that was refused |
| `metrics.log` | The live file, since restored with Monday's entry re-added |
| `incident/verify.log` | The verification failure report |

---

### Line-by-line differences between snapshot (expected) and rejected version

**Line 2 — `2026-07-29`**

| Version | Content | Difference |
|---|---|---|
| **Snapshot** | `2026-07-29  builds=36  failures=0` | two spaces after the date, two spaces before `failures=` |
| **Rejected** | `2026-07-29 builds=36 failures=0` | one space each |

→ **Changes:** Removed **one space** before `builds=` and **one space** before `failures=`.

**Line 4 — `2026-07-31`**

| Version | Content | Difference |
|---|---|---|
| **Snapshot** | `2026-07-31 builds=38   failures=4` | three spaces before `failures=` |
| **Rejected** | `2026-07-31 builds=38 failures=4` | one space before `failures=` |

→ **Changes:** Removed **two spaces** before `failures=`.

**Line 6 — `2026-08-02`**

| Version | Content | Difference |
|---|---|---|
| **Snapshot** | `2026-08-02  builds=34 failures=1` | two spaces after the date |
| **Rejected** | `2026-08-02 builds=34 failures=1` | one space after the date |

→ **Changes:** Removed **one space** before `builds=`.

**Line 8 — `2026-08-04`** *(new line, not in snapshot)*

| Version | Content |
|---|---|
| **Snapshot** | *(ends at line 7 — `2026-08-03`)* |
| **Rejected** | `2026-08-04 builds=37 failures=1` |

→ **Changes:** Added a new eighth line for the new day's data (this is expected and normal).

---

### Why verification refused it

The `verify.log` tells us exactly what happened:

```
2026-08-04 21:00:03 ledger-verify: FAILED prefix check, first divergence at byte offset 43
2026-08-04 21:00:03 ledger-verify: expected '2026-07-29  builds=36  failures=0'
2026-08-04 21:00:03 ledger-verify: found    '2026-07-29 builds=36 failures=0'
```

The verification does a **byte-for-byte prefix comparison** against the snapshot. The snapshot preserves **irregular whitespace**: some lines have extra spaces inserted between fields (lines 2, 4, and 6). Whoever generated the rejected version on Monday **normalised that whitespace** — they collapsed all runs of spaces down to a single space — and then appended the new `2026-08-04` line.

Because the prefix of the rejected file no longer matched the snapshot byte-for-byte (even on existing historical lines), the verification check failed at byte 43 (the first spot where the two files differed), and the push was rejected.

The live `metrics.log` has since been restored to match the snapshot exactly (preserving the irregular spacing on lines 2, 4, 6), with the `2026-08-04` entry appended *without* modifying any existing lines.

---

### Rule for how this file gets updated from now on

**Append only — never modify existing lines.**

When adding a new day's entry:
1. Read the existing file as raw bytes.
2. **Do not** re-format, re-indent, normalise whitespace, strip trailing spaces, or otherwise touch any existing line.
3. Append the new line to the end, matching whatever spacing convention the most recent line uses.
4. Push.

The snapshot is compared via a prefix check (byte-for-byte on all existing content), so any change — even removing a single space on a historical line — will cause verification to fail.

**user**: Agreed. Decision: metrics.log is append-only; it is an audit trail. Never rewrite past lines and do not tidy old spacing or formatting, however inconsistent it looks: after any update, the previous file content must remain a byte-identical prefix of the new file, with the day's entry appended at the end and nothing else touched.
