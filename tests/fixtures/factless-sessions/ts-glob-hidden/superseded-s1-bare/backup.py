#!/usr/bin/env python3
import shutil
import os

def main():
    src = os.path.join(os.getcwd(), 'project')
    dst = os.path.join(os.getcwd(), 'backups', 'project')
    shutil.copytree(src, dst, dirs_exist_ok=True)
    print(f"Copied {src} -> {dst}")

if __name__ == '__main__':
    main()
