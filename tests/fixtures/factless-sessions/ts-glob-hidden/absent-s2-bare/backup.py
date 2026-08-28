#!/usr/bin/env python3
import shutil
import os

src_dir = os.path.join(os.getcwd(), 'project')
dst_dir = os.path.join(os.getcwd(), 'backups', 'project')

os.makedirs(os.path.dirname(dst_dir), exist_ok=True)
shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)

print(f"Copied '{src_dir}' to '{dst_dir}'")
