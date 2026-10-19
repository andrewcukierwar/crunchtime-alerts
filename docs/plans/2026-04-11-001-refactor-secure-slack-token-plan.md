---
title: "refactor: Replace hardcoded Slack token with environment variable"
type: refactor
status: completed
date: 2026-04-11
origin: docs/brainstorms/2026-04-11-secure-slack-token-requirements.md
---

# refactor: Replace hardcoded Slack token with environment variable

## Overview

Remove `config.py` and replace its single hardcoded `bot_token` string with a `SLACK_BOT_TOKEN` environment variable read at startup. Add a startup guard that exits with a clear, actionable error if the variable is missing. Add `.env.example` so new contributors know what to set. Update `.gitignore` and the README to match the new pattern.

## Problem Frame

The bot token lives in `config.py` as a plaintext string. While `config.py` is gitignored, the setup contract is invisible to anyone cloning the repo — there is no `.env.example`, no README instruction pointing to an environment variable, and no error message if the variable is absent. Environment variable-based configuration is the standard pattern for portable, automatable scripts.

See origin: `docs/brainstorms/2026-04-11-secure-slack-token-requirements.md`

## Requirements Trace

**Runtime behavior**
- R1. `main.py` reads `SLACK_BOT_TOKEN` from the environment via `os.environ.get`, replacing `import config` and `config.bot_token`. Exits immediately with a clear message if unset.

**Contributor scaffolding**
- R3. `.env.example` is added with a placeholder token value.
- R4. A bare `.env` line is added to `.gitignore` (the existing `.env/` directory entry does not match a flat file).

**File removal and gitignore cleanup**
- R2. `config.py` is deleted.
- R5. `config.py` is removed from `.gitignore`.

## Scope Boundaries

- No `python-dotenv` dependency; `.env` loading is the user's responsibility (shell export or manual source).
- Slack channel name (`#crunchtime-alerts`) stays hardcoded in `main.py` — out of scope.
- Token rotation in the Slack admin console is a prerequisite action, not a code change.

## Context & Research

### Relevant Code and Patterns

- `main.py` is the **only** file that imports `config`. Lines 5 (`import config`) and 8 (`WebClient(token=config.bot_token)`) are the sole change sites.
- `config.py` is currently line 2 of `.gitignore`; `.env` (flat file) has no entry; `.env/` (directory) is on line 39.
- No test suite and no CI exist in this project.
- `uv` is the package manager (`pyproject.toml` present). No `python-dotenv` in dependencies.

### Institutional Learnings

- No `docs/solutions/` exists yet. This is the first tracked solution.

## Key Technical Decisions

- **`os.environ.get` + `sys.exit` over bare `os.environ[...]`:** Bare bracket access raises a cryptic `KeyError`. `os.environ.get` with an explicit `if not token: sys.exit(message)` produces a human-readable error pointing to `.env.example`. This matches the success criterion that a new contributor can self-diagnose configuration errors without reading source code.

- **R5 (remove `config.py` from `.gitignore`):** The requirements doc specifies removing this entry. The document review flagged a counterpoint: keeping the entry is free defense-in-depth against accidentally tracking a future `config.py`. The plan follows the requirements doc and removes the entry, since `config.py` as a configuration pattern is being replaced, not just renamed. If a future `config.py` appears it will be a different file and should be evaluated on its own merits.

- **README update included:** The requirements doc deferred this to planning judgment. The README explicitly documents the old `config.py` setup pattern in two places (Installation step 3 and the Project Structure tree). Not updating it would directly contradict the success criterion that a new contributor can onboard from `.env.example` alone. The update is included.

## Open Questions

### Resolved During Planning

- **Should README be updated?** Yes — README currently shows the old `config.py` pattern; omitting the update breaks the onboarding success criterion. (see origin: Scope Boundaries)
- **Should R5 (remove `config.py` from .gitignore) be kept?** Yes, following the requirements doc. See Key Technical Decisions above.

### Deferred to Implementation

- **Token rotation timing:** Rotate the Slack token **before merging**. Pre-flight steps: (1) run `git log --all -p -- config.py` and confirm the token string has never been committed; (2) rotate in the Slack admin console and record the new value; (3) then proceed with the implementation units. Do not delete `config.py` until the new token is confirmed working.

## Implementation Units

