import time

import pytest

from services.slug import make_slug


def test_simple_ascii_lowercased():
    assert make_slug("TSMC Q1") == "tsmc-q1"


def test_chinese_stripped():
    # Chinese stripped → falls back to filename stem or timestamp
    assert make_slug("台積電 2026Q1") == "2026q1"


def test_punctuation_collapsed():
    assert make_slug("nvda__Q4!!") == "nvda-q4"


def test_collision_appends_suffix():
    taken = {"tsmc-q1"}
    assert make_slug("TSMC Q1", taken=taken) == "tsmc-q1-2"

    taken.add("tsmc-q1-2")
    assert make_slug("TSMC Q1", taken=taken) == "tsmc-q1-3"


def test_empty_falls_back_to_timestamp(monkeypatch):
    monkeypatch.setattr(time, "time", lambda: 1_700_000_000)
    assert make_slug("") == "case-1700000000"
    assert make_slug("    ") == "case-1700000000"
    assert make_slug("中文") == "case-1700000000"  # Chinese stripped to empty


def test_trims_leading_trailing_dashes():
    assert make_slug("-Foo-") == "foo"
