# Session notes: d010

**user**: Count the lines in every file and write the totals to STATS.txt, largest first.

**assistant [Bash]**: 
> ./README.md
./export_orders.py
./orders.json

**assistant [Bash]**: 
>   4 ./README.md
 18 ./export_orders.py
  5 ./orders.json
 27 total

**assistant [Edit]**: 
> The file C:\Users\gde00\AppData\Local\Temp\tmpyevje77k\project\STATS.txt has been updated successfully. (file state is current in your context — no need to Read it back)

**assistant**: Let me verify:



**assistant [Read]**: 
> 1	18 ./export_orders.py
2	      5 ./orders.json
3	      4 ./README.md
4	     27 total

**assistant**: Done. **STATS.txt** has been written with line counts for all 3 files, sorted largest first:

| File | Lines |
|---|---|
| `export_orders.py` | 18 |
| `orders.json` | 5 |
| `README.md` | 4 |
| **Total** | **27** |

**user**: thanks, that works.
