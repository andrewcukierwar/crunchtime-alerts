---
date: 2026-04-11
topic: open-ideation
focus: null
---

# Ideation: crunchtime-alerts Improvements

## Codebase Context

- **Project shape:** Python 3.12 CLI Slack bot (~250 lines, 5 modules): `main.py`, `nba_alerts.py`, `nba_elo.py`, `nba_watchability.py`, `config.py`. Uses `uv` for dependency management. Stack: `nba-api`, `pandas`, `numpy`, `requests`, `slack-sdk`.
- **Architecture:** Polling-based daemon loop (60s interval), three alert tiers (5-min, 1-min, overtime), FiveThirtyEight-style ELO ratings + watchability scoring.
- **Notable patterns:** Pre-game time-window check (30-min intervals before games start) already shows intent for adaptive polling; `get_score_report()` is fully implemented but never called (dead code); `FAV_TEAMS` has an explicit `# TODO` comment.
- **Pain points:** Hardcoded Slack token in `config.py`, no error handling on any external call, no logging, in-memory-only alert state, full ELO recomputation on every startup, fragile CrackStreams URL probing at startup.

---

## Ranked Ideas

### 1. Secure the Slack Token

**Description:** Replace the bare `bot_token = 'xoxb-...'` in `config.py` with `os.environ["SLACK_BOT_TOKEN"]`. Load a `.env` file for local dev via `python-dotenv` or `uv run --env-file`. Add `.env` and `config.py` to `.gitignore`. The token is currently committed in git history.

**Rationale:** A live credential granting Slack workspace write access is committed in plaintext. One repo visibility change or Slack auto-revocation silently kills the bot at the worst possible moment. Every other improvement — deployment, sharing, CI — is blocked or risky until this is resolved. It's a 3-line fix.

**Downsides:** Requires updating the launch method (pass env var or maintain a local `.env`). Minor one-time friction.

**Confidence:** 95%
**Complexity:** Low
**Status:** Explored — brainstorm 2026-04-11, requirements at `docs/brainstorms/2026-04-11-secure-slack-token-requirements.md`

---

### 2. Error Handling + Logging Across All External Calls

**Description:** Wrap every `requests.get()` (ESPN, CrackStreams), every `nba_api` call, and every `client.chat_postMessage()` in try/except with logged errors and graceful degradation. Replace all bare `print()` calls with Python's `logging` module (timestamped, leveled, file + stdout). Also fix the `is_completed()` float equality bug (`game['clock'] != 0` should use `> 0.001`) and add a guard for empty game slates (prevents `IndexError` on rest days).

**Rationale:** The entire bot dies silently on any network blip — no log, no Slack message, no error. A single ESPN 500 or rate-limit at 9pm on game night leaves everyone in the dark. Logging turns invisible failures into diagnosable ones. Highest-leverage improvement for operational trust.

**Downsides:** More code to write/maintain. Needs decisions about retry policy (exponential backoff vs. skip-and-continue). Risk of over-engineering simple retry logic.

**Confidence:** 92%
**Complexity:** Medium
**Status:** Unexplored

---

### 3. Persist Alert State Across Restarts

**Description:** Serialize the `nba_alerted` dict to a date-keyed JSON file (`./state.json`) on every mutation. On startup, load it if today's date matches. Four lines: `json.dump` on write, `json.load` on read, date check, clear stale keys.

**Rationale:** A crash or manual restart during a game re-fires every alert (5-min, 1-min, OT) for all already-alerted games. Duplicate Slack pings during a tense Q4 are worse than no alerts. Also unblocks scheduled/automated operation — the process can be safely restarted without re-alerting.

**Downsides:** State file could get stale if the system clock or timezone changes. Edge case: mid-game crash where the clock has advanced past an alert window — state is correct but game context may have shifted.

**Confidence:** 88%
**Complexity:** Low
**Status:** Unexplored

---

### 4. Cache ELO Ratings for the Day

**Description:** After computing `get_team_elos()`, write the result to a date-stamped file (`elo-cache-YYYY-MM-DD.json`). On startup, if today's cache exists and is less than 24 hours old, load it instead of recomputing from the full season game log via `nba_api`.

