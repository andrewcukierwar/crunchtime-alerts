---
title: Float Equality Bug with ESPN Game Clock Values
date: 2026-04-13
category: docs/solutions/logic-errors
module: crunchtime-alerts
problem_type: logic_error
component: tooling
severity: high
symptoms:
  - "is_completed() always returned False for finished games — polling loop never exited"
  - "get_score_report() never displayed final score format for completed games"
  - "Float equality check clock == 0 or clock != 0 silently misfired on completed games"
root_cause: logic_error
resolution_type: code_fix
related_components:
  - nba_alerts.py
tags:
  - float-equality
  - espn-api
  - clock-comparison
  - epsilon
  - python
  - silent-logic-error
  - polling-loop
---

# Float Equality Bug with ESPN Game Clock Values

## Problem

ESPN's scoreboard API returns the game clock as a float. For completed games it returns a small non-zero value (approximately `0.001`) rather than exactly `0.0`. Code that compared `clock == 0` or `clock != 0` required exact equality, which was never satisfied — `is_completed()` always returned `False` for finished games, causing the polling loop to run indefinitely.

## Symptoms

- `is_completed()` always returned `False` despite games being over — bot polled ESPN all night
- `get_score_report()` never displayed the completed-game final score format (the `clock == 0` branch was unreachable)
- Silent failure: no exception, no error log — just wrong behavior

## What Didn't Work

The bug was identified through code analysis rather than runtime debugging, so no alternative fixes were attempted before the correct solution was applied. However, a single-site fix (updating only `is_completed()`) would have been incomplete — the same `clock == 0` comparison existed in a second call site, `get_score_report()`, which would have continued silently misbehaving. Both sites needed updating together.

## Solution

Extract a named threshold constant and replace all exact float equality checks with threshold comparisons:

```python
# nba_alerts.py — add near top of file, after imports
CLOCK_ZERO = 0.001  # ESPN returns a small non-zero float for completed games, not exactly 0.0

# is_completed() — before
if game['quarter'] < 4 or game['clock'] != 0 or game['score'][0] == game['score'][1]:

# is_completed() — after
if game['quarter'] < 4 or game['clock'] > CLOCK_ZERO or game['score'][0] == game['score'][1]:

# get_score_report() — before
elif game['quarter'] >= 4 and game['clock'] == 0 and away_score != home_score:

# get_score_report() — after
elif game['quarter'] >= 4 and game['clock'] <= CLOCK_ZERO and away_score != home_score:
```

## Why This Works

ESPN's API encodes "game over" as a clock value near zero (e.g., `0.001`), not exactly `0.0`. Python's `==` operator requires exact equality for floats, which is never satisfied by `0.001`. The `CLOCK_ZERO = 0.001` constant acts as a tolerance epsilon: any clock value at or below `0.001` is treated as "game over."

This is safe because the game clock is expressed in **seconds** (confirmed by the 5-minute alert threshold `clock <= 300` and the 1-minute alert threshold `clock <= 60` in `check_for_new_alerts()`). Legitimate in-game clocks count down from `720.0` — a threshold of `0.001` seconds is well below any meaningful remaining game time and cannot produce false positives.

Naming the constant also documents intent for future readers and prevents the two call sites from drifting apart — if the threshold ever needs adjusting, one change updates both.

## Prevention

- **Never use `== 0` or `!= 0` on floats from external APIs.** Sports clock fields, financial values, GPS coordinates, and sensor readings often encode "zero" as a small non-zero float due to serialization or rounding.
- **Extract float thresholds as named constants** with a comment explaining the tolerance and its rationale. This forces you to choose the epsilon deliberately and documents it for future readers.
- **Verify the clock unit before choosing an epsilon.** `0.001` is safe for a seconds-based clock but would be dangerously large for a minutes-based one (0.001 minutes = 0.06 seconds — a live game could be at that value).
- **Grep for all uses of the same field** before declaring a fix complete. The `clock == 0` pattern appeared in both `is_completed()` and `get_score_report()` — a single-site fix would have left the second site broken.

## Related Issues

- See also: `docs/solutions/logic-errors/sentinel-initialization-keyerror-game-state-2026-04-13.md` — a related P0 crash in the same polling loop, fixed in the same PR, where games dict missing `quarter`/`clock`/`score` keys caused a `KeyError` before `update_games()` ran. The two bugs share the root cause of the game dict schema not being enforced at construction time.
