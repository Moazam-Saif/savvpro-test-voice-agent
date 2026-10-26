"""
tests/nlu/test_normalize.py – Normalization unit tests.
"""
from assistant.brain.normalize import normalize


def test_lowercase():
    assert normalize("HELLO WORLD") == "hello world"


def test_curly_quotes():
    assert "\u2018" not in normalize("it\u2018s fine")


def test_am_pm():
    assert "am" in normalize("10 a.m.")
    assert "pm" in normalize("3 p.m.")


def test_oclock_dropped():
    assert "o'clock" not in normalize("three o'clock")


def test_number_words():
    result = normalize("five thirty pm")
    assert "5" in result
    assert "30" in result


def test_strip_punct():
    result = normalize("Hello! World?")
    assert "!" not in result
    assert "?" not in result


def test_keep_colon():
    assert ":" in normalize("3:30 pm")


def test_collapse_whitespace():
    result = normalize("  hello   world  ")
    assert result == "hello world"
