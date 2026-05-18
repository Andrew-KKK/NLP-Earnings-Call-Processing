from fastapi.testclient import TestClient

from app import app


def test_partial_returns_table_rows_only():
    response = TestClient(app).get("/api/case/tsmc/qna")
    assert response.status_code == 200
    body = response.text
    assert "<table" in body
    assert "分析師問題" in body
    assert "<html" not in body and "<body" not in body
