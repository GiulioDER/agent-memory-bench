"""Does lineage-filtered evidence produce better answers? 11 tasks x 2 corpora.

No treatment change and no agent involved. The mechanism is that only verdict-ok hits enter
recall's evidence bundle, so on the declared-lineage corpus the stale document is excluded from
what a generator sees, while on the control both versions arrive as peers. Same question, same
model, two bundles.

Uses only paths verified on 2026-08-31: the arm's own _server_env, `recall search --evidence`,
and PR #553's OpenAI-compatible provider against OpenRouter.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, ".")
from recall.answer_provider import resolve_answer_provider

from adapters.recall.adapter import RecallAdapter

PAIRS = [("bench-lineage-t0-superseded", "t0"), ("bench-lineage-t2-superseded", "t2")]
adapter = RecallAdapter(Path("results/.diag"), Path("corpus/README.md"))
provider = resolve_answer_provider()
assert provider is not None, "answer provider did not resolve; check RECALL_REASONING_ANSWER_*"

root = Path("corpus/conditions/superseded/seed-1/sessions")
tasks = sorted(p.name for p in root.iterdir() if p.is_dir() and (p / "p01.jsonl").exists())
print("tasks:", len(tasks))

HIT = re.compile(r"^\s{2}(\w+)\s+conf=([\d.]+)\s+cos=([\d.]+)\s+(\S+)")
out = []
for task in tasks:
    stale = [p.name for p in (root / task).glob("stale_*.jsonl")]
    if not stale:
        continue
    q = task.replace("ts-", "").replace("-", " ")
    row = {"task": task, "query": q}
    for tenant, label in PAIRS:
        env = adapter._server_env(tenant)
        r = subprocess.run(
            [sys.executable, "-m", "recall.cli", "--tenant", tenant, "search", "-k", "6",
             "--evidence", q],
            env=env, capture_output=True, text=True, timeout=180, check=False)
        verdicts, bundle = {}, ""
        for line in r.stdout.splitlines():
            m = HIT.match(line)
            if m:
                verdicts[m.group(1)] = verdicts.get(m.group(1), 0) + 1
        s = r.stdout.strip()
        i = s.find("{")
        if i >= 0:
            try:
                payload = json.loads(s[i:])
                bundle = json.dumps(payload)[:6000]
            except Exception:  # noqa: BLE001 - a malformed payload is data, not a crash
                bundle = s[i:i + 6000]
        ans, err = None, None
        if bundle:
            try:
                ans = str(provider(
                    "Answer ONLY from the evidence. Be one sentence.",
                    "Evidence:\n" + bundle + "\n\nQuestion: what is the CURRENT convention for "
                    + q + "?"))[:400]
            except Exception as e:  # noqa: BLE001 - a provider error is recorded, not raised
                err = f"{type(e).__name__}: {str(e)[:200]}"
        row[label] = {"verdicts": verdicts, "answer": ans, "error": err,
                      "bundle_chars": len(bundle)}
    out.append(row)
    print(json.dumps(row)[:400])

Path("results/reasoning-diag.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"\nwrote results/reasoning-diag.json  rows={len(out)}")
for r in out:
    t0 = r.get("t0", {})
    t2 = r.get("t2", {})
    print(f"  {r['task']:<22} t0 {t0.get('verdicts')!s:<28} | t2 {t2.get('verdicts')}")
