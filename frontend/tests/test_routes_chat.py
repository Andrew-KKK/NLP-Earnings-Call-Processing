from fastapi.testclient import TestClient

from app import app


def test_chat_returns_sse(monkeypatch):
    async def fake_stream(**_kwargs):
        yield "你好"
        yield "，"
        yield "這裡是回覆。"

    monkeypatch.setattr("routes.chat._stream_chat", fake_stream)

    client = TestClient(app)
    with client.stream("GET", "/chat/stream", params={"case": "tsmc", "msg": "hi"}) as response:
        assert response.status_code == 200
        body = "".join(chunk for chunk in response.iter_text())
    assert "你好" in body and "回覆" in body
