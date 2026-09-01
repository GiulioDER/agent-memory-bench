"""Preregistration 023's non-optional guard.

A Tier 2 search must return at least one hit with verdict == "superseded". Without it a silently
unparsed frontmatter block reproduces Tier 0 byte for byte, and the run would be reported as
"lineage does not help" rather than as a broken render. Exits non-zero so the chain stops here.

Three things this gets right that earlier versions got wrong, each found by reading real output
rather than assuming a shape:

* It uses `RecallAdapter._server_env`, the arm's OWN environment. The corpus-build helper's env
  routes to the legacy chunks table and prints `generation=legacy`, so a guard using it could
  pass or fail on rows no session ever sees.
* It parses the TEXT listing, not the `--evidence` JSON bundle. `recall search --help` states
  only verdict-ok hits enter the bundle, so a superseded hit is by definition absent from it and
  a bundle-parsing guard could never observe the thing it exists to check.
* It separates APPARATUS failure from a lineage verdict. The first version reported "no
  frontmatter was parsed" when every search had actually died on a missing VOYAGE_API_KEY. A
  broken apparatus that renders as a finding is the exact failure this guard exists to prevent,
  so it must not commit that failure itself.
"""
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, ".")
from adapters.recall.adapter import RecallAdapter

TENANT = sys.argv[1] if len(sys.argv) > 1 else "bench-lineage-t2-superseded"
EXPECT = sys.argv[2] if len(sys.argv) > 2 else "superseded"   # or "none" for a control tenant
QUERIES = [
    "semver pin compatible release operator",
    "base36 id lowercase increment",
    "timezone dubai local timestamps",
    "migration filename prefix convention",
    "golden file manual footer regeneration",
]
HIT = re.compile(r"^\s{2}(\w+)\s+conf=([\d.]+)\s+cos=([\d.]+)\s+(\S+)")
META = re.compile(r"valid_from=(\S+)")

adapter = RecallAdapter(Path("results/.guard-staging"), Path("corpus/README.md"))
env = adapter._server_env(TENANT)

verdicts, superseded, lineage_seen, total, ok_searches = {}, [], 0, 0, 0
for q in QUERIES:
    cmd = [sys.executable, "-m", "recall.cli", "--tenant", TENANT, "search", "-k", "5", q]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=180, check=False)
    if r.returncode != 0:
        print(f"  ! search failed for {q!r}: {r.stderr[-300:]}")
        continue
    ok_searches += 1
    print()
    print(f"  query: {q}")
    for line in r.stdout.splitlines():
        m = HIT.match(line)
        if m:
            v, conf, cos, src = m.groups()
            total += 1
            verdicts[v] = verdicts.get(v, 0) + 1
            print(f"    {v:<15} conf={conf} cos={cos}  {src}")
            if v == "superseded":
                superseded.append((q, src))
        vm = META.search(line)
        if vm and vm.group(1) != "-":
            lineage_seen += 1

print()
print(
    f"  searches ok={ok_searches}/{len(QUERIES)}  hits={total}  verdicts={verdicts}  "
    f"hits with a real valid_from={lineage_seen}"
)
print(f"  superseded hits: {len(superseded)}")
for q, src in superseded[:6]:
    print(f"    {q[:36]:<36} {src}")

if ok_searches == 0:
    print()
    print("  APPARATUS FAILED: not one search completed, so this run says NOTHING about lineage.")
    print("  Do not read it as a guard result. Fix the search first.")
    sys.exit(2)

if EXPECT == "none":
    ok = lineage_seen == 0 and not superseded
    print()
    print("  CONTROL %s: expected no lineage on this tenant." % ("OK" if ok else "UNEXPECTED"))
    sys.exit(0 if ok else 3)

if lineage_seen == 0:
    print()
    print("  GUARD FAILED: every hit reported valid_from=-, so no frontmatter was parsed at all.")
    sys.exit(1)
if not superseded:
    print()
    print("  GUARD FAILED: frontmatter parsed, but no hit carried verdict == 'superseded'.")
    print("  Tier 2 would be Tier 0 with extra fields and no comparison would mean anything.")
    sys.exit(1)
print()
print("  GUARD PASSED: recall parses declared lineage and demotes the stale plant.")
