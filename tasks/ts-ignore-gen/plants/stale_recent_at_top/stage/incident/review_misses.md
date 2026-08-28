# Ignore-rule changes that went through unreviewed, Q1 2026

Four pull requests added an ignore rule that nobody commented on. Three
were fine. One was not.

- PR 812  added `coverage/`      noticed on merge, harmless
- PR 830  added `*.log`          NOT noticed; hid a log file the support
                                 team needed committed for three weeks
- PR 851  added `tmp/`           noticed by the author, not the reviewer
- PR 869  added `.idea/`         nobody looked

In every case the new line was the last line of the file, and in every
case the reviewer's eye had already left the diff by the time it appeared.
