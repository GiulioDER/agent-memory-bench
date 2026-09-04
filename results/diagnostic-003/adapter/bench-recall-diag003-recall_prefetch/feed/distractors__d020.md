# Session notes: d020

**user**: Count the lines in every file and write the totals to STATS.txt, largest first.

**assistant**: I'll start by exploring the project structure to find all files and count their

**assistant [Bash]**: 
> ./README.md
./docs/intro.txt
./docs/menu.txt

**assistant [Bash]**: 
> ./README.md
./docs/intro.txt
./docs/menu.txt

**assistant**: Let me check if there's any other files I might be missing, and then count lines in all of

**assistant [Bash]**: 
>   1 ./docs/intro.txt
  1 ./docs/menu.txt
  4 ./README.md
  6 total

**assistant**: Now I'll write the results to `STATS.txt`, sorted largest first.



**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Read]**: 
> 1	     4 ./README.md
2	     1 ./docs/intro.txt
3	     1 ./docs/menu.txt
4	

**assistant**: Done. Here's a summary of what was written to `STATS.txt`:

| File | Lines |
|------|-------|
| `./README.md` | 4 |
| `./docs/intro.txt` | 1 |
| `./docs/menu.txt` | 1 |

The entries are sorted largest first. There were 3 files found in total, with 6 lines across all files.

**user**: thanks, that works.
