# DockerJanitor design

Date: 2026-11-26. Status: awaiting review.

## Purpose
The deployment machine fills up with old Docker data. DockerJanitor cleans it once a month, warns by email before it does, warns when a disk is nearly full, and is controlled from a web page.

## Shape
- Project `Applications/DockerJanitor`, one container, host port `26510`.
- Python, FastAPI, Docker SDK, `smtplib`, one static HTML page, managed by uv.
- One asyncio scheduler loop inside the app, waking once a minute. Docker, SMTP and disk calls run in worker threads.
- Settings, next run date and history live in one JSON file in the `/data` volume, written atomically.
- One process only, one run at a time (a second request gets 409).

## What a run deletes
| Item | Rule | Default |
|---|---|---|
| Untagged images | `images.prune` with `dangling=true` | on |
| Build cache | unused for 7 days (`all`, `until=168h`) | on |

Volumes, containers and tagged images are never deleted. The code calls no other delete operation.

## Schedule
- Settings: day of month (1 to 28), hour, reminder days before (default 3). Times use `TZ`.
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
- Defaults: `/disks/system` (host `/DATA/.diskprobe`) and `/disks/backup` (host `/media/HDD320-1/.diskprobe`). Host paths come from `.env`.
- Alert at 85% used or more (setting), at most once per 7 days per disk. Falling below the threshold resets it.
- A disk that cannot be read shows as "unreadable" on the page and is reported in the same alert email.
- If the probe folder is not really on that disk (disk unmounted), the figures are those of the parent disk. The deploy steps say to check them once.

## Web page and API
- Shows: next run, reminder state, last error, disks, preview, history (last 50), settings.
- Actions: Preview, Run now, Skip, Postpone, Save settings, Send test email.
- Every `/api` call, reads included, needs header `X-Admin-Password` equal to `ADMIN_PASSWORD` (constant-time compare). Empty `ADMIN_PASSWORD` disables them all with 403. The scheduler then does not run either, because nobody could skip a run.
- `GET /health` and the static page need no password. `/health` does not call Docker.
- Relative URLs only, so ServiceHub can frame it.
- Preview lists dangling images with sizes and reclaimable build cache. `docker df` can be slow, so the page shows a busy state.

## Configuration
`.env` (untracked, with `.env.example`): `ADMIN_PASSWORD`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY` (`starttls` or `ssl`), `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `MAIL_TO`, `TZ`, `SYSTEM_PROBE_DIR`, `BACKUP_PROBE_DIR`, `SERVICE_BIND`.

Schedule, threshold and cleanup switches are edited on the page, not in `.env`.

## Security
The Docker socket is root-equivalent on the host (same method as ServiceHub). Keep the service on the LAN. The password travels over plain HTTP on that LAN. Secrets are never logged or returned by the API.

## Deploy
Copy the folder to `/media/ZimaOS-HD/Apps/Applications/DockerJanitor`, create the two probe folders, fill in `.env`, `docker compose up -d --build`. Compose has `extra_hosts: host.docker.internal:host-gateway`.

## Tests
- Schedule logic with a fake clock: reminder, run, skip, postpone, failed email, downtime.
- Delete calls with a fake Docker client: only the two prune operations, with the filters above; switches off.
- API: password required, empty password disables.
- Email and Docker are faked. No Docker daemon is needed for tests.

## Not included
GitHub repository and `live` branch deploy, several recipients, SMS or chat messages, container control (ServiceHub does that).
