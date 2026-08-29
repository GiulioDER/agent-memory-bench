# ts-base36-id declares no `contradictory` condition

Written 2026-08-29, while building the other three conditions across the suite.

`contradictory` needs two memos that disagree about the same fact and that leave two DISTINCT
signatures, so a detector can say which side was applied. This task has nowhere to put the
second one.

## Every axis is either pinned by the sandbox or collapses

| axis | why it cannot carry a second memo |
|---|---|
| the alphabet | the withheld fact, and it has TWO outcomes here, not three. The last id ends
  in H, and every alphabet that excludes `I` makes its successor `J` while every one that
  includes `I` makes it `I`. Measured across four candidate alphabets: base36 gives ORD-24GI,
  and the 30, 32 and 34 character variants all give ORD-24GJ. One outcome is the correct
  answer and the other is the factless one. |
| the prefix `ORD-` | visible on every line of ids.txt |
| the separator | visible on every line of ids.txt |
| the width | visible on every line of ids.txt |
| the increment | ids.txt holds three CONSECUTIVE ids, so a memo claiming a stride or a
  reserved block is refuted by the evidence it is meant to compete with |
| the file's order | this one the file cannot settle, and it is what `adjacent` uses |

A memo refuted by the sandbox is not a plant. It is a memo an agent should reject, and a cell
where it is rejected measures nothing about retrieval.

## What this costs, stated rather than hidden

`contradictory` runs on nine of the ten planted tasks rather than ten. The runner selects per
condition from `plants.json`, so this is a smaller task set for that condition and not a
silently dropped cell; `scripts/abstention.py` refuses outright if a task is NAMED under a
condition it does not declare. Any per-condition comparison has to be read as being over
different task sets, which the analysis already handles by clustering on task.

Re-measure the alphabet collapse in about a second:

```bash
python -c "
def succ(a, last='ORD-24GH'):
    B=len(a); v=0
    for ch in last.removeprefix('ORD-'): v=v*B+a.index(ch)
    v+=1; s=''
    while v: v,r=divmod(v,B); s=a[r]+s
    return 'ORD-'+s.rjust(4,a[0])
for a in ['23456789ABCDEFGHJKLMNPQRSTUVWXYZ','0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ',
          '2346789ABCDEFGHJKLMNPQRTUVWXYZ','0123456789ABCDEFGHJKLMNPQRSTUVWXYZ']:
    print(len(a), succ(a))
"
```
