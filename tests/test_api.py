import pytest
from fastapi.testclient import TestClient

from janitor import app as app_module
from janitor.app import create_app

PASSWORD = "correct horse battery"
AUTH = {"X-Admin-Password": "correct%20horse%20battery"}


@pytest.fixture
def setup(janitor, monkeypatch, capsys):
    monkeypatch.setattr(app_module, "WRONG_PASSWORD_DELAY", 0)
    with TestClient(create_app(janitor, tick_seconds=None)) as client:
        yield client, capsys.readouterr().out.split()[-1]


def finish_setup(client, code):
    return client.post("api/setup", json={"code": code, "password": PASSWORD})


def test_nothing_works_before_setup_and_setup_works_once(setup):
    client, code = setup
    assert client.get("health").status_code == 200
    assert client.get("api/status").json() == {"setup_done": False}
    assert client.post("api/run", headers=AUTH).status_code == 403
    assert finish_setup(client, code).status_code == 200
    assert finish_setup(client, code).status_code == 409
    assert client.get("api/overview").status_code == 401
    assert client.get("api/overview", headers={"X-Admin-Password": "nope"}).status_code == 401
    assert client.get("api/overview", headers=AUTH).status_code == 200


def test_setup_locks_after_five_wrong_codes(setup):
    client, code = setup
    for _ in range(5):
        assert finish_setup(client, "wrong").status_code == 403
    assert finish_setup(client, code).status_code == 403


def test_smtp_password_is_sealed_kept_and_never_returned(setup, janitor, mail):
    client, code = setup
    finish_setup(client, code)
    settings = client.get("api/overview", headers=AUTH).json()["settings"]
    assert client.put("api/settings", headers=AUTH, json={**settings, "smtp_password": "s3cret-value"}).status_code == 200
    assert client.put("api/settings", headers=AUTH, json={**settings, "smtp_password": ""}).status_code == 200
    overview = client.get("api/overview", headers=AUTH)
    assert "s3cret-value" not in overview.text and overview.json()["smtp_password_set"] is True
    assert b"s3cret-value" not in janitor.store.path.read_bytes()
    assert client.post("api/test-email", headers=AUTH).status_code == 200
    assert mail.passwords == ["s3cret-value"]


def test_bad_settings_are_refused(setup):
    client, code = setup
    finish_setup(client, code)
    assert client.put("api/settings", headers=AUTH, json={"day": 31}).status_code == 422
    assert client.put("api/settings", headers=AUTH, json={"timezone": "Mars/Base"}).status_code == 422
    assert client.post("api/postpone", headers=AUTH, json={"days": 0}).status_code == 422
