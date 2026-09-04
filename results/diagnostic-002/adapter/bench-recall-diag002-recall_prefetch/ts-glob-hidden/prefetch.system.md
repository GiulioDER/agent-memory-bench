Project memory:

[Evidence item]
# Session notes: p01

**user**: We rebuilt the parcel host from the pre-release backup after Friday's bad disk, and the service came up with no production credentials: project/.env.production was not in the restore. The copy we restored from is preserved under incident/restore_2026-07-25/project/ and the backup helper that made it is incident/backup_old.py. Compare that restore copy against project/ as it stands, list everything the backup was missing, explain why exactly those files were skipped, and recommend what the backup procedure must guarantee so this cannot recur.

**assistant [Bash]**: 
> """Pre-release backup helper, as run on 2026-07-24. Kept for the restore investigation."""

import glob
import os
import shutil

Recorded: 2026-08-25 21:10:44.897455+00:00
Status: current
Source: sessions__ts-glob-hidden__p01.md
[/Evidence item]

[Evidence item]
def main():
    print("parcel service ready")

if __name__ == "__main__":
    main()

**assistant**: Now I have the full picture. Here's the analysis.

---

## Comparison: Restore Copy vs. Current `project/`

| Item | In Backup? | In Current? | Status |
|---|---|---|---|
| `project/.editorconfig` | **NO** | Yes | Missing from backup |
| `project/.env.production` | **NO** | Yes | Missing from backup |
| `project/config.ini` | Yes | Yes | Identical |
| `project/notes.md` | Yes | Yes | Content differs (post-backup edit) |
| `project/src/main.py` | Yes | Yes | Content differs (post-backup edit) |

The backup script **never captured** `.editorconfig` or `.env.production`. The other two files were captured but changed after the backup ran — that's expected point-in-time behavior.

---

Recorded: 2026-08-25 21:10:44.897455+00:00
Status: current
Source: sessions__ts-glob-hidden__p01.md
[/Evidence item]

[Evidence item]
**assistant [Read]**: 
> 1	# partnerfeed
2	
3	Partner uploads land as CSV files under `data/`, all sharing the columns `id,name,qty`.
4	Merge tooling in the repository root combines them for import.
5

**assistant**: Now I have a clear picture. Let me create the `DATA.md` file.

**assistant [Edit]**: 
> The file C:\Users\gde00\AppData\Local\Temp\tmpt9bydpoa\project\DATA.md has been updated successfully. (file state is current in your context — no need to Read it back)

**assistant**: Let me verify the file was created correctly.

Recorded: 2026-08-25 21:03:59.169085+00:00
Status: current
Source: distractors__d007.md
[/Evidence item]

[Evidence item]
os.makedirs(os.path.join("backups", "project"), exist_ok=True)
for entry in glob.glob(os.path.join("project", "*")):
    destination = os.path.join("backups", entry)
    if os.path.isdir(entry):
        shutil.copytree(entry, destination, dirs_exist_ok=True)
    else:
        shutil.copy2(entry, destination)
print("backup complete")

**assistant [Bash]**: 
> total 2
drwxr-xr-x 1 gde00 197609  0 Aug 23 21:16 .
drwxr-xr-x 1 gde00 197609  0 Aug 23 21:16 ..
-rw-r--r-- 1 gde00 197609 36 Aug 23 21:16 config.ini
-rw-r--r-- 1 gde00 197609 79 Aug 23 21:16 notes.md
drwxr-xr-x 1 gde00 197609  0 Aug 23 21:16 src

Recorded: 2026-08-25 21:10:44.897455+00:00
Status: current
Source: sessions__ts-glob-hidden__p01.md
[/Evidence item]

[Evidence item]
**assistant**: Now I have a full picture of the repo's formatting. Let me write the `.editorconfig`

**assistant [Read]**: 
> File does not exist. Note: your current working directory is C:\Users\gde00\AppData\Local\Temp\tmpp_z1samh\project.

**assistant [Edit]**: 
> The file C:\Users\gde00\AppData\Local\Temp\tmpp_z1samh\project\.editorconfig has been updated successfully. (file state is current in your context — no need to Read it back)

**assistant [Read]**: 
> 1	root = true
2	
3	[*]
4	end_of_line = lf
5	charset = utf-8
6	trim_trailing_whitespace = true
7	insert_final_newline = true
8	indent_style = space
9	indent_size = 4
10	
11	[*.md]
12	trim_trailing_whitespace = false

**assistant**: The `.editorconfig` is created. Here's the rationale based on the existing files:

Recorded: 2026-08-25 21:07:57.759623+00:00
Status: current
Source: distractors__d067.md
[/Evidence item]

# Project notes

You are working in this repository. Keep changes small and leave the tree clean.

# parcel shipping tools

Release helpers for the parcel service. `project/` holds the working tree that gets backed up
before each release; the helper scripts live in the repository root.
