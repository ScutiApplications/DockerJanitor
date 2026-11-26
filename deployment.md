# Deploying DockerJanitor

Target: `/media/ZimaOS-HD/Apps/Applications/DockerJanitor` on the deployment machine. Port 26510.

The Docker socket gives this container root-level control of the machine. Keep it on the LAN.

## 1. Publish the code (on your PC)

The machine takes the code from GitHub, so commit and push `main` first:

```powershell
git -C D:\User\Documents\Programming\Applications\DockerJanitor push
```

## 2. Clone and start (on the machine)

The repository is private: the machine needs GitHub access (a saved login, token or SSH key).

```bash
mkdir -p /media/ZimaOS-HD/Apps/Applications
git clone https://github.com/ScutiApplications/DockerJanitor.git /media/ZimaOS-HD/Apps/Applications/DockerJanitor
cd /media/ZimaOS-HD/Apps/Applications/DockerJanitor
mkdir -p /DATA/.diskprobe
docker compose up -d --build
docker compose ps
```

Optional second disk (for example a backup disk): create `.diskprobe` on it, remove the `#` from its line in `docker-compose.yml`, set the path, and run `docker compose up -d` again. Without that line the disk is not shown and sends no warning.

Check once that each probe folder is on its own disk (the lines must show different filesystems):

```bash
df -h /DATA/.diskprobe /media/<backup-disk>/.diskprobe
```

## 3. First setup (in the browser)

1. Read the setup code on the machine: `docker compose logs | grep "setup code"` (use the last line).
2. Open `http://<machine-ip>:26510`, enter the code and a new admin password.
3. Fill in the email settings, save, and use **Send test email**. Gmail: host `smtp.gmail.com`, port 587, STARTTLS, an app password.
4. Check the next run date. Scheduled runs happen only if the reminder email can be sent.
5. Optional: add it in ServiceHub (Discover).

## Update

Push from your PC (step 1), then on the machine:

```bash
cd /media/ZimaOS-HD/Apps/Applications/DockerJanitor
git pull
docker compose up -d --build
```

Settings stay in the volumes.

If you edited `docker-compose.yml` for a second disk and `git pull` refuses, keep your edit like this:

```bash
git stash
git pull
git stash pop
```

## Forgot the password

```bash
cd /media/ZimaOS-HD/Apps/Applications/DockerJanitor
docker compose exec docker_janitor python -m janitor reset-password
docker compose restart
docker compose logs --tail 20
```
