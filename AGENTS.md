# DockerJanitor

Monthly Docker cleanup (untagged images, build cache unused for 7 days) with email reminders, disk-full alerts and a web page. Port 26510 (workspace block 26500-26999). Design: `docs/superpowers/specs/2026-11-26-docker-janitor-design.md`.

## Agent instructions
This file is the one instruction file for every coding agent; `CLAUDE.md` only imports it (`@AGENTS.md`). Edit this file, never `CLAUDE.md`.

## Commands (managed by uv)
- Install: `uv sync`
- Test: `uv run pytest -q` (no Docker daemon or mail server needed)
- Run on a PC: `uv run python tools/dev_run.py` (port 29900, data under `.local/`)
- Deploy: see `deployment.md`

## Rules
- Never add a delete operation other than the two prunes in `src/janitor/cleaner.py`. Volumes, containers and tagged images are never removed.
- A scheduled run happens only after its reminder email was sent with the full notice. When in doubt, do not run.
- No `.env` and no config files: settings live in SQLite, edited on the page.
- The SMTP password is stored encrypted (key in the `/key` volume), the admin password only as a scrypt hash. Never log or return either.
- UI uses relative URLs only (ServiceHub frames it); `GET /health` answers without auth and without calling Docker.
- Commit with the noreply author email `214214011+scutiii2@users.noreply.github.com`.
