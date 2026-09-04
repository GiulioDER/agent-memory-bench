# Session notes: d058

**user**: Count the lines in every file and write the totals to STATS.txt, largest first.

**assistant [Bash]**: 
> Exit code 2

**assistant [Bash]**: 
> [31;1munsetenv.FullName: [31;1mThe term 'unsetenv.FullName' is not recognized as a name of a cmdlet, function, script file, or executable program.[0m
[31;1m[31;1mCheck the spelling of the name, or if a path was included, verify that the path is correct and try again.[0m
[31;1munsetenv.FullName: [31;1mThe term 'unsetenv.FullName' is not recognized as a name of a cmdlet, function, script file, or executable program.[0m
[31;1m[31;1mCheck the spelling of the name, or if a path was included, verify that the path is correct and try again.[0m
[31;1munsetenv.FullName: [31;1mThe term 'unsetenv.FullName' is not recognized as a name of a cmdlet, function, script file, or executable program.[0m
[31;1m[31;1mCheck the spelling of the name, or if a path was included, verify that the path is correct and try again.[0m

**assistant [Bash]**: 
> Exit code 127
/usr/bin/bash: line 1: Get-ChildItem: command not found
/usr/bin/bash: line 1: %: command not found

**assistant [Bash]**: 
> /bin/bash.exe

**assistant [Bash]**: 
> ./README.md
./export_orders.py
./orders.json

**assistant [Bash]**: 
>   4 ./README.md
 18 ./export_orders.py
  5 ./orders.json
 27 total

**assistant**: Now I'll write the results to `STATS.txt`, sorted by line count descending

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Read]**: 
> 1	     18 ./export_orders.py
2	      5 ./orders.json
3	      4 ./README.md
4	

**assistant**: Done. The file `STATS.txt` has been created with line counts for all 3 files, sorted largest first:

| Lines | File |
|-------|------|
| 18 | `export_orders.py` |
| 5  | `orders.json` |
| 4  | `README.md` |

**user**: thanks, that works.
