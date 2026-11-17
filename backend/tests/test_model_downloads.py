import hashlib
import json
import threading
import time
from contextlib import contextmanager

import pytest

PAYLOAD = bytes(range(256)) * 64
SHA = hashlib.sha256(PAYLOAD).hexdigest()


@pytest.fixture
def fake_model(monkeypatch, client):
    import httpx

    from app.ai import models

    name = f"test-dl/{time.monotonic_ns()}.bin"
    monkeypatch.setitem(models.MODELS, "testdl", {"name": "Test download", "license": "MIT", "size": 1, "files": {name: ("https://example.invalid/x.bin", SHA)}})
    fetched = []

    class Stream:
        headers = {"content-length": str(len(PAYLOAD))}

        def raise_for_status(self):
            return None

        def iter_bytes(self, n):
            for i in range(0, len(PAYLOAD), 1024):
                time.sleep(0.002)
                yield PAYLOAD[i:i + 1024]

    @contextmanager
    def stream(method, url, **kw):
        fetched.append(url)
        yield Stream()

    monkeypatch.setattr(httpx, "stream", stream)
    return {"name": name, "fetched": fetched}


def test_two_downloads_of_one_model_at_once_leave_one_good_file(fake_model):
    from app.ai import models

    errors = []

    def run():
        try:
            models.download("testdl")
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(30)
    assert not errors
    assert models.path(fake_model["name"]).read_bytes() == PAYLOAD
    assert models.ready("testdl")
    assert len(fake_model["fetched"]) == 1
    assert not list(models.path(fake_model["name"]).parent.glob("*.download"))
    assert "testdl" not in models._downloading


def test_a_file_without_a_matching_sidecar_is_not_installed(fake_model):
    from app.ai import models

    target = models.path(fake_model["name"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(PAYLOAD)
    assert not models.ready("testdl")
    models._sidecar(fake_model["name"]).write_text(json.dumps({"sha256": "0" * 64}))
    assert not models.ready("testdl")
    models._sidecar(fake_model["name"]).write_text(json.dumps({"sha256": SHA}))
    assert models.ready("testdl")


def test_a_wrong_sidecar_is_downloaded_again(fake_model):
    from app.ai import models

    target = models.path(fake_model["name"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"x" * 4096)
    models._sidecar(fake_model["name"]).write_text(json.dumps({"sha256": "f" * 64}))
    models.download("testdl")
    assert target.read_bytes() == PAYLOAD and models.ready("testdl")


def test_ai_download_returns_the_task_already_running(commands, monkeypatch):
    from app.ai import models
    from app.engine import tasks

    release = threading.Event()
    calls = []

    def slow(model, progress=None):
        calls.append(model)
        release.wait(10)
        return {"model": model, "ready": False}

    monkeypatch.setattr(models, "download", slow)
    first = commands("ai.download", {"model": "sky"})
    second = commands("ai.download", {"model": "sky"})
    other = commands("ai.download", {"model": "depth"})
    release.set()
    assert first["task"] == second["task"]
    assert other["task"] != first["task"]
    tasks.wait(first["task"], 10)
    tasks.wait(other["task"], 10)
    third = commands("ai.download", {"model": "sky"})
    tasks.wait(third["task"], 10)
    assert third["task"] != first["task"]
