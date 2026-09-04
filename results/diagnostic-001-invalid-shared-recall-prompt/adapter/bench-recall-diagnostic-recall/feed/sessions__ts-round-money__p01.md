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

The discrepancy comes from **0.805** and **1.885** both being exactly halfway between two cents. Standard rounding ("round half up") pushes each up by 0.005, giving us an extra **0.01** in total that gets swallowed when we round only at the end.

---

## Recommended Standard

Align with the partner's approach:

1. **Round each line item** to the nearest cent (2 decimal places) using standard "round half up" arithmetic.
2. **Sum the rounded line items** to produce the invoice total.
3. **Never round a total** that is already the sum of rounded values.

This guarantees that the partner's per-line remittance logic will always match our final total.

**user**: Confirmed, that closes the reconciliation gap. Decision: money is never float. Every line total is computed with Decimal and rounded to cents with ROUND_HALF_UP per line, before summing. Totals formatted with two decimals from the Decimal sum.
