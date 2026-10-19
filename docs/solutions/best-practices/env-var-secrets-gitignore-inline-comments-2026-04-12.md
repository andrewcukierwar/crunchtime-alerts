---
title: "Replacing hardcoded secrets with environment variables and avoiding .gitignore inline comment pitfalls"
date: 2026-04-12
category: docs/solutions/best-practices/
module: crunchtime-alerts
problem_type: best_practice
component: tooling
severity: high
applies_when:
  - "Migrating a hardcoded secret (API token, password, key) to an environment variable in any Python project"
  - "Adding .env patterns to .gitignore for the first time"
  - "A contributor asks 'where do I put my token?' — signal that .env.example is missing"
symptoms:
  - "Secret token lives in a gitignored config file with no onboarding path for contributors"
  - ".gitignore patterns containing inline # comments silently fail to match intended files"
  - ".env.* glob catches .env.example, blocking git add"
root_cause: config_error
resolution_type: code_fix
tags:
  - secrets-management
  - environment-variables
  - gitignore
  - python
  - dotenv
  - inline-comments-gotcha
  - fail-fast
  - onboarding
---

# Replacing hardcoded secrets with environment variables and avoiding .gitignore inline comment pitfalls

## Context

Python CLI projects that authenticate to third-party APIs sometimes store tokens in a config module (e.g., `config.py`) that is gitignored. This pattern is fragile: contributors who clone the repo have no idea the file is required, what variable names it expects, or what format the values take. If the `.gitignore` entry is ever removed, the token is committed. There is no onboarding path and no fail-fast feedback when the token is absent.

The better pattern is to read secrets from environment variables at startup, fail immediately with a clear error if the variable is absent, and commit a `.env.example` file that self-documents what each contributor needs to set.

This refactor was applied to `crunchtime-alerts` (a personal NBA alert Slack bot) to replace `config.py` with `SLACK_BOT_TOKEN`. Two `.gitignore` pitfalls were discovered and fixed during implementation — they are documented here because they fail silently and are easy to introduce without noticing.

## Guidance

### 1. Read the token from the environment at startup, not from a config module

Validate immediately so the program exits with an actionable error rather than a cryptic API exception later.

```python
import os
import sys
from slack_sdk import WebClient

def main():
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        sys.exit("Error: SLACK_BOT_TOKEN is not set. See .env.example for setup instructions.")
    if not token.startswith("xoxb-"):
        sys.exit("Error: SLACK_BOT_TOKEN does not look like a Slack bot token (expected xoxb-...). Check .env.example.")
    client = WebClient(token=token)
```

**Why the `xoxb-` prefix check?** Slack issues different token types: bot tokens start with `xoxb-`, user tokens with `xoxp-`, app-level tokens with `xapp-`. The prefix check catches wrong-type tokens (e.g., pasting a user token into a bot-token field) before they reach the API and produce a confusing auth error. Note: this check does *not* catch the placeholder value `your-slack-bot-token-here` from `.env.example` — that's caught by the falsy check above it.

**`os.environ.get` vs `os.environ[...]`**: Use `.get()`. Bare bracket access raises `KeyError` with no context. `.get()` returns `None`, which you can test with an explicit `if not token` block that prints a human-readable message pointing to `.env.example`.

### 2. Add a committed `.env.example` file

```
# Copy this file to .env and fill in your actual token.
# Copy to .env only — variant filenames like .env.local are not gitignored in this repo.
#
# To avoid exposing the token in shell history, export via your shell profile:
#   export SLACK_BOT_TOKEN=xoxb-your-token-here
# rather than passing it inline on the command line.

SLACK_BOT_TOKEN=your-slack-bot-token-here
```

**Format rules:**
- Use `KEY=VALUE` lines without the `export` prefix — most dotenv tools and shell sourcing patterns expect bare `KEY=VALUE`.
- Put `export` guidance in comments only, not on the value line itself.
- Use a clearly fake placeholder (`your-slack-bot-token-here`, not an actual token format) so accidental verbatim use is caught by the prefix check.

### 3. Update `.gitignore` to cover the secrets file and variants

```gitignore
# Secrets — flat file and variant filenames (.env/ directory entry below covers dirs)
.env
.env.*
!.env.example
```

The `!.env.example` negation is required because `.env.*` matches `.env.example`. See `.gitignore` Gotchas below.

### 4. Remove the config module

Once the token is sourced from the environment, delete `config.py` and remove its `.gitignore` entry. If the live token is in `config.py`, rotate it before deleting:

1. Verify the token was never committed: `git log --all -p -- config.py`
2. Rotate in the service's admin console (e.g., Slack → api.slack.com/apps → OAuth & Permissions)
3. Set the new token: `export SLACK_BOT_TOKEN=xoxb-new-token`
4. Confirm the bot runs, then delete `config.py`

## Why This Matters

- **Security posture**: A gitignored config file is one carelessly edited `.gitignore` away from being committed. Environment variables keep secrets out of the source tree entirely.
- **Contributor onboarding**: Without `.env.example`, a new contributor must read source code to discover what variables are required. A committed example file makes this self-documenting.
- **Fail-fast behavior**: Validating the token at startup means the error surface is a clear, actionable message — not a cryptic exception from inside the Slack SDK after the program has already done work.
- **Shell history hygiene**: The `.env.example` comment nudges contributors toward `export` in their shell profile rather than inline `SLACK_BOT_TOKEN=xoxb-... python main.py`, which would leave the token in shell history.

## When to Apply

Any Python CLI that authenticates to a third-party service using a token, key, or secret — especially when others will clone and run the code. Not needed for non-secret values (public URLs, non-sensitive defaults).

## Examples

**Before: token in a config module**

`config.py` (gitignored, never committed):
```python
bot_token = "xoxb-12345-abcde-..."
```

`main.py`:
```python
import config
from slack_sdk import WebClient

def main():
    client = WebClient(token=config.bot_token)
    # A new contributor who clones this repo gets an ImportError with no guidance
```

**After:** see Guidance section above. Set the token with:
```bash
export SLACK_BOT_TOKEN=xoxb-12345-abcde-...   # add to ~/.zshrc for persistence
```

## .gitignore Gotchas

Both of these fail silently — no error, no warning, the rule simply doesn't work.

### Gotcha 1: Inline comments silently break patterns (session history)

`.gitignore` does **not** support inline comments. A line like:

```
.env   # flat file
```

is not "ignore `.env` (with a comment)". The entire string `.env   # flat file` — including spaces and `#` — becomes the literal pattern. Git silently ignores the actual `.env` file and looks for a file literally named `.env   # flat file`.

**Verification:** `git check-ignore -v .env` — if it returns nothing, the rule is not matching.

**Fix:** Always put comments on their own lines:
```gitignore
# This comment is safe — it's on its own line
.env
```

### Gotcha 2: `.env.*` catches `.env.example`, blocking `git add` (session history)

The glob `.env.*` is useful for catching `.env.local`, `.env.staging`, `.env.production`, etc. But it also matches `.env.example`. Running `git add .env.example` will fail with "path is ignored by one of your .gitignore files".

**Verification:** `git check-ignore -v .env.example` — the last-matching rule shows what's blocking it.

**Fix:** Add a negation rule immediately after the glob. Order matters — git evaluates rules top to bottom, last match wins:

```gitignore
.env.*
!.env.example
```

## Related

- `docs/plans/2026-04-11-001-refactor-secure-slack-token-plan.md` — implementation plan for this refactor
- `docs/brainstorms/2026-04-11-secure-slack-token-requirements.md` — requirements document
- PR: andrewcukierwar/crunchtime-alerts#1
