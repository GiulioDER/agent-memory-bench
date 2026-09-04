Project memory:

[Evidence item]
**assistant [Bash]**: 
> README.md: ASCII text
items.csv: CSV ASCII text
---
# billingkit$
$
Small billing utilities. Line items arrive in `items.csv` with columns `qty,unit_price`.$
Tools live in the repository root and read their input from the current directory.$
---
qty,unit_price$
2,3.50$
1,10.25$
4,0.20$

**assistant**: Now I have a clear picture of the formatting. Let me check one more thing — if there's any existing `.editorconfig` or gitattributes

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Bash]**: 
>   4 README.md
  4 items.csv
  8 total

**assistant**: Now I have all the information I need. The existing files share these formatting properties:

Recorded: 2026-08-26 07:31:58.743491+00:00
Status: current
Source: distractors__d095.md
[/Evidence item]

[Evidence item]
./.git/objects/a0/19d9c7bb2da952f0946fbb088011e332614c79
./.git/objects/a2/47d4d3192253b24b3d7bd5e1fefa65de9a89eb
./.git/objects/f3/02c8b8a35e2adb3b71d02e25e104f909f7960b
./.git/refs/heads/main
./items.csv
./README.md

**assistant [Read]**: 
> 1	qty,unit_price
2	2,3.50
3	1,10.25
4	4,0.20
5

**assistant [Read]**: 
> 1	# billingkit
2	
3	Small billing utilities. Line items arrive in `items.csv` with columns `qty,unit_price`.
4	Tools live in the repository root and read their input from the current directory.
5

**assistant [Bash]**: 
> qty,unit_price
2,3.50
1,10.25
4,0.20

**assistant**: Now I'll create the `DATA.md` file describing the data

Recorded: 2026-08-26 07:27:34.488008+00:00
Status: current
Source: distractors__d002.md
[/Evidence item]

[Evidence item]
# Session notes: p01

**user**: Partner reconciliation bounced invoice INV-1042: they computed a total of 2.70 and our export said 2.69, and the invoice came back (their note is in reconciliation/partner_note.txt, the line items in invoices/inv-1042.csv). Work out exactly where the missing cent comes from, and tell me what arithmetic and rounding we should standardise on so our totals always match the partner's.

**assistant [Read]**: 
> 1	INV-1042 rejected at reconciliation.
2	Partner computed total: 2.70
3	Our exported total: 2.69
4	Partner remittance system computes each line to the cent before summing.
5	Please align and resubmit.
6

**assistant [Read]**: 
> 1	qty,unit_price
2	7,0.115
3	1,1.885
4

**assistant**: ## Analysis of the Missing Cent

**Invoice INV-1042** has two line items:

Recorded: 2026-08-26 07:33:09.117388+00:00
Status: current
Source: sessions__ts-round-money__p01.md
[/Evidence item]

[Evidence item]
./.git/objects/62/f1737e7ab400225f3cc1aafbe5d22d5ab167c9
./.git/objects/a2/47d4d3192253b24b3d7bd5e1fefa65de9a89eb
./.git/objects/f3/02c8b8a35e2adb3b71d02e25e104f909f7960b
./.git/refs/heads/main
./items.csv
./README.md

**assistant [Read]**: 
> 1	# billingkit
2	
3	Small billing utilities. Line items arrive in `items.csv` with columns `qty,unit_price`.
4	Tools live in the repository root and read their input from the current directory.
5

**assistant [Read]**: 
> 1	qty,unit_price
2	2,3.50
3	1,10.25
4	4,0.20
5

Recorded: 2026-08-26 07:31:58.743491+00:00
Status: current
Source: distractors__d095.md
[/Evidence item]

[Evidence item]
| Qty | Unit Price | Raw Total |
|-----|-----------|-----------|
| 7   | 0.115     | 0.805     |
| 1   | 1.885     | 1.885     |
|     |           | **2.690** |

### How the partner got 2.70

The partner rounds **each line item to the cent first**, then sums:

- `7 × 0.115 = 0.805` → rounds to **0.81**
- `1 × 1.885 = 1.885` → rounds to **1.89**
- **Total: 0.81 + 1.89 = 2.70** ✅

### How we got 2.69

We summed the raw totals first, then rounded the grand total:

- `0.805 + 1.885 = 2.690`
- Rounded to 2 decimal places → **2.69** ❌

### The missing cent

Recorded: 2026-08-26 07:33:09.117388+00:00
Status: current
Source: sessions__ts-round-money__p01.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# billingkit

Small billing utilities. Line items arrive in `items.csv` with columns `qty,unit_price`.
Tools live in the repository root and read their input from the current directory.
