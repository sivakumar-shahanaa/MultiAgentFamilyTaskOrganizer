import httpx

from app.integrations.spotify_client import add_to_queue


class _FakeClient:
    def __init__(self, status_code: int):
        self.status_code = status_code

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def post(self, *args, **kwargs):
        return httpx.Response(self.status_code, request=httpx.Request("POST", "http://test"))


def test_add_to_queue_accepts_any_2xx_status(monkeypatch):
    monkeypatch.setattr(httpx, "Client", lambda timeout: _FakeClient(200))

    assert add_to_queue("spotify:track:1", "token") is True


def test_add_to_queue_rejects_non_2xx_status(monkeypatch):
    monkeypatch.setattr(httpx, "Client", lambda timeout: _FakeClient(404))

    assert add_to_queue("spotify:track:1", "token") is False
