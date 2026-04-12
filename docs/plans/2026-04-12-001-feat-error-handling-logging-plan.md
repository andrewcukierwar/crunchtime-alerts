---
title: "feat: Add error handling, logging, and bug fixes across all external calls"
type: feat
status: active
date: 2026-04-12
origin: docs/brainstorms/2026-04-12-error-handling-logging-requirements.md
---

# feat: Add error handling, logging, and bug fixes across all external calls

## Overview

The bot currently has no error handling on any external call and no structured logging. A single ESPN 500, rate-limit, or network timeout at 9pm on game night silently kills the process — no log, no Slack message, no indication of what happened. This plan adds operational trust: graceful degradation at each external call site, structured log output, and fixes for two latent bugs (float equality in clock comparisons, `IndexError` on rest days).

A document review on the requirements doc surfaced two gaps that are addressed here: (1) `nba_watchability.get_watchability()` makes an independent ESPN call with no timeout or error handling — it must be covered alongside the other calls; (2) `get_score_report()` contains the same float equality clock bug as `is_completed()` and must be fixed in the same pass.

## Problem Frame

Four `requests.get()` call sites exist across three modules (`nba_alerts.py` ×3, `nba_watchability.py` ×1). None have timeouts or error handling. There are also two `client.chat_postMessage()` call sites with no error handling. On rest days, `get_time_windows()` crashes with `IndexError` when the ESPN API returns no events. Two functions compare `game['clock']` to `0` with exact float equality, which may never trigger at end-of-game. See origin doc for full requirement list (R1–R10).

## Requirements Trace

- R1. All `requests.get()` calls include an explicit timeout. A timeout or connection error does not crash the bot.
- R2. `update_games()` failures in the hot loop are caught, logged, and skipped — last known game state preserved.
- R3. `set_games()` failures at startup are caught and the bot exits with a logged error.
- R4. `client.chat_postMessage()` failures are caught and logged; execution continues.
- R5. `set_game_urls()` per-game failures are caught; that game's URL falls back to a placeholder.
- R6. When ESPN returns no events, the bot posts "No NBA games today" to `#crunchtime-alerts` and exits cleanly.
- R7. All `print()` calls are replaced with `logging` module calls at appropriate levels.
- R8. Logs include timestamps. Output goes to both console and a rotating log file.
- R9a. `is_completed()` line 93: replace `game['clock'] != 0` with `game['clock'] > 0.001`.
- R9b. `get_score_report()` line 108: replace `game['clock'] == 0` with `game['clock'] <= 0.001`. Same float equality root cause; fixed in the same pass. (surfaced in doc review)
- R10. `get_time_windows()`: guard against an empty `games` dict (secondary defense after R6 guard in main.py).
- R-WA *(doc review addition)*. `nba_watchability.get_watchability()` adds a 10s timeout and try/except; on failure, degrades to 'Medium' watchability for all games rather than crashing startup.

## Scope Boundaries

