import asyncio

import services.chat_service as chat
from services.case_registry import find_case
from services.precomputed_loader import load_case_bundle
from services.chat_service import build_context, SYSTEM_PROMPT


def test_build_context_includes_qna_and_scores():
    bundle = load_case_bundle(find_case("tsmc"))
    ctx = build_context(bundle)
    assert "Q&A" in ctx or "問題" in ctx
    assert "綜合透明度" in ctx
    assert SYSTEM_PROMPT[:8] in ctx or "你是" in ctx


def test_stream_chat_yields_chunks(monkeypatch):
    class _Chunk:
        def __init__(self, text):
            self.text = text

    class _FakeModel:
        def generate_content(self, contents, stream=False, generation_config=None):
            assert stream is True
            return iter([_Chunk("第 2 題（"), _Chunk("資本支出）為 41 分。")])

    monkeypatch.setattr(chat, "_ChatModel", lambda *_a, **_k: _FakeModel())

    async def collect():
        out = []
        async for piece in chat.stream_chat(
            context="ctx", history=[], user_msg="哪一題分數最低？",
            api_key="k", model="x",
        ):
            out.append(piece)
        return out

    assert asyncio.run(collect()) == ["第 2 題（", "資本支出）為 41 分。"]
