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
if max(delays) < 20.0:
    print(f"VERDICT NEVER_GREW {delays}")
    sys.exit(9)
if len({round(delay, 6) for delay in delays}) < 3:
    print(f"VERDICT CONSTANT_DELAY {delays}")
    sys.exit(10)
first_half = delays[: len(delays) // 2]
second_half = delays[len(delays) // 2 :]
if sum(second_half) / len(second_half) <= sum(first_half) / len(first_half):
    print(f"VERDICT NOT_GROWING {delays}")
    sys.exit(11)
print("VERDICT BACKOFF_OK")
