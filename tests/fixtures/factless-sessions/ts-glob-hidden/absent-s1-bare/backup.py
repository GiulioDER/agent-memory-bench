import os
import shutil

src = os.path.join(os.getcwd(), "project")
dst = os.path.join(os.getcwd(), "backups", "project")

os.makedirs(os.path.dirname(dst), exist_ok=True)
shutil.copytree(src, dst, dirs_exist_ok=True)
