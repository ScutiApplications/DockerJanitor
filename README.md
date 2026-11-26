# DockerJanitor

Cleans old Docker data once a month, emails you before and after, warns when a disk is nearly full, and is controlled from a web page on port 26510.

- Removes untagged images and build cache unused for 7 days. Each can be switched off.
- Never removes volumes, containers or tagged images.
- Sends a reminder some days before a run. You can skip, postpone or run it now. If the reminder cannot be sent, the run waits.
- Checks two disks every hour and emails at the warning level, at most weekly per disk.

All settings are edited on the page and stored in SQLite. Install: [deployment.md](deployment.md).