- No retry logic — skip-and-continue is the failure policy for the hot loop. No exponential backoff.
- CrackStreams removal is out of scope. R5/R1 add timeout and try/except around the existing URL probe only.
- No changes to alert thresholds, watchability scoring, or ELO computation.
- No new dependencies. Stdlib `logging` only.
- Daily report failure: skip-and-continue (no retry). The no-retry scope boundary applies consistently to both hot-loop and startup Slack calls.
- `nba_elo.get_output()` / `nba_api` SDK calls are out of scope — that chain has its own complexity and is a separate idea (#4 ELO caching).

### Deferred to Separate Tasks

- ELO data caching and `nba_api` error handling: idea #4 in ideation doc
- CrackStreams removal: idea #5 in ideation doc
- Alert state persistence across restarts: idea #3 (after a crash + manual restart, in-progress alerts re-fire — accepted for this iteration)
- Consecutive-failure detection in hot loop (N failures → Slack warning): not in scope; doc review advisory noted and deferred

## Context & Research

### Relevant Code and Patterns

- `nba_alerts.py:11` — `set_game_urls()`: one `requests.get()` per game to CrackStreams, no timeout, no try/except
- `nba_alerts.py:16` — `set_games()`: `requests.get()` to ESPN scoreboard; `data['events']` KeyError risk; no guard
- `nba_alerts.py:33` — `update_games()`: same ESPN call inside hot loop
- `nba_alerts.py:72–85` — `send_alerts()`: calls `update_games()`, then `chat_postMessage()`; `alerted[timeframe].add(teams)` happens **after** `chat_postMessage()` — a failed send correctly leaves the alert eligible for retry next cycle
- `nba_alerts.py:87–91` — `get_time_windows()`: `list(games.values())[0]` at line 89 raises `IndexError` on empty dict
- `nba_alerts.py:93–97` — `is_completed()`: `game['clock'] != 0` float equality bug
- `nba_alerts.py:108` — `get_score_report()`: `game['clock'] == 0` — **same float equality bug, must be fixed in R9 pass**
- `nba_alerts.py:82–84` — `chat_postMessage()` in `send_alerts()`; line 83 `print('Alert Sent')`
- `nba_watchability.py:17` — `get_watchability()`: independent `requests.get()` to ESPN scoreboard, no timeout, no error handling; called via `get_daily_report()` at `nba_alerts.py:61`
- `main.py:20` — daily report `chat_postMessage()`; line 21 `print('NBA Daily Report Sent')`
- `main.py:23` — `get_time_windows(nba_games)` called after `set_games()` returns — crash site for rest days
- `main.py` print calls at lines 21, 28, 32, 40

**Startup sequence in main.py (relevant to R3/R6 call-site ordering):**
1. `set_games()` → returns `nba_games` dict
2. *(R6 guard goes here: if not nba_games → post + exit)*
3. `get_daily_report(nba_games)` → calls `get_watchability()` internally
4. `client.chat_postMessage()` → daily report Slack post
5. `get_time_windows(nba_games)` → crash site

### Institutional Learnings

- `docs/solutions/best-practices/env-var-secrets-gitignore-inline-comments-2026-04-12.md` — existing `SLACK_BOT_TOKEN` startup guard pattern; new error handling for `chat_postMessage` layers on top of this, not replaces it

### External References

None needed — stdlib `logging` and `requests.exceptions` are sufficient. Use `except Exception` (not `except SlackApiError`) for Slack call sites — no additional import needed, and this is consistent with the hot-loop boundary pattern already shown in Unit 4.

## Key Technical Decisions

- **R6/R3 exit path separation**: R3 (ESPN exception at startup) exits via `sys.exit(1)` with no Slack post — it's a diagnostic failure. R6 (ESPN returns empty events) exits via `sys.exit(0)` after posting "No NBA games today" — it's a normal rest-day condition. These are two distinct `except`/`if` branches in `main.py`; never collapse them into one handler.
- **R6 guard placement**: The guard for empty events **must** live in `main.py` after `set_games()` returns and before `get_daily_report()` and `get_time_windows()` are called. The `get_time_windows()` guard (R10) is a secondary defense only.
- **Hot loop error boundary**: Wrap the entire `send_alerts()` call in `main.py`'s while loop with try/except. When `send_alerts()` raises (e.g., `update_games()` fails), `nba_games` and `alerted` retain their previous-cycle values — this is the "last known game state preserved" behavior from R2.
- **Logging setup location**: Root logger configured once in `main()` in `main.py` before any other calls. All other modules (`nba_alerts.py`, `nba_watchability.py`) use `import logging` and call `logging.info()` / `logging.warning()` / `logging.error()` directly against the root logger. No module-level `basicConfig()` or `addHandler()` calls outside `main.py`.
- **Log file**: `crunchtime.log` in project root, `maxBytes=1_000_000`, `backupCount=3`. No `logs/` subdirectory — keeps it simple for a single-file project. Add `*.log` to `.gitignore`.
- **Timeouts**: 10s for all ESPN calls; 5s for CrackStreams probes (a CrackStreams timeout is functionally equivalent to a 404 — shorter bound keeps startup responsive across a full game slate).
- **Watchability failure policy**: `get_watchability()` catches its own exception, logs WARNING, and returns `{}`. The caller (`get_daily_report()`) falls back to a default watchability entry (`{'Watchability': 'Medium', 'Away Rating': 0, 'Home Rating': 0}`) via `watchability_dict.get(game, default)`. This keeps the daily report intact even if the watchability ESPN call fails. **Why degrade-and-continue (unlike R3's exit policy)**: watchability data is optional — the bot's core function (score monitoring and alerts) depends only on `set_games()` and `update_games()`. A watchability failure degrades the daily report but does not block alert delivery. Game list data is strictly required; watchability data is not.
- **`alerted` update order on failed send**: The existing ordering (`chat_postMessage()` then `alerted.add()`) is already correct — a failed send leaves the alert eligible for retry next cycle. No reordering needed; just wrap the send in try/except.
- **R9 fix value**: `0.001` threshold for both comparisons (`> 0.001` in `is_completed()`, `<= 0.001` in `get_score_report()`). `game['clock']` is in **seconds** (proven by `check_for_new_alerts()` using `<= 300` for 5-min and `<= 60` for 1-min windows). Values range from 0.0 (game end) to 720.0 (full 12-min quarter). The `0.001` epsilon (< 1 ms) correctly identifies end-of-game without false positives.
- **Daily report retry**: None. The no-retry policy applies uniformly to all Slack calls — adding retry for only the daily report introduces asymmetry for minimal benefit on a personal bot.

## Open Questions

### Resolved During Planning

- **Log file location**: Project root (`crunchtime.log`), not `logs/` subdirectory — simpler for a single-machine personal bot.
- **Timeout values**: 10s ESPN, 5s CrackStreams (see Key Technical Decisions above).
- **Daily report retry**: No retry — consistent with skip-and-continue scope boundary.
- **Watchability failure policy**: Degrade to 'Medium' (see Key Technical Decisions).
- **R6 guard call-site**: Confirmed `main.py` after `set_games()`, before `get_daily_report()` — not inside `nba_alerts.py`.
- **R9 scope**: Extended to cover `get_score_report()` line 108 (doc review P1 finding).

### Deferred to Implementation

- **Exception types**: For all ESPN `requests.get()` call sites, catch `(requests.exceptions.RequestException, KeyError, ValueError)`. `RequestException` covers network failures, timeouts, and connection errors. `KeyError` covers `data['events']` and similar direct-access patterns on the parsed JSON. `ValueError` covers malformed JSON (`response.json()` failure). The hot-loop boundary in `main.py` uses the same narrow tuple — start narrow during implementation, broaden to `except Exception` only after manual validation (see Unit 4 approach).
- **`get_score_report()` clock check direction**: The full condition at line 108 is `game['quarter'] >= 4 and game['clock'] == 0 and away_score != home_score`. The fix changes only `game['clock'] == 0` to `game['clock'] <= 0.001`. Verify the `game['quarter'] >= 4` and score inequality parts are preserved unchanged during implementation.

## Implementation Units

- [x] **Unit 1: Logging infrastructure**

**Goal:** Configure `logging` in `main()`, replace all `print()` calls in `main.py` with logging calls at appropriate levels.

**Requirements:** R7, R8

**Dependencies:** None — must land first; all other units depend on logging calls.

**Files:**
- Modify: `main.py`
- Modify: `.gitignore` (add `*.log`)

**Approach:**
- In `main()`, before any other calls: configure root logger with two handlers — `RotatingFileHandler('crunchtime.log', maxBytes=1_000_000, backupCount=3)` and `StreamHandler()`. Both use format `'%(asctime)s %(levelname)s %(message)s'`.
- Replace `main.py` print calls:
  - line 21 `print('NBA Daily Report Sent')` → `logging.info('NBA daily report sent')`
  - line 28 `print('Checking to see if first game started')` → `logging.info('Waiting for first game to start')`
  - line 32 `print('First game started')` → `logging.info('First game started')`
  - line 40 `print('All games done')` → `logging.info('All games completed')`
- Do not configure logging in any module other than `main.py`.

**Patterns to follow:**
- Existing token validation guard in `main()` (lines 7–12) — same `sys.exit()` fail-fast pattern for startup validation

**Test scenarios:**
- Happy path: Run bot normally → `crunchtime.log` is created, each logged event includes an ISO timestamp and level, console output mirrors log file content
- Rotation: Manually inflate log file past 1 MB → backup files appear (`crunchtime.log.1`, `.2`, `.3`), log continues cleanly
- No side effects: Importing `nba_alerts` or `nba_watchability` does not create a log file or configure any handlers

**Verification:**
- `crunchtime.log` exists after a run
- All four previous `print()` locations in `main.py` are gone
- No `logging.basicConfig()`, `addHandler()`, or `RotatingFileHandler` calls outside `main.py`

---

- [x] **Unit 2: Startup hardening — set_games, rest day guard, get_time_windows**

**Goal:** Add a 10s timeout to `set_games()`, add R6 rest-day exit guard in `main.py`, add R10 secondary guard in `get_time_windows()`, replace `nba_alerts.py` print call.

**Requirements:** R1 (set_games ESPN call), R3, R6, R7 (nba_alerts.py:83 print), R10

**Dependencies:** Unit 1 (logging must be configured first)

**Files:**
- Modify: `nba_alerts.py`
- Modify: `main.py`

**Approach:**
- `nba_alerts.py` — `set_games()`: add `timeout=10` to `requests.get()`; let exceptions propagate to the caller (main.py owns the exit).
- `nba_alerts.py` — `send_alerts()` line 83: replace `print('Alert Sent')` with `logging.info('Alert sent: %s vs %s (%s)', away_team, home_team, timeframe)` or similar.
- `nba_alerts.py` — `get_time_windows()` (R10): add an early return guard at the top — `if not games: return None`.
- `main.py` — after `get_time_windows()` returns, guard the None case: `if lower_window is None: logging.error('Could not determine game start windows'); sys.exit(1)`. This is a secondary defense; the primary guard (R6) prevents reaching this path under normal operation.
- `main.py` — after `set_games()` returns, add two guards before proceeding:
  1. **R3 (exception)**: wrap `set_games()` call with `try/except Exception`: log ERROR with message and `sys.exit(1)` — no Slack post.
  2. **R6 (empty events)**: after successful return, `if not nba_games:` → `logging.info(...)`, `client.chat_postMessage(channel='#crunchtime-alerts', text='No NBA games today')`, `sys.exit(0)`.
- The R6 `chat_postMessage()` call **must** be wrapped in its own try/except at the time it is introduced here. A failed Slack post on rest day should log a warning and still `sys.exit(0)` — the bot ran correctly, the notification just failed to send. Do not defer this to Unit 4; an unguarded Slack call in the rest-day exit path contradicts R6's "exits cleanly" goal.

**Patterns to follow:**
- `main.py` token guard pattern (lines 7–12): `if not ...: sys.exit(...)` fail-fast structure

**Test scenarios:**
- Happy path: ESPN returns valid events → `nba_games` populated, execution proceeds past the guards
- R6 — rest day: Mock ESPN returning `{'events': []}` → bot logs "No NBA games today", posts to Slack, exits with code 0
- R3 — ESPN exception: Mock `requests.get()` raising `requests.exceptions.ConnectionError` inside `set_games()` → bot logs ERROR, exits with code 1, no Slack post sent
- R3 — ESPN timeout: Mock `requests.get()` raising `requests.exceptions.Timeout` → same R3 behavior as above
- R10 guard: Call `get_time_windows({})` directly → returns `None` instead of raising `IndexError`
- Distinction: An ESPN network exception must NOT trigger the "No NBA games today" Slack post; only an empty-events response should

**Verification:**
- `set_games()` source shows `timeout=10` on the `requests.get()` call
- `main.py` has two separate code paths after `set_games()`: one for exceptions, one for empty return
- `get_time_windows()` does not raise `IndexError` when called with `{}`

---

- [x] **Unit 3: External call hardening — set_game_urls and get_watchability**

**Goal:** Add per-game timeout + try/except to `set_game_urls()` with URL fallback; add timeout + error handling to `nba_watchability.get_watchability()` with watchability degradation.

**Requirements:** R1 (CrackStreams + watchability ESPN timeouts), R5, R-WA

**Dependencies:** Unit 1 (logging)

**Files:**
- Modify: `nba_alerts.py`
- Modify: `nba_watchability.py`

**Approach:**
- `nba_alerts.py` — `set_game_urls()`: wrap each per-game `requests.get()` in try/except inside the existing loop. On `Exception`: `logging.warning('Could not fetch stream URL for %s vs %s: %s', ...)` and set the game's URL to a placeholder string (e.g., `'#'` or `'https://www.nba.com'`). Add `timeout=5` to the `requests.get()` call. One failing URL probe must not crash the full startup loop.
- `nba_watchability.py` — `get_watchability()`: add `timeout=10` to `requests.get()`; wrap in try/except. On exception: `logging.warning('Could not fetch watchability data: %s', e)` and return `{}` (empty dict). The caller handles the empty dict.
- `nba_alerts.py` — `get_daily_report()` line 63: update the `games[game].update(...)` call to use `watchability_dict.get(game, {'Watchability': 'Medium', 'Away Rating': 0, 'Home Rating': 0})` instead of direct dict access. This makes the call site resilient to both a failed `get_watchability()` call and a key mismatch between the two ESPN responses. **This change and the `get_watchability()` try/except above are a single atomic change** — applying one without the other leaves a `KeyError` crash on the nominal degraded path (empty `watchability_dict` from `get_watchability()`).

**Patterns to follow:**
- Same `timeout=` parameter pattern as Unit 2's `set_games()` fix

**Test scenarios:**
- R5 — CrackStreams timeout: Mock one game's `requests.get()` to raise `Timeout` → that game gets placeholder URL; other games' URLs are fetched normally; startup completes
- R5 — CrackStreams all fail: All URL probes fail → all games get placeholder URLs; startup continues; daily report still sent
- R-WA — watchability ESPN fails: Mock `get_watchability()` ESPN call to fail → `get_watchability()` returns `{}`; `get_daily_report()` uses 'Medium' fallback for all games; daily report is sent with fallback values
- R-WA — watchability key mismatch: `get_watchability()` returns a dict missing one game key → that game gets 'Medium' fallback; other games use their actual watchability values

**Verification:**
- `set_game_urls()` source shows `timeout=5` and per-game try/except
- `get_watchability()` source shows `timeout=10` and try/except returning `{}`
- `get_daily_report()` uses `.get(game, default)` rather than direct `watchability_dict[game]` access

---

- [x] **Unit 4: Runtime hardening — hot loop and daily report**

**Goal:** Wrap hot loop `send_alerts()` call with skip-and-continue; wrap daily report and alert `chat_postMessage()` calls with try/except; add update_games timeout.

**Requirements:** R1 (update_games ESPN timeout), R2, R4

**Dependencies:** Unit 1 (logging), Unit 2 (startup sequence already hardened)

**Files:**
- Modify: `nba_alerts.py`
- Modify: `main.py`

**Approach:**
- `nba_alerts.py` — `update_games()`: add `timeout=10` to `requests.get()`. Let exceptions propagate to `send_alerts()` / main.py.
- `nba_alerts.py` — `send_alerts()` line 82: wrap `client.chat_postMessage(...)` in try/except. On `Exception`: `logging.warning('Failed to send alert for %s vs %s: %s', ...)` and continue the inner loop. Do NOT update `alerted[timeframe].add(teams)` after a failed send — the existing ordering is correct and the alert will be retried next cycle.
- `main.py` — hot loop (while loop, line 36): wrap the `send_alerts()` call:
  ```
  try:
      nba_games, alerted = nba_alerts.send_alerts(client, nba_games, alerted)
  except (requests.exceptions.RequestException, KeyError, ValueError) as e:
      logging.warning('Error during game update cycle: %s', e)
  ```
  When `send_alerts()` raises, `nba_games` and `alerted` retain their previous values (skip-and-continue, R2). **Start with the narrow catch above** — this surfaces coding bugs (AttributeError, TypeError) as visible crashes during the implementation and testing phase. After manual validation on a real game night, the catch may be broadened to `except Exception` if desired. The narrow tuple covers network failures (`RequestException`), ESPN parse failures (`KeyError` on `data['events']`, `ValueError` on malformed JSON), and the pre-existing `name`/`displayName` key inconsistency between `set_games()` and `update_games()`.
- `main.py` — daily report `client.chat_postMessage()` (line 20): wrap in try/except. On `Exception`: `logging.warning('Failed to send daily report: %s', e)` and continue. No retry.

**Patterns to follow:**
- The `try/except` structure from Unit 2's `set_games()` guard in `main.py`

**Test scenarios:**
- R2 — ESPN down during hot loop: Mock `update_games()` to raise → `send_alerts()` raises → main.py catches, logs WARNING, `nba_games` retains previous-cycle values, loop continues, next iteration proceeds normally
- R4 — Slack rate-limited during alert: Mock `chat_postMessage()` to raise `SlackApiError` inside `send_alerts()` → warning logged, `alerted` not updated, alert retried next cycle
- R4 — daily report Slack failure: Mock daily report `chat_postMessage()` to raise → warning logged, startup continues to `get_time_windows()` and hot loop
- Alerted state preservation: After a failed `send_alerts()`, the same alert fires again on the next cycle (not silently dropped)

**Verification:**
- `update_games()` source shows `timeout=10`
- `send_alerts()` wraps `chat_postMessage()` in try/except without updating `alerted` on failure
- `main.py` while loop catches `send_alerts()` exceptions and preserves `nba_games` and `alerted`
- `main.py` daily report `chat_postMessage()` is wrapped in try/except

---

- [x] **Unit 5: Bug fixes — float equality and clock comparisons**

**Goal:** Fix float equality clock comparisons in `is_completed()` and `get_score_report()`.

**Requirements:** R9a, R9b

**Dependencies:** None — independent of all other units, can land in any order

**Files:**
- Modify: `nba_alerts.py`

**Approach:**
- `nba_alerts.py` — `is_completed()` line 93 (R9a): change `game['clock'] != 0` to `game['clock'] > 0.001`. The full condition becomes `game['quarter'] < 4 or game['clock'] > 0.001 or game['score'][0] == game['score'][1]`.
- `nba_alerts.py` — `get_score_report()` line 108 (R9b): change `game['clock'] == 0` to `game['clock'] <= 0.001`. The full condition is `game['quarter'] >= 4 and game['clock'] <= 0.001 and away_score != home_score` — preserve the `quarter >= 4` and score inequality parts unchanged.
- No other changes to these functions.

**Patterns to follow:**
- Same function, adjacent line — minimal change principle

**Test scenarios:**
- `is_completed()` with clock=0.0: construct a game dict with `quarter=4, clock=0.0, score=(95, 90)` → `is_completed()` returns `True`
- `is_completed()` with clock=0 (int): same dict but `clock=0` (int) → `is_completed()` returns `True`
- `is_completed()` with clock=0.0001: same dict but `clock=0.0001` → `is_completed()` returns `True` (well within threshold)
- `is_completed()` with clock=1.0: `quarter=4, clock=1.0, score=(95, 90)` → `is_completed()` returns `False` (game still in progress)
- `get_score_report()` with clock=0.0: should render the final-score format, not mid-game format

**Verification:**
- `is_completed()` line 93 reads `> 0.001`, not `!= 0` (R9a)
- `get_score_report()` line 108 reads `<= 0.001`, not `== 0`; `quarter >= 4` condition preserved (R9b)

## System-Wide Impact

- **Interaction graph:** `main.py` orchestrates all external calls. `send_alerts()` is the only function called from both startup and the hot loop. Logging is configured once in `main()` — all module-level log calls inherit the root logger.
- **Error propagation:** Startup failures (R3) propagate via exception to `main.py` → `sys.exit(1)`. Rest-day exit (R6) is a controlled `sys.exit(0)`. Hot-loop errors (R2) are caught at the `send_alerts()` call site in `main.py` and do not propagate. Alert send failures (R4) are caught inside `send_alerts()` and do not propagate.
- **State lifecycle risks:** Skipping a hot-loop cycle preserves `nba_games` and `alerted` from the previous cycle. The `alerted` dict is only updated after a successful send — a failed send correctly keeps the alert eligible for retry next cycle.
- **API surface parity:** No new public interfaces. All changes are internal error handling and logging within existing functions.
- **Integration coverage:** The R6/R3 distinction (empty events vs. exception) must be verified manually with a mock or a real rest day — unit tests alone can verify the logic but not the Slack post.
- **Unchanged invariants:** Alert threshold logic (`check_for_new_alerts()`), watchability scoring criteria, ELO computation, and the hot-loop timing (`sleep(60 - time() % 60)`) are all untouched.

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| R6 and R3 exit paths collapsed into one `except` block | Plan explicitly calls out two separate code paths; test scenarios validate the distinction |
| `get_score_report()` line 108 conditional structure broken by R9 fix | Defer to implementer to read the full `elif` chain carefully; verification checks both comparisons |
| Logging setup in a module other than `main.py` causes double log lines | Verification checklist explicitly checks for absence of `basicConfig`/`addHandler` outside `main.py` |
| `get_time_windows()` R10 guard returns `None` and main.py doesn't handle it | Plan specifies `main.py` handles the `None` return from `get_time_windows()` gracefully |
| Watchability key mismatch between two sequential ESPN calls | `get_daily_report()` uses `.get(game, default)` — key mismatch degrades gracefully to 'Medium' |

## Documentation / Operational Notes

- Add `*.log` to `.gitignore` to prevent `crunchtime.log` from being committed.
- After this work, a rest-day run produces a Slack post and a clean log instead of a silent crash. The log file (`crunchtime.log`) is the primary diagnostic artifact for post-mortem on game nights.
- Two solution docs worth creating after implementation: float-equality clock bug (project-specific gotcha) and skip-and-continue polling pattern.

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-12-error-handling-logging-requirements.md](docs/brainstorms/2026-04-12-error-handling-logging-requirements.md)
- Related code: `nba_alerts.py`, `nba_watchability.py`, `main.py`
- Related PRs/issues: andrewcukierwar/crunchtime-alerts#1 (secure token refactor — preceding work)
