# Session notes: p01

**user**: Release 142 deployed clean on staging and fell over on prod-web1, leaving stray directories behind (ops/prod_deploy_142.log; ops/release_dirs_note.txt explains how prod names its release dirs). Reproduce the failure locally with a release dir shaped like prod's, explain exactly what deploy.sh does wrong, and state the rule our deploy scripts must follow so any release directory name works.

**assistant [Read]**: 
> 1	Prod release directories are named from the launch calendar by the release
2	tooling; the current campaign directory is '/srv/releases/June Launch/'.
3	Staging uses plain '/srv/releases/rel-NNN', which is why staging stays green.
4	

**assistant [Read]**: 
> 1	release 142 deploy to prod-web1, 2026-06-22 02:11 -- FAILED (exit 1)
2	
3	$ bash -x deploy.sh "/srv/releases/June Launch/rel-142"
4	+ set -euo pipefail
5	+ TARGET='/srv/releases/June Launch/rel-142'
6	+ mkdir -p /srv/releases/June Launch/rel-142/app
7	+ cp app/main.py /srv/releases/June Launch/rel-142/app/
8	cp: -r not specified; omitting directory '/srv/releases/June'
9	
10	left behind on prod-web1: directory '/srv/releases/June' and, relative to the
11	checkout, 'Launch/rel-142/app/' containing main.py. The staging deploy of the
12	same tag succeeded (staging release dir: /srv/releases/rel-142).
13	

**assistant [Bash]**: 
> ./app/main.py
./deploy.sh

**assistant [Read]**: 
> 1	#!/usr/bin/env bash
2	set -euo pipefail
3	
4	TARGET=$1
5	
6	mkdir -p $TARGET/app
7	cp app/main.py $TARGET/app/
8	echo "deployed app to $TARGET"
9	

**assistant [Read]**: 
> 1	"""Entry point for the shipped site."""
2	
3	print("site up")
4	

**assistant**: Let me reproduce the failure

**assistant [Bash]**: 
> ++ TARGET='/srv/releases/June Launch/rel-142'
++ mkdir -p /srv/releases/June Launch/rel-142/app
mkdir: cannot create directory '/srv': Permission denied
++ echo '--- ls after mkdir ---'
--- ls after mkdir ---
++ ls -la /srv/releases/June/
++ echo 'No /srv/releases/June/'
No /srv/releases/June/
++ ls -la Launch/rel-142/app/
total 0
drwxr-xr-x 1 gde00 197609 0 Aug 23 21:33 .
drwxr-xr-x 1 gde00 197609 0 Aug 23 21:33 ..
++ echo '--- now test cp ---'
--- now test cp ---
++ cp app/main.py /srv/releases/June Launch/rel-142/app/
cp: cannot stat '/srv/releases/June': No such file or directory
++ echo 'result: 1'
result: 1
+ pwd -P

**assistant [Bash]**: 
> cleaned up

**assistant [Bash]**: 
> === 1. mkdir -p with UNQUOTED TARGET ===
Directory tree after mkdir:
srv_deploy_test
srv_deploy_test/releases
srv_deploy_test/releases/June

=== 2. Now cp with UNQUOTED TARGET ===
cp: -r not specified; omitting directory 'srv_deploy_test/releases/June'
cp exit code: 1
Shell cwd was reset to C:\Users\gde00\AppData\Local\Temp\tmp1xmuqc61\project

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Bash]**: 
> /tmp/srv_deploy_test
/tmp/srv_deploy_test/releases
/tmp/srv_deploy_test/releases/June

**assistant [Bash]**: 
> /tmp/Launch
/tmp/Launch/rel-142
---

**assistant [Bash]**: 
> /tmp/Launch
/tmp/Launch/rel-142
/tmp/Launch/rel-142/app

**assistant [Bash]**: 
> cleaned up

**assistant**: Here's the full explanation:

---

## What `deploy.sh` does wrong — line by line

The script's `TARGET` variable is **never quoted**. When called as:

```bash
bash deploy.sh "/srv/releases/June Launch/rel-142"
```

Shell parameter expansion happens before word splitting, so every use of `$TARGET` gets split on whitespace.

### Line 6: `mkdir -p $TARGET/app`

The shell expands this to **two separate arguments**:

```
mkdir -p /srv/releases/June Launch/rel-142/app
```

- `mkdir -p /srv/releases/June` → creates `/srv/releases/June/`
- `mkdir -p Launch/rel-142/app` → creates `Launch/rel-142/app/` **relative to CWD**

Instead of a single tree `/srv/releases/June Launch/rel-142/app/`, you get two disjoint directories:

| Path | What it is |
|---|---|
| `/srv/releases/June/` | Stray — first half of the split |
| `Launch/rel-142/app/` | Stray — second half of the split, created in the wrong place |

### Line 7: `cp app/main.py $TARGET/app/`

Expands to:

```
cp app/main.py /srv/releases/June Launch/rel-142/app/
```

`cp` interprets three destination arguments. The first one is `/srv/releases/June/` (now a directory thanks to the previous `mkdir -p`), and `cp` refuses to copy a file *into* a directory without `-r`, producing:

```
cp: -r not specified; omitting directory '/srv/releases/June'
```

and exits 1.

### Staging worked because...

Staging uses `/srv/releases/rel-142` — **no spaces**. Word splitting is a no-op, so the bug stays hidden.

---

## The fix: always quote variable expansions

The rule is simple and absolute:

> **All shell variable expansions used as path arguments must be double-quoted.**

Apply it to both lines:

```diff
- mkdir -p $TARGET/app
+ mkdir -p "$TARGET"/app

- cp app/main.py $TARGET/app/
+ cp app/main.py "$TARGET"/app/
```

Or more idiomatically:

```bash
mkdir -p "$TARGET/app"
cp app/main.py "$TARGET/app/"
```

This prevents word splitting on spaces (or any other `IFS` character) and ensures the path is treated as a single argument regardless of its contents.

**user**: That's the one. Decision: quote every path expansion in deploy.sh and in every deploy script. Prod hosts have spaces in directory names, and an unquoted variable goes through word splitting, so $TARGET must always appear as "$TARGET", and the same for every other path variable. Fix the script's existing lines as well, and treat an unquoted expansion in a deploy script as a review blocker.
