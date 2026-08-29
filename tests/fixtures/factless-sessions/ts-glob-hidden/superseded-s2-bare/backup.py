import shutil
import os
import sys

def main():
    source = os.path.join(os.path.dirname(os.path.abspath(__file__)), "project")
    dest = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backups", "project")
    
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    
    if os.path.exists(dest):
        shutil.rmtree(dest)
    
    shutil.copytree(source, dest)
    print(f"Backup complete: {source} -> {dest}")

if __name__ == "__main__":
    main()
