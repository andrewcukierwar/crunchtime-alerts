---
date: 2026-04-11
topic: secure-slack-token
---

# Secure Slack Token via Environment Variable

## Problem Frame

The Slack bot token is stored in `config.py` as a plaintext string. While `config.py` is gitignored, the pattern is non-standard: there is no documentation of what the file should contain, no `.env.example` to guide setup, and the current approach won't work in any automated or shared environment without manually creating the file. Moving to `os.environ` makes the configuration explicit, portable, and self-documenting.

## Requirements

- R1. The bot reads `SLACK_BOT_TOKEN` from the environment via `os.environ.get("SLACK_BOT_TOKEN")` in `main.py`, replacing `import config` and `config.bot_token`. If the variable is not set, the program exits immediately with a clear message: `Error: SLACK_BOT_TOKEN is not set. See .env.example for setup instructions.`
- R2. `config.py` is deleted from the repo.
- R3. A `.env.example` file is added to the repo documenting the required environment variable (token value replaced with a placeholder).
- R4. A bare `.env` line is added to `.gitignore` (distinct from the existing `.env/` directory entry, which does not match a flat file) so a local `.env` file can be used for dev without being tracked.
- R5. `config.py` is removed from `.gitignore` (no longer needed as the file won't exist).

## Success Criteria

- Running `SLACK_BOT_TOKEN=xoxb-... python main.py` works correctly.
- A new contributor who clones the repo can determine the required configuration from `.env.example` alone, without reading source code.
- No token value appears anywhere in tracked files.

## Scope Boundaries

- No changes to how the Slack channel name is specified (stays hardcoded in `main.py`).
- `python-dotenv` is not added as a dependency; `.env` loading is left to the user's shell or environment.
- README updates are optional and deferred to planning judgment.

## Key Decisions

- **`os.environ` directly, no python-dotenv:** Keeps the dependency list minimal. The user is responsible for exporting the variable (shell, `.env` file sourced manually, etc.).
