# Session notes: d041

**user**: Count the lines in every file and write the totals to STATS.txt, largest first.

**assistant [Bash]**: 
> ./api.py
./demo.py
./README.md

**assistant [Bash]**: 
>  15 ./api.py
 12 ./demo.py
  4 ./README.md
 31 total

**assistant [Edit]**: 
> The file C:\Users\gde00\AppData\Local\Temp\tmp_5kjnp36\project\STATS.txt has been updated successfully. (file state is current in your context — no need to Read it back)

**assistant [Read]**: 
> 1	15 ./api.py
2	 12 ./demo.py
3	  4 ./README.md
4	 31 total

**assistant**: Done! Created `STATS.txt` with line counts for all files, sorted largest first:

| File | Lines |
|---|---|
| `./api.py` | 15 |
| `./demo.py` | 12 |
| `./README.md` | 4 |
| **Total** | **31** |

**user**: thanks, that works.
