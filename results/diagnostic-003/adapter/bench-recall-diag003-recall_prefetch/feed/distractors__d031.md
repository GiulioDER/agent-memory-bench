# Session notes: d031

**user**: Count the lines in every file and write the totals to STATS.txt, largest first.

**assistant**: I'll explore the project structure, count lines in every file, and write the results sorted largest-first to STAT

**assistant [Bash]**: 
> ./.git/COMMIT_EDITMSG
./.git/config
./.git/description
./.git/HEAD
./.git/hooks/applypatch-msg.sample
./.git/hooks/commit-msg.sample
./.git/hooks/fsmonitor-watchman.sample
./.git/hooks/post-update.sample
./.git/hooks/pre-applypatch.sample
./.git/hooks/pre-commit.sample
./.git/hooks/pre-merge-commit.sample
./.git/hooks/pre-push.sample
./.git/hooks/pre-rebase.sample
./.git/hooks/pre-receive.sample
./.git/hooks/prepare-commit-msg.sample
./.git/hooks/push-to-checkout.sample
./.git/hooks/sendemail-validate.sample
./.git/hooks/update.sample
./.git/index
./.git/info/exclude
./.git/logs/HEAD
./.git/logs/refs/heads/main
./.git/objects/05/0ef6e43397c291fbefc8daada1edd97fdca1b9
./.git/objects/2d/afe5fe46357fcf64e17be736542118efe0dddf
./.git/objects/50/7b67b8dce751dea183787eabf816f7b00dd7c6
./.git/objects/53/39783ec2953f81cfb802bfe3410cc50e380758
./.git/objects/98/21397174beb569cf8817ab76c72369a464e301
./.git/objects/f6/8c71a60e22f89ad72a470946f11b647011a52b
./.git/refs/heads/main
./data/acme.csv
./data/blue.csv
./README.md

**assistant**: Good. The non-.git files are `README.md`, `data/acme.csv`, and `data/blue.csv`. Let me count lines in each.



**assistant [Bash]**: 
>   4 README.md
  3 data/acme.csv
  2 data/blue.csv
  9 total

**assistant**: Now I'll write the results to `STATS.txt`, sorted largest first.



**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Read]**: 
> 1	  4 README.md
2	  3 data/acme.csv
3	  2 data/blue.csv
4	

**assistant**: Done! Here's what was written to **STATS.txt** (sorted largest first):

| Lines | File |
|-------|------|
| 4 | `README.md` |
| 3 | `data/acme.csv` |
| 2 | `data/blue.csv` |

**user**: thanks, that works.
