"""Natural-English paraphrase coverage for the documented NLU vocabulary."""
from datetime import date

import pytest

from assistant.brain.nlu.commands import Command, detect_command
from assistant.brain.nlu.dates import parse_date
from assistant.brain.nlu.intents import score_intents
from assistant.brain.nlu.names import extract_name
from assistant.brain.normalize import normalize
from assistant.brain.nlu.services import extract_services
from assistant.brain.nlu.times import parse_time
from assistant.brain.nlu.yesno import extract_yesno
from assistant.brain.types import Intent, Polarity


TODAY = date(2026, 10, 26)


@pytest.mark.parametrize(
    ("text", "intent"),
    [
        ("I need to come in", Intent.BOOK),
        ("Could you schedule me for a cleaning?", Intent.BOOK),
        ("When can you fit me in?", Intent.BOOK),
        ("I'd like to see the dentist", Intent.BOOK),
        ("I can't make my appointment", Intent.CANCEL),
        ("Please call off my appointment", Intent.CANCEL),
        ("Can you move my appointment?", Intent.RESCHEDULE),
        ("What time do you open?", Intent.INFO_HOURS),
        ("How long does a filling take?", Intent.INFO_DURATION),
        ("What treatments do you offer?", Intent.INFO_SERVICES),
    ],
)
def test_intent_paraphrases(text, intent):
    result = score_intents(text)
    assert result.best() == intent


@pytest.mark.parametrize(
    ("text", "command"),
    [
        ("Could you repeat that, please?", Command.REPEAT),
        ("Hold on a second", Command.HOLD),
        ("Never mind", Command.START_OVER),
        ("I need to speak to an operator", Command.HUMAN),
        ("That's all, goodbye", Command.BYE),
        ("Are you a real person?", Command.ROBOT),
    ],
)
def test_global_command_paraphrases(text, command):
    assert detect_command(text) == command


def test_command_does_not_eat_booking_content():
    assert detect_command("Please repeat the appointment for Friday", anything_extracted=True) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("half past five", (5, 30)),
        ("quarter past 3", (3, 15)),
        ("quarter to six", (5, 45)),
        ("noon", (12, 0)),
        ("midday", (12, 0)),
        ("5:30 pm", (17, 30)),
        ("17:30", (17, 30)),
    ],
)
def test_time_paraphrases(text, expected):
    result = parse_time(normalize(text))
    assert result.time is not None
    assert (result.time.hour, result.time.minute) == expected


def test_evening_is_not_guessed_as_a_bookable_time():
    assert parse_time("this evening").out_of_hours is True


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("the day after tomorrow", date(2026, 10, 28)),
        ("in 3 days", date(2026, 10, 29)),
        ("the 3rd", date(2026, 11, 3)),
        ("3 November", date(2026, 11, 3)),
        ("October 30th", date(2026, 10, 30)),
        ("10-30", date(2026, 10, 30)),
    ],
)
def test_date_paraphrases(text, expected):
    result = parse_date(text, TODAY)
    assert result.date == expected


def test_conflicting_date_language_is_reported():
    result = parse_date("Friday the 3rd", TODAY)
    assert result.conflict is not None


def test_weekend_phrase_returns_a_weekend_hint():
    result = parse_date("this weekend", TODAY)
    assert result.hint == "THIS_WEEKEND"
    assert result.week_anchor == date(2026, 10, 31)


@pytest.mark.parametrize(
    "text",
    [
        "a scale and polish",
        "a hygiene appointment",
        "a cavity filling",
        "to have a tooth pulled",
        "remove a tooth",
        "a consultation",
        "bleaching",
    ],
)
def test_service_paraphrases_are_positive(text):
    results = extract_services(text)
    assert any(item.polarity == Polarity.POS for item in results)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("My name is Sarah Thompson", "Sarah Thompson"),
        ("This is Ali Raza", "Ali Raza"),
        ("John speaking", "John"),
        ("I'm Maria Gonzalez", "Maria Gonzalez"),
    ],
)
def test_name_paraphrases(text, expected):
    name, for_other, direct_patient = extract_name(text)
    assert name == expected
    assert for_other is False
    assert direct_patient is None


def test_name_for_someone_else_paraphrase():
    name, for_other, direct_patient = extract_name("for my daughter Ali")
    assert name == "Ali"
    assert for_other is True
    assert direct_patient == "Ali"


@pytest.mark.parametrize("text", ["yes", "yeah", "sure", "that works", "go ahead", "please do"])
def test_confirmation_paraphrases(text):
    assert extract_yesno(text) == "yes"


@pytest.mark.parametrize("text", ["no", "nope", "that's wrong", "incorrect", "not really"])
def test_rejection_paraphrases(text):
    assert extract_yesno(text) == "no"


def test_mixed_yes_and_no_is_not_confirmation():
    assert extract_yesno("yes, no, make it Saturday") is None
