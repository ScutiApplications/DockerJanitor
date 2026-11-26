# Deploying DockerJanitor

Target: `/media/ZimaOS-HD/Apps/Applications/DockerJanitor` on the deployment machine. Port 26510.

The Docker socket gives this container root-level control of the machine. Keep it on the LAN.

## 1. Copy the code (PowerShell, on your PC)

```powershell
cd D:\User\Documents\Programming\Applications\DockerJanitor
git archive --format=tar.gz -o "$env:TEMP\dockerjanitor.tar.gz" HEAD
scp "$env:TEMP\dockerjanitor.tar.gz" lex@scutiserver1.local:/tmp/
```

## 2. Start (on the machine)

```bash
mkdir -p /media/ZimaOS-HD/Apps/Applications/DockerJanitor
cd /media/ZimaOS-HD/Apps/Applications/DockerJanitor
tar -xzf /tmp/dockerjanitor.tar.gz
mkdir -p /DATA/.diskprobe /media/HDD320-1/.diskprobe
docker compose up -d --build
docker compose logs
```

Check once that each probe folder is on its own disk (the two lines must show different filesystems):

```bash
df -h /DATA/.diskprobe /media/HDD320-1/.diskprobe
```

Other disk paths: edit the two probe lines in `docker-compose.yml`.

## 3. First setup (in the browser)

1. Open `http://<machine-ip>:26510`.
2. Enter the setup code from `docker compose logs` and a new admin password.
3. Fill in the email settings, save, and use **Send test email**. Gmail: host `smtp.gmail.com`, port 587, STARTTLS, an app password.
4. Check the next run date. Scheduled runs happen only if the reminder email can be sent.
5. Optional: add it in ServiceHub (Discover).

## Update

Repeat step 1, then in the project folder: `tar -xzf /tmp/dockerjanitor.tar.gz && docker compose up -d --build`. Settings stay in the volumes.

## Forgot the password

```bash
docker compose exec docker_janitor python -m janitor reset-password
docker compose restart
docker compose logs --tail 20
```