**Rationale:** `get_team_elos()` hits `stats.nba.com`, downloads a full season game log (~1200 games), and recomputes ELO from scratch — every run. This is the slowest part of startup and the most likely call to get rate-limited. ELO ratings don't change during a game day; caching is a net-zero accuracy tradeoff for a large reliability gain.

**Downsides:** Cache file needs correct invalidation (stale after midnight if the bot runs past midnight). Small on-disk footprint (~1KB).

**Confidence:** 90%
**Complexity:** Low
**Status:** Unexplored

---

### 5. Remove the CrackStreams URL Probe

**Description:** Delete `set_game_urls()` or replace it with a no-op / configurable URL template. The current implementation makes N sequential blocking `requests.get()` calls to `crackstreams.ms` (no timeout, no error handling) to probe which URL variant returns a non-404.

**Rationale:** This is the single most fragile code path: it blocks startup for every game on the slate, uses a piracy site that changes domains frequently, uses text-match error detection, and provides links most users ignore. The probe can be removed in ~10 lines without degrading alert quality. Stream links can become an optional env var template or be dropped entirely.

**Downsides:** Removes streaming links from Slack messages. Any users relying on the links would need to find alternatives.

**Confidence:** 93%
**Complexity:** Low
**Status:** Unexplored

---

### 6. Wire Up the Dead `get_score_report()` Function

**Description:** `get_score_report()` is fully implemented in `nba_alerts.py` but never called — dead code. Wire it into the main loop to post a halftime score update (Q2 end) and a start-of-Q4 digest to Slack. Requires adding quarter-transition tracking to the main loop (~5–10 lines).

**Rationale:** Free value — the feature is already built. Halftime and Q4-start updates give Slack subscribers context without waiting for crunch-time. Exercises the periodic-digest pattern that could later power end-of-game recaps.

**Downsides:** Read `get_score_report()` carefully before wiring — verify correctness first. Adds more Slack message volume; some users may find mid-game pings noisy.

**Confidence:** 85%
**Complexity:** Low
**Status:** Unexplored

---

### 7. Configurable FAV_TEAMS and Alert Thresholds

**Description:** Move `FAV_TEAMS = ['Knicks']` (already marked `# TODO` in `nba_watchability.py`), the Slack channel name (`#crunchtime-alerts`), and alert thresholds (`clock <= 300`, `clock <= 60`, `differential <= 5`) out of source code into environment variables or a `config.yaml`. Read at startup.

**Rationale:** The TODO has been in the code since inception. Changing your favorite team requires editing Python source and restarting. Hardcoded thresholds bury alert sensitivity inside a function. Externalizing these converts developer tasks into operator tasks and is the prerequisite for sharing the bot.

**Downsides:** Adds a config file to manage. Multi-team env var needs a serialization convention (comma-separated). Risk of over-engineering — pick a minimal subset for a personal bot.

**Confidence:** 87%
**Complexity:** Low
**Status:** Unexplored

---

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Adaptive polling intervals | Complex to implement correctly; current approach works; better as a brainstorm topic |
| 2 | Process supervision / daemonization | Deployment infrastructure outside codebase scope |
| 3 | Auto-detect no-game days (IndexError) | Real bug, absorbed into Idea #2 (error handling) |
| 4 | `is_completed()` float equality bug | Real bug, absorbed into Idea #2 |
| 5 | Watchability as numeric signal | Speculative downstream value for a personal bot |
| 6 | Decouple duplicate ESPN fetch | Low-impact DRY issue; absorbed into any error handling refactor |
| 7 | Test suite for core logic | Important long-term; ROI lower than runtime reliability fixes at this project size |
| 8 | Multi-sport expansion | No evidence of user need; speculative scope expansion |
| 9 | Multi-channel / alternate delivery | Speculative; no evidence of need |
| 10 | Reframe as service vs. CLI | Derivative framing; covered by ops-ready cluster outcomes |

---

## Session Log

- 2026-04-11: Initial ideation — 18 candidates generated across 4 frames, 7 survived adversarial filter
- 2026-04-11: Brainstormed Idea #1 (Secure the Slack Token) — requirements doc written, document review passed, proceeding to ce:plan