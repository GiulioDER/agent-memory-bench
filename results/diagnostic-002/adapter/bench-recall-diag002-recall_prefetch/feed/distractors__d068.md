# Session notes: d068

**user**: Count the lines in every file and write the totals to STATS.txt, largest first.

**assistant**: Let me explore the project structure

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
./.git/objects/01/677acf43a6008af0499b2ce20718192dd2ff6e
./.git/objects/92/01aab3fce14d304019134fb0abb6bf1afbef8b
./.git/objects/9b/848d08bc88790ce847c40b62058594ba0447c6
./.git/objects/ad/d76f46564e1483264b6a761556557a7c10b476
./.git/objects/bc/8bbd279fdfa777e62eda4c972c949cf0d22276
./.git/objects/d4/e9119d5f0cea550a31211d95703775752a67d4
./.git/refs/heads/main
./docs/intro.txt
./docs/menu.txt
./README.md

**assistant**: Let me exclude .git files and count lines in each project file:



**assistant [Bash]**: 
>   6 total
  4 ./README.md
  1 ./docs/menu.txt
  1 ./docs/intro.txt

**assistant**: Now let me write the results to STATS.txt

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Read]**: 
> 1	  6 total
2	  4 ./README.md
3	  1 ./docs/menu.txt
4	

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Read]**: 
> 1	  6 total
2	  4 ./README.md
3	  1 ./docs/menu.txt
4	  1 ./docs/intro.txt
5	

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Read]**: 
> 1	  4 ./README.md
2	  1 ./docs/menu.txt
3	  1 ./docs/intro.txt
4	  0 ./STATS.txt
5	

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Read]**: 
> 1	  4 ./README.md
2	  1 ./docs/menu.txt
3	  1 ./docs/intro.txt
4	

**assistant**: Done! `STATS.txt` has been created with the line counts sorted largest first:

```
     4 ./README.md
     1 ./docs/menu.txt
     1 ./docs/intro.txt
```

**user**: thanks, that works.
