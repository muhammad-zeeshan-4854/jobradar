from datetime import timezone

import pytest

from jobradar.utils import looks_remote, parse_datetime, parse_salary, strip_html


@pytest.mark.parametrize("text,expected", [
    ("$80k - $100k", (80000, 100000, "USD")),
    ("60,000 - 75,000 EUR", (60000, 75000, "EUR")),
    ("£45k", (45000, 45000, "GBP")),
    ("$40/hour", (None, None, "USD")),
    ("Competitive", (None, None, None)),
    (None, (None, None, None)),
])
def test_parse_salary(text, expected):
    assert parse_salary(text) == expected


def test_strip_html_unescapes_and_truncates():
    out = strip_html("<p>Hello&nbsp;<b>world</b></p>" + " word" * 200, max_len=40)
    assert out.startswith("Hello world")
    assert out.endswith("…")
    assert len(out) <= 41


def test_parse_datetime_formats():
    assert parse_datetime(1700000000).tzinfo == timezone.utc
    assert parse_datetime("2024-05-01T10:00:00").tzinfo == timezone.utc
    assert parse_datetime("2024-05-01T10:00:00Z").hour == 10
    assert parse_datetime("not a date") is None
    assert parse_datetime(None) is None


def test_looks_remote():
    assert looks_remote("Remote - Europe")
    assert looks_remote("Anywhere")
    assert not looks_remote("Berlin")
