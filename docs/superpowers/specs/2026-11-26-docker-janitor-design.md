# DockerJanitor design

Date: 2026-11-26. Status: awaiting review.

## Purpose
The deployment machine fills up with old Docker data. DockerJanitor cleans it once a month, warns by email before it does, warns when a disk is nearly full, and is controlled from a web page.

## Shape
- Project `Applications/DockerJanitor`, one container, host port `26510`.
- Python, FastAPI, Docker SDK, `smtplib`, one static HTML page, managed by uv.
- One asyncio scheduler loop inside the app, waking once a minute. Docker, SMTP and disk calls run in worker threads.
- All settings, state and history live in one SQLite database in the `/data` volume.
- One process only, one run at a time (a second request gets 409).

## What a run deletes
| Item | Rule | Default |
|---|---|---|
| Untagged images | `images.prune` with `dangling=true` | on |
| Build cache | unused for 7 days (`all`, `until=168h`) | on |

Volumes, containers and tagged images are never deleted. The code calls no other delete operation.

## Schedule
- Settings: day of month (1 to 28), hour, reminder days before (default 3), time zone (default `Asia/Manila`).
- At `run date - reminder days` the app emails a reminder with the preview.
- On the run date it runs, then emails the result: freed space per item, free space per disk, errors.
- **Skip** moves the run to next month. **Postpone** moves it N days (1 to 27). Both require a new reminder.
- **Run now** runs at once, needs no reminder, and leaves the scheduled date unchanged.
- Auto-run happens only if a reminder for that run date was sent at least `reminder days` earlier.
- If the reminder cannot be sent, the app retries hourly, does not run, and shows why on the page.
- If the app was down past a reminder or run time, it sends the reminder first and moves the run date to `today + reminder days`.
- With reminder days 0, the reminder and the run happen together; the run still needs the email to send.
- A failed run is recorded and reported by email, then the date moves to next month. No automatic retry.

## Disk alert
- Hourly check. Each watched disk is an empty probe folder on that disk, mounted read-only, measured with `shutil.disk_usage`. The container cannot read other files on the disks.
- Two disks: `/disks/system` (host `/DATA/.diskprobe`) and `/disks/backup` (host `/media/HDD320-1/.diskprobe`). Host paths are written in `docker-compose.yml`, because Docker mounts them before the app starts.
- Alert at 85% used or more (setting), at most once per 7 days per disk. Falling below the threshold resets it.
- A disk that cannot be read shows as "unreadable" on the page and is reported in the same alert email.
- If the probe folder is not really on that disk (disk unmounted), the figures are those of the parent disk. The deploy steps say to check them once.

## Web page and API
- Shows: next run, reminder state, last error, disks, preview, history (last 50), settings.
- Actions: Preview, Run now, Skip, Postpone, Save settings, Send test email.
- Every `/api` call except setup, reads included, needs header `X-Admin-Password` (checked against the stored hash, constant-time compare).
- `GET /health`, `GET /api/status` (says only whether setup is done) and the static page need no password. `/health` does not call Docker.
- Relative URLs only, so ServiceHub can frame it.
- Preview lists dangling images with sizes and reclaimable build cache. `docker df` can be slow, so the page shows a busy state.

## Configuration
No `.env` and no config files. Everything is stored in the database and edited on the page: SMTP host, port, security (`starttls` or `ssl`), user, password, sender, recipient, time zone, schedule, disk threshold, cleanup switches. Port and disk mounts are fixed in `docker-compose.yml`.

## First setup
- With no admin password stored, the app writes a random setup code to its log at each start. Read it with `docker compose logs`.
- The page asks for that code and a new password (at least 10 characters). Only this setup call works until then, and the scheduler stays off.
- Setup works once. Five wrong codes lock it until restart.
- Forgotten password: `docker compose exec docker_janitor python -m janitor reset-password` clears it. Restart to get a new setup code. This needs shell access to the host.

## Security
- The Docker socket is root-equivalent on the host (same method as ServiceHub). Keep the service on the LAN. The password travels over plain HTTP on that LAN.
- Admin password: stored only as a salted scrypt hash.
- SMTP password: encrypted (Fernet). The key file is in its own volume `/key`, apart from the database. This protects a copied database, not a compromised host.
- Secrets are never logged or returned by the API. The page shows only whether the SMTP password is set; an empty field keeps it.

## Deploy
Copy the folder to `/media/ZimaOS-HD/Apps/Applications/DockerJanitor`, create the two probe folders, `docker compose up -d --build`, then do the first setup on the page. Compose has `extra_hosts: host.docker.internal:host-gateway`, binds `0.0.0.0`, and has two named volumes (`/data`, `/key`).

## Tests
- Schedule logic with a fake clock: reminder, run, skip, postpone, failed email, downtime.
- Delete calls with a fake Docker client: only the two prune operations, with the filters above; switches off.
- API: password required; setup code, lockout and one-time setup; SMTP password never returned and not stored as plain text.
- Email and Docker are faked. No Docker daemon is needed for tests.

## Not included
GitHub repository and `live` branch deploy, several recipients, SMS or chat messages, container control (ServiceHub does that).
