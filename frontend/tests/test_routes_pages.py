from fastapi.testclient import TestClient

from app import app


def test_landing_lists_three_precomputed_companies():
    response = TestClient(app).get("/")
    assert response.status_code == 200
    body = response.text
    assert "法說會分析" in body
    assert "TSMC" in body and "NVDA" in body and "FOXCONN" in body
    assert "上傳逐字稿" in body


def test_dashboard_renders_all_five_panels():
    response = TestClient(app).get("/case/tsmc")
    assert response.status_code == 200
    body = response.text
    # Hero
    assert "Q&A 透明度評分" in body
    # Radar
    assert "雷達圖" in body
    assert "radar-canvas" in body
    # Insights
    assert "投資洞察" in body
    # Q&A table
    assert "Q&A 摘要表" in body
    assert "分析師問題" in body
    # Risk-label classes present
    assert "risk-direct" in body or "risk-vague" in body or "risk-evasive" in body or "risk-tone" in body
    # Chat panel
    assert "GEMINI 智能問答" in body
