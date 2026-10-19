---
title: KeyError Crash When Polling Loop Runs Before Dict Is Fully Initialized
date: 2026-04-13
category: docs/solutions/runtime-errors
module: crunchtime-alerts
problem_type: runtime_error
component: tooling
severity: critical
symptoms:
  - "Process crashes with KeyError: 'quarter' on first ESPN timeout or network error"
  - "Crash occurs outside any try/except — process terminates entirely with no recovery"
  - "Reproducible on any transient network failure during the first poll cycle"
root_cause: logic_error
resolution_type: code_fix
related_components:
  - nba_alerts.py
  - main.py
tags:
  - keyerror
  - sentinel-values
  - dict-initialization
  - polling-loop
  - python
  - defensive-initialization
  - is-completed
---

# KeyError Crash When Polling Loop Runs Before Dict Is Fully Initialized

## Problem

`set_games()` built game dicts with only `time`, `away_full`, `home_full`, and `url` keys. `is_completed()` and `check_for_new_alerts()` accessed `game['quarter']`, `game['clock']`, and `game['score']` unconditionally. If a network error prevented `update_games()` from populating live data on the first poll, the `while not is_completed(nba_games)` condition crashed immediately with an uncaught `KeyError: 'quarter'`, terminating the process.

## Symptoms

- `KeyError: 'quarter'` crash on the first ESPN timeout or connection error
- The crash occurs outside any `try/except` block — it terminates the entire process with a traceback
- Reproducible by blocking network access after `set_games()` succeeds at startup

## What Didn't Work

**Attempt 1 — Guard inside `is_completed()`:**

Adding `if 'quarter' not in game: return False` to `is_completed()` was considered. Rejected because it treats a symptom rather than the root cause: the game dict itself is structurally incomplete at construction time.

**Attempt 2 — Remove the priming call (session history):**

A "priming" `send_alerts()` call existed before the while loop, intended to pre-populate game state before the guard condition evaluated. The first fix attempt was to simply remove this priming call, reasoning that eliminating the pre-loop call would prevent `is_completed()` from being called with incomplete dicts.

This was insufficient. The `while not is_completed(nba_games)` condition is evaluated at the top of the loop's *first iteration* — before `update_games()` ever runs. Removing the priming call did not change this ordering: `nba_games` still contained only the keys from `set_games()` on the first pass, and `is_completed()` still crashed on `game['quarter']`. (session history)

## Solution

Initialize all expected keys in `set_games()` with sentinel values that are safe for downstream consumers to read before live data arrives:

```python
# nba_alerts.py — set_games() initializes complete dict at construction time
games[(away_team, home_team)] = {
    'time': event['status']['type']['shortDetail'].split('-')[1][1:],
    'away_full': away['team']['displayName'].replace(' ', '-').replace('LA', 'Los-Angeles'),
    'home_full': home['team']['displayName'].replace(' ', '-').replace('LA', 'Los-Angeles'),
    # Sentinel values — safe for is_completed() and check_for_new_alerts()
    # before update_games() runs on the first poll cycle
    'score': (0, 0),
    'quarter': 0,
    'clock': 9999.0,
    'displayClock': '',
}
```

```python
# main.py — remove the redundant priming call before the while loop
# BEFORE (crash path — if this raised, nba_games stayed stale):
try:
    nba_games, nba_alerted = nba_alerts.send_alerts(client, nba_games, nba_alerted)
except (RequestException, KeyError, ValueError) as e:
    logging.warning('Error during game update cycle: %s', e)

while not nba_alerts.is_completed(nba_games):  # <-- crashed on stale dict
    ...

# AFTER (the loop owns the first poll; no priming needed):
while not nba_alerts.is_completed(nba_games):  # safe — quarter=0 returns False
    try:
        nba_games, nba_alerted = nba_alerts.send_alerts(client, nba_games, nba_alerted)
    except (RequestException, KeyError, ValueError) as e:
        logging.warning('Error during game update cycle: %s', e)
    sleep(60 - time() % 60)
```

## Why This Works

The sentinel values were chosen so that every downstream consumer handles them correctly before live data arrives:

| Key | Sentinel | Why safe |
|-----|----------|----------|
| `quarter` | `0` | `is_completed()` checks `quarter < 4` → `True` → returns `False` (not done) |
| `clock` | `9999.0` | `is_completed()` checks `clock > CLOCK_ZERO` → `True` → returns `False` |
| `score` | `(0, 0)` | `check_for_new_alerts()` reads `score` → `differential=0`; `quarter==4` is `False` → no alerts |
| `displayClock` | `''` | Alert text formatting safely produces an empty string |

> **Update 2026-10-19:** `is_completed()` no longer reads `quarter` or `clock`. `set_games()` now stores ESPN's real `state` (`pre`/`in`/`post`) from the first fetch, and completion is `state == 'post'` (see the update in `docs/solutions/logic-errors/float-equality-espn-clock-comparison-2026-04-13.md`). The sentinels above still keep `check_for_new_alerts()` and alert formatting safe before the first update.

The while loop enters on its first iteration (sentinel `quarter=0 < 4`), `send_alerts()` calls `update_games()` which overwrites all sentinel values with live ESPN data, and subsequent iterations evaluate real game state.

Removing the priming call is also important: a priming call whose exception is silently swallowed creates a hidden failure mode where the caller cannot tell whether the priming succeeded. The loop's first iteration is a cleaner, self-contained design — the loop itself is the consumer of data, so it should own the first fetch.

## Prevention

- **Initialize every key a dict consumer will access, even as sentinel values.** The dict schema should be complete at construction time. Downstream functions should never need to guard against missing keys with `if 'key' in game`.
- **Treat the while loop as the first consumer of its data.** Do not rely on setup code *outside* the loop to guarantee state that the loop condition depends on. If the guard condition (`is_completed()`) needs populated data, put the population step *inside* the loop.
- **Avoid priming calls whose exceptions are silently swallowed** if the result is immediately used in a guard condition. A try/except around a priming call with no re-raise creates a hidden failure: the caller sees normal execution but state may be indeterminate.
- **Watch for the two-site failure pattern:** when a crash path exists outside a try/except but is triggered by a failure *inside* a try/except (the priming call's except → stale state → is_completed crash). The exception handling at the priming site creates a false sense of safety.

## Related Issues

- See also: `docs/solutions/logic-errors/float-equality-espn-clock-comparison-2026-04-13.md` — the float equality bug in the same polling loop, where `clock == 0` never matched because ESPN returns `0.001` for completed games. Fixed in the same PR.
