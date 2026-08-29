import os

reports_dir = "reports"
files = sorted(os.listdir(reports_dir), key=lambda f: int(f.split("-")[1].split(".")[0]))
for f in files:
    print(f)
