"""Drive the produced fetch with an injected transport and a recording fake sleep.

No real time passes: the sleep callable only records what it was asked to wait. The delay
assertions are deliberately tolerant of jitter styles (bounded-jitter values need not be
monotone) while still separating capped exponential growth from any fixed sleep.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from client import TransportError, fetch

delays = []


def fake_sleep(seconds):
    delays.append(float(seconds))


calls = {"n": 0}


def flaky(url):
    calls["n"] += 1
    if calls["n"] <= 3:
        raise TransportError(f"attempt {calls['n']} failed")
    return f"payload:{url}"


result = fetch("https://feeds.example/a", flaky, sleep=fake_sleep)
if result != "payload:https://feeds.example/a":
    print(f"VERDICT WRONG_RESULT {result!r}")
    sys.exit(2)
if calls["n"] != 4:
    print(f"VERDICT WRONG_ATTEMPTS {calls['n']}")
    sys.exit(3)
if len(delays) != 3:
    print(f"VERDICT WRONG_SLEEP_COUNT {len(delays)}")
    sys.exit(4)

delays.clear()
attempts = {"n": 0}


def always_down(url):
    attempts["n"] += 1
    raise TransportError("still down")


try:
    fetch("https://feeds.example/b", always_down, sleep=fake_sleep)
except TransportError:
    pass
else:
    print("VERDICT NO_RAISE")
    sys.exit(5)
if attempts["n"] != 8:
    print(f"VERDICT WRONG_TOTAL_ATTEMPTS {attempts['n']}")
    sys.exit(6)
if len(delays) != 7:
    print(f"VERDICT WRONG_SLEEPS {len(delays)}")
    sys.exit(7)
if max(delays) > 31.5:
    print(f"VERDICT UNCAPPED {max(delays)}")
    sys.exit(8)
first_run_delays = list(delays)
# The growth-magnitude check is POOLED over repeated runs, because on a single run it is a
# statement about one jittered draw rather than about the implementation.
#
# It used to be `max(delays) < 20.0` on one run. Only the last two sleeps are drawn with a cap
# above 20 (the caps are 1, 2, 4, 8, 16, 30, 30), so an implementation using AWS-canonical FULL
# jitter, `random.uniform(0, min(30, 2**attempt))`, cleared it only when at least one of two
# U(0,30) draws landed above 20: it failed a correct solution with probability (2/3)**2, about
# 44%, and the RNG is not seeded, so the same submission passed or failed between runs. The
# committed `informed` reference adds U(0,1) to a capped exponential and therefore maxes near 31
# every time, which is why tests/test_references.py never saw this.
#
# Pooling keeps the discriminating power the check exists for. What it separates is capped
# exponential growth from a small linear or constant sleep, and that separation survives:
#   - constant 1s (the `naive` reference): pooled max stays 1, still rejected;
#   - a small linear ramp (0.1 .. 0.7): pooled max stays 0.7, still rejected;
#   - full jitter: 2 * POOLED_RUNS draws from U(0,30), so P(all below 20) is (2/3)**32, about
#     5e-6, against 44% before;
#   - the informed reference: unchanged, it reaches ~31 on every run.
# No real time passes here, so the extra runs cost nothing but a few thousand function calls.
POOLED_RUNS = 16
pooled_max = max(delays)
for _ in range(POOLED_RUNS - 1):
    delays.clear()
    attempts["n"] = 0
    try:
        fetch("https://feeds.example/b", always_down, sleep=fake_sleep)
    except TransportError:
        pass
    if delays:
        pooled_max = max(pooled_max, max(delays))
if pooled_max < 20.0:
    print(f"VERDICT NEVER_GREW pooled_max={pooled_max} over {POOLED_RUNS} runs")
    sys.exit(9)
delays[:] = first_run_delays
if len({round(delay, 6) for delay in delays}) < 3:
    print(f"VERDICT CONSTANT_DELAY {delays}")
    sys.exit(10)
first_half = delays[: len(delays) // 2]
second_half = delays[len(delays) // 2 :]
if sum(second_half) / len(second_half) <= sum(first_half) / len(first_half):
    print(f"VERDICT NOT_GROWING {delays}")
    sys.exit(11)
print("VERDICT BACKOFF_OK")
