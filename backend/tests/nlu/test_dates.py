"""
tests/nlu/test_dates.py – Date parser unit tests.
"""
from datetime import date, timedelta
import pytest
from assistant.brain.nlu.dates import parse_date


TODAY = date(2026, 10, 26)  # Monday


def test_today():
    r = parse_date("today", TODAY)
    assert r.date == TODAY


def test_tomorrow():
    r = parse_date("tomorrow", TODAY)
    assert r.date == TODAY + timedelta(days=1)


def test_weekday_strict_next():
    # Today is Monday; "monday" alone should give +7
    r = parse_date("monday", TODAY)
    assert r.date == TODAY + timedelta(days=7)


def test_friday_next():
    r = parse_date("friday", TODAY)
    assert r.date == date(2026, 10, 30)


def test_this_friday():
    r = parse_date("this friday", TODAY)
    assert r.date == date(2026, 10, 30)


def test_next_week():
    r = parse_date("next week", TODAY)
    assert r.hint == "NEXT_WEEK"
    assert r.week_anchor is not None


def test_earliest():
    r = parse_date("as soon as possible", TODAY)
    assert r.pref_mode == "EARLIEST"


def test_numeric_date():
    r = parse_date("11/3", TODAY)
    assert r.date is not None
    assert r.date.month == 11
    assert r.date.day == 3


def test_month_word_day():
    r = parse_date("november 3", TODAY)
    assert r.date == date(2026, 11, 3)


def test_trailing_morning_window():
    r = parse_date("friday morning", TODAY)
    assert r.date == date(2026, 10, 30)
    assert r.time_window == "MORNING"


def test_trailing_afternoon_window():
    r = parse_date("friday afternoon", TODAY)
    assert r.date == date(2026, 10, 30)
    assert r.time_window == "AFTERNOON"
