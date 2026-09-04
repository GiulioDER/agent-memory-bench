# Session notes: d076

**user**: Count the lines in every file and write the totals to STATS.txt, largest first.

**assistant [Bash]**: 
> ./.git/COMMIT_EDITMSG
./.git/HEAD
./.git/config
./.git/description
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
./.git/objects/06/29587580ddfbd89955d92e6a85638cc799d48f
./.git/objects/14/ed29ce54b40944d35f6be40dbb6ba4f3cb8434
./.git/objects/80/e49879e726568b165be2fb1a91160be527fede
./.git/objects/c9/bc5b24f56e1e4bfbf827644c0560332f27e0b9
./.git/refs/heads/main
./README.md
./metrics.log

**assistant [Bash]**: 
>   3 README.md
  7 metrics.log
 10 total

**assistant [Edit]**: 
> The file C:\Users\gde00\AppData\Local\Temp\tmp9qr468ji\project\STATS.txt has been updated successfully. (file state is current in your context — no need to Read it back)

**assistant**: Done. Here's what `STATS.txt` contains (largest first):

```
7 metrics.log
  3 README.md
```

**user**: thanks, that works.
