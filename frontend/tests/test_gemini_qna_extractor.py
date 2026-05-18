import json

import services.gemini_qna_extractor as extractor


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModel:
    def __init__(self, *_, **__):
        self.calls: list[str] = []

    def generate_content(self, prompt, generation_config=None):
        self.calls.append(prompt)
        return _FakeResponse(json.dumps({
            "qna_list": [
                {"question": "What about AI demand?", "answer": "It's very strong."},
                {"question": "", "answer": "too short"},  # filtered downstream
            ]
        }))


def test_extract_returns_validated_pairs(monkeypatch):
    fake = _FakeModel()
    monkeypatch.setattr(extractor, "_GenerativeModel", lambda *_a, **_k: fake)
    pairs = extractor.extract_qna_from_chunk("chunk text", api_key="k", model="gemini-2.0-flash")
    assert pairs == [
        {"question": "What about AI demand?", "answer": "It's very strong."},
    ]
    assert "chunk text" in fake.calls[0]


def test_extract_retries_on_failure(monkeypatch):
    calls = {"n": 0}

    class _FailingModel:
        def generate_content(self, prompt, generation_config=None):
            calls["n"] += 1
            if calls["n"] < 3:
                raise RuntimeError("transient")
            return _FakeResponse(json.dumps({"qna_list": [{"question": "Q?", "answer": "A!"}]}))

    monkeypatch.setattr(extractor, "_GenerativeModel", lambda *_a, **_k: _FailingModel())
    monkeypatch.setattr(extractor.time, "sleep", lambda _s: None)
    pairs = extractor.extract_qna_from_chunk("c", api_key="k", model="x")
    assert pairs == [{"question": "Q?", "answer": "A!"}]
    assert calls["n"] == 3
