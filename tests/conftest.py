"""Fakes for Docker, email, disks and time. No Docker daemon or mail server is used."""
from datetime import datetime, timedelta, timezone

import pytest

from janitor.security import SecretBox
from janitor.service import Janitor
from janitor.settings import Settings
from janitor.store import Store


class Clock:
    def __init__(self):
        self.now = datetime(2026, 11, 20, 0, 0, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def to(self, month, day, hour=0, minute=0):
        self.now = datetime(2026, month, day, hour, minute, tzinfo=timezone.utc)

    def forward(self, **delta):
        self.now += timedelta(**delta)


class Mail:
    def __init__(self):
        self.sent, self.passwords, self.broken = [], [], False

    def __call__(self, settings, password, message):
        if self.broken:
            raise OSError("mail server down")
        self.sent.append(message)
        self.passwords.append(password)

    @property
    def subjects(self):
        return [m["Subject"].removeprefix("[DockerJanitor] ") for m in self.sent]


class FakeCleaner:
    def __init__(self):
        self.runs = []

    async def preview(self, images, cache):
        return {"images": {"count": 2, "bytes": 500}}

    async def run(self, images, cache):
        self.runs.append((images, cache))
        return {"images": {"count": 2, "bytes": 500}}


class FakeDisks:
    def __init__(self):
        self.percent = 10

    async def read(self):
        return [{"name": "system", "percent": self.percent, "free": 1, "total": 2, "error": ""}]


# UTC and hour 0 keep the dates in the tests readable.
SETTINGS = Settings(day=1, hour=0, reminder_days=3, timezone="UTC", smtp_host="mail.test",
                    mail_from="janitor@example.com", mail_to="admin@example.com")


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def mail():
    return Mail()


@pytest.fixture
def janitor(tmp_path, clock, mail):
    store = Store(tmp_path / "janitor.db")
    store.set_sync("settings", SETTINGS.model_dump())
    return Janitor(store, SecretBox(tmp_path / "key" / "secret.key"), FakeCleaner(), FakeDisks(), mail, clock)