- [x] **Unit 1: Update `main.py` to read from environment**

  **Goal:** Replace `import config` and `config.bot_token` with `os.environ.get("SLACK_BOT_TOKEN")` and a startup validation guard.

  **Requirements:** R1

  **Dependencies:** None

  **Files:**
  - Modify: `main.py`

  **Approach:**
  - Remove `import config` (line 5)
  - Add `import os` and `import sys`
  - Before `client = WebClient(...)`, read the env var and exit if missing:
    `token = os.environ.get("SLACK_BOT_TOKEN")` → if not token: `sys.exit(...)` with message pointing to `.env.example`
  - Add a second guard after the null check: if the token does not start with `xoxb-`, exit with a message indicating the token looks wrong (catches a verbatim copy of the `.env.example` placeholder)
  - Pass `token` to `WebClient(token=token)`
  - No other logic in `main.py` changes

  **Patterns to follow:**
  - Standard Python startup guard pattern; no framework precedent needed

  **Test scenarios:**
  - Happy path: `SLACK_BOT_TOKEN` is set → `WebClient` is initialized without error and execution proceeds normally
  - Error path: `SLACK_BOT_TOKEN` is not set → program exits immediately with a message containing both the variable name and a reference to `.env.example`
  - Edge case: `SLACK_BOT_TOKEN` is set to an empty string → treated as unset (falsy check via `if not token`) → same exit behavior as missing
  - Edge case: `SLACK_BOT_TOKEN` is set to the literal placeholder `your-slack-bot-token-here` → fails the `xoxb-` prefix check → exits with a message indicating the token looks like a placeholder

  **Verification:**
  - Running `SLACK_BOT_TOKEN=test python main.py` reaches the Slack API call (not a startup crash)
  - Running `python main.py` without the env var exits with a clear message, not a traceback

---

- [x] **Unit 2: Add `.env.example` and update `.gitignore`**

  **Goal:** Give contributors a documented config template and ensure a local `.env` file can never be accidentally tracked.

  **Requirements:** R3, R4

  **Dependencies:** None (can run in parallel with Unit 1)

  **Files:**
  - Create: `.env.example`
  - Modify: `.gitignore`

  **Approach:**
  - `.env.example` content: one value line — `SLACK_BOT_TOKEN=your-slack-bot-token-here` (no `export` keyword, so the file stays valid for dotenv tooling). Include two comment lines: one explaining how to copy to `.env`, one recommending `export SLACK_BOT_TOKEN=...` in a shell profile to avoid shell history exposure from inline assignment. Example warning: `# Copy to .env only — variants like .env.local are not gitignored in this repo.`
  - `.gitignore`: add a bare `.env` line **and** a `.env.*` glob (to cover `.env.local`, `.env.dev`, etc.) near the top of the file. The existing `.env/` entry covers directories only; both new entries are needed for flat-file coverage. Note in a comment that `.env/` already existed.

  **Test scenarios:**
  - Test expectation: none — pure configuration file changes with no behavioral logic

  **Verification:**
  - `.env.example` is tracked in git and visible to a fresh clone
  - A new file named `.env` at the repo root is not tracked by `git status`

---

- [x] **Unit 3: Delete `config.py`, update `.gitignore` entry, and update README**

  **Goal:** Remove the old configuration pattern from the codebase and documentation.

  **Requirements:** R2, R5; README update (planning judgment per origin)

  **Dependencies:** Units 1 and 2 must both be complete (Unit 1: `main.py` must not import `config` before `config.py` is deleted; Unit 2: `.gitignore` additions must land before Unit 3's `.gitignore` removal to avoid conflicting edits to the same file)

  **Files:**
  - Delete: `config.py`
  - Modify: `.gitignore` (remove the `config.py` line — line 2)
  - Modify: `README.md`

  **Approach:**
  - Delete `config.py` from the working tree
  - Remove `config.py` from `.gitignore` (line 2)
  - README changes (two locations):
    1. **Installation step 3** (currently "Set up your Slack bot token in `config.py`"): replace with instructions to copy `.env.example` to `.env` and set `SLACK_BOT_TOKEN`. Use only placeholder values in code examples (e.g., `xoxb-your-token-here`) — never a real token.
    2. **Project Structure tree**: replace `config.py` entry with `.env.example` and `.env` (gitignored)

  **Test scenarios:**
  - Test expectation: none — file deletion and documentation update with no behavioral logic

  **Verification:**
  - `config.py` no longer exists in the working tree
  - `git status` after deleting `config.py` shows it as deleted (not ignored)
  - README Installation section no longer references `config.py`

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Live token not rotated before the old `config.py` is deleted | **Pre-flight gate (before Unit 1):** verify token is not in git history (`git log --all -p -- config.py`), then rotate in Slack admin console and record the new value. Do not delete `config.py` until the new token is confirmed working. |
| Shell history exposure if token is passed inline (`SLACK_BOT_TOKEN=... python main.py`) | Document `export SLACK_BOT_TOKEN=...` as the recommended pattern in `.env.example` comments |
| Users with existing local `config.py` who pull this change | `config.py` will still exist locally (gitignored, not deleted by git). Their bot will break until they export `SLACK_BOT_TOKEN`. Note this in the README or commit message. |

## Sources & References

- **Origin document:** [docs/brainstorms/2026-04-11-secure-slack-token-requirements.md](docs/brainstorms/2026-04-11-secure-slack-token-requirements.md)
- Related code: `main.py` lines 5, 8; `.gitignore` lines 2, 39; `README.md` lines 26-30, ~49
