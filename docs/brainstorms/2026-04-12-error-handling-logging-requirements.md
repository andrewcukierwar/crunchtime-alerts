---
date: 2026-04-12
topic: error-handling-logging
---

# Error Handling and Logging Across All External Calls

## Problem Frame

The bot has no error handling on any external call and no structured logging. A single ESPN 500, rate-limit, or network timeout at 9pm on game night silently kills the process — no log, no Slack message, no indication of what happened. There are also two latent bugs: a float equality check that may never trigger end-of-game detection, and an `IndexError` crash on rest days. This work adds operational trust so the bot can fail gracefully and be diagnosed when it doesn't.

## Requirements

**Error handling and graceful degradation**
- R1. All `requests.get()` calls include an explicit timeout (e.g. 10s). A timeout or connection error does not crash the bot.
- R2. `update_games()` failures in the hot loop are caught, logged, and skipped — the last known game state is preserved for the next cycle.
- R3. `set_games()` failures at startup are caught and the bot exits with a logged error.
- R4. `client.chat_postMessage()` failures (alerts and daily report) are caught and logged; the loop continues.
- R5. `set_game_urls()` failures per-game are caught; that game's URL falls back to a placeholder rather than crashing startup.

**Rest day handling**
- R6. When ESPN returns no events, the bot posts "No NBA games today" to `#crunchtime-alerts` and exits cleanly.

**Logging**
- R7. All `print()` calls are replaced with `logging` module calls at appropriate levels (INFO for normal operation, WARNING for recoverable failures, ERROR for caught exceptions).
- R8. Logs include timestamps. Output goes to both console and a rotating log file.

**Bug fixes**
- R9. `is_completed()`: replace `game['clock'] != 0` with `game['clock'] > 0.001` to avoid float equality failure at end-of-game.
- R10. `get_time_windows()`: guard against an empty `games` dict (duplicate of R6's exit path — ensure consistency).

## Success Criteria

- The bot survives a full game night if ESPN returns one or more transient errors during the hot loop.
- A rest day run exits cleanly with a Slack message instead of crashing with `IndexError` or `KeyError`.
- After any failure, the log contains enough context to diagnose what failed and when.
- No duplicate alerts are fired due to the `is_completed()` bug.

## Scope Boundaries

- No retry logic — skip-and-continue is the failure policy for the hot loop (R2). No exponential backoff.
- CrackStreams removal is out of scope (idea #5 in the ideation doc). R5 adds a timeout and try/except around the existing URL probe; it does not remove it.
- No changes to alert thresholds, watchability scoring, or ELO computation.
- No `python-dotenv` or new dependencies. Use stdlib `logging` only.

## Key Decisions

- **Skip-and-continue over retry in the hot loop**: A 60-second retry interval is already built in. Retrying immediately adds complexity for a marginal benefit on a personal bot.
- **File + console logging**: The bot may run unattended; a rotating log file preserves post-mortem history without unbounded disk use.
- **Rest day → post + exit**: Keeps the daily Slack message consistent across game days and rest days. Silent exit would leave subscribers wondering if the bot ran.
- **Timeout on CrackStreams calls (R5)**: Even though removal is deferred, an unbounded blocking call at startup is unacceptable. A timeout ensures startup completes in bounded time.

## Dependencies / Assumptions

- The bot runs as a foreground process on a single machine (no process supervisor). This is consistent with the skip-and-continue policy — a crash still requires manual restart.
- `game['clock']` is confirmed to be a float (verified: ESPN API returns clock as a numeric type via `event['status']['clock']`).

## Outstanding Questions

### Deferred to Planning

- [Affects R8][Technical] What log file name, location, and rotation policy? (e.g. `crunchtime.log` in the project root, 1MB max, 3 backups — or a `logs/` subdirectory.)
- [Affects R1, R5][Technical] What timeout value for `requests.get()`? 10s is a reasonable default; verify against ESPN and CrackStreams typical response times.
- [Affects R4][Technical] Should a failed daily report post be retried once before logging and continuing? The daily report is a one-shot at startup, unlike hot-loop alerts.

## Next Steps

→ `/ce:plan` for structured implementation planning
