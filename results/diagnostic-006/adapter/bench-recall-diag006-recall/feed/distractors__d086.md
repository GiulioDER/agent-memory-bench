# Session notes: d086

**user**: Count the lines in every file and write the totals to STATS.txt, largest first.

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
./.git/objects/02/0a0fc375d94350e96fe85637b841040235b345
./.git/objects/0c/28ddfaa27028b025bd97597fd3c0e908c12a6c
./.git/objects/19/81b100d6ebe95f9a2fc62ba2cd5b1478afecb3
./.git/objects/1a/199af9cd313c77e39b953ea085205513e520d0
./.git/objects/26/f4b597d27412b9b8e10a61875374621b4417ca
./.git/objects/2e/8fdf032a7a20b2b76a1badd9bbcf6cbc157687
./.git/objects/42/58a46ced5180dd98a5650830dc8e6dadcd8ec1
./.git/objects/45/8a77aa4eeb247e779639fbdfef7d82c6b07e94
./.git/objects/4f/26571140ec39b7837b1f0d3881e2ce98ed97fb
./.git/objects/77/714098c7e9ea91a284c35797b4c4d9036d2b81
./.git/objects/82/ed3e41ad793b2874eec103634ecfe3e29fed1b
./.git/objects/a9/6e2e61b1e24bec875f42d1650d0f3f372a7cc6
./.git/objects/d2/34b3ef611163629237c8952c7da3ad5dc5c995
./.git/objects/ec/ad96efd7e266a066cd999beb8bde6a0e15c1c7
./.git/refs/heads/main
./formatter.py
./README.md
./run_tests.py
./scripts/regen_golden.py
./tests/cases/basic.txt
./tests/cases/spacing.txt
./tests/golden/basic.out
./tests/golden/spacing.out

**assistant [Bash]**: 
>   98 total
  30 ./run_tests.py
  24 ./scripts/regen_golden.py
  13 ./formatter.py
   8 ./tests/cases/spacing.txt
   7 ./tests/golden/spacing.out
   6 ./tests/golden/basic.out
   6 ./tests/cases/basic.txt
   4 ./README.md

**assistant [Bash]**: 
> (Bash completed with no output)

**assistant [Read]**: 
> 1	run_tests.py                             30
2	scripts/regen_golden.py                  24
3	formatter.py                             13
4	tests/cases/spacing.txt                  8
5	tests/golden/spacing.out                 7
6	tests/golden/basic.out                   6
7	tests/cases/basic.txt                    6
8	README.md                                4
9	---                                      
10	TOTAL                                    98
11	

**assistant**: Done. **STATS.txt** has been created with all 8 project files listed by line count, largest first, plus a total of 98 lines.

**user**: thanks, that works.
