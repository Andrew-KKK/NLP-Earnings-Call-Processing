from fastapi.testclient import TestClient

from app import app


def test_landing_then_dashboard_then_partial_for_tsmc():
    client = TestClient(app)

    landing = client.get("/")
    assert landing.status_code == 200
    assert "TSMC" in landing.text

    dash = client.get("/case/tsmc")
    assert dash.status_code == 200
    assert "雷達圖" in dash.text
    assert "Q&A 摘要表" in dash.text
    assert "GEMINI" in dash.text

    partial = client.get("/api/case/tsmc/qna")
    assert partial.status_code == 200
    assert "<table" in partial.text


def test_unknown_case_returns_404():
    response = TestClient(app).get("/case/does-not-exist")
    assert response.status_code == 404
