"""
tests/nlu/test_services.py – Service extraction unit tests.
"""
from assistant.brain.nlu.services import extract_services
from assistant.brain.types import Polarity


def test_cleaning():
    results = extract_services("i need a cleaning")
    assert any(e.value == "cleaning" and e.polarity == Polarity.POS for e in results)


def test_checkup_synonym():
    results = extract_services("i want an exam")
    assert any(e.value == "checkup" for e in results)


def test_filling_not_fill_out():
    """'fill out' must not extract FILLING (whole-word rule)."""
    results = extract_services("can you fill out the form")
    assert not any(e.value == "filling" for e in results)


def test_root_canal():
    results = extract_services("i need a root canal")
    assert any(e.value == "root_canal" for e in results)


def test_negated_service():
    results = extract_services("not a cleaning, a checkup")
    cleaning = [e for e in results if e.value == "cleaning"]
    assert all(e.polarity == Polarity.NEG for e in cleaning)
    checkup = [e for e in results if e.value == "checkup"]
    assert any(e.polarity == Polarity.POS for e in checkup)


def test_extraction_exam_not_example():
    """'exam' must match but 'example' must NOT (whole-word rule)."""
    results = extract_services("for example a cleaning")
    # "example" contains "exam" but should NOT trigger checkup
    assert not any(e.value == "checkup" for e in results)
