import pytest

from jobradar.sources import SourceError, get_source
from tests.conftest import FakeResponse, FakeSession

REMOTIVE = {"jobs": [{
    "id": 101, "url": "https://remotive.com/1", "title": "Python Engineer",
    "company_name": "Acme", "tags": ["Python", "AWS"], "publication_date": "2026-09-29T08:00:00",
    "candidate_required_location": "Europe", "salary": "$70k - $90k", "description": "<p>Hi</p>",
}]}
REMOTEOK = [
    {"legal": "notice"},
    {"id": "202", "position": "Backend Dev", "company": "Beta", "tags": ["go"], "epoch": 1759200000,
     "salary_min": 80000, "salary_max": 0, "url": "https://remoteok.com/202", "location": ""},
]
ARBEITNOW_P1 = {"data": [{"slug": "dev-1", "title": "Dev", "company_name": "Gamma", "remote": False,
                          "location": "Berlin", "tags": ["php"], "job_types": ["full time"],
                          "created_at": 1759200000, "url": "https://arbeitnow.com/1"}],
                "links": {"next": "https://www.arbeitnow.com/api/job-board-api?page=2"}}
ARBEITNOW_P2 = {"data": [{"slug": "dev-2", "title": "Dev 2", "company_name": "Delta", "remote": True,
                          "location": "", "url": "https://arbeitnow.com/2"}], "links": {"next": None}}


def test_remotive_parses_and_dedupes_terms():
    session = FakeSession({"https://remotive.com/api": REMOTIVE})
    jobs = get_source("remotive")(session).fetch(["python", "django"])
    assert len(session.calls) == 2 and len(jobs) == 1
    job = jobs[0]
    assert (job.salary_min, job.salary_max, job.salary_currency) == (70000, 90000, "USD")
    assert job.tags == ["python", "aws"]
    assert job.location == "Remote (Europe)" and job.description == "Hi"


def test_remoteok_skips_legal_notice():
    jobs = get_source("remoteok")(FakeSession({"https://remoteok.com/api": REMOTEOK})).fetch([])
    assert len(jobs) == 1
    assert jobs[0].salary_min == 80000 and jobs[0].salary_max is None
    assert jobs[0].location == "Remote"


def test_arbeitnow_follows_pagination():
    session = FakeSession({
        "https://www.arbeitnow.com/api/job-board-api?page=2": ARBEITNOW_P2,
        "https://www.arbeitnow.com/api/job-board-api": ARBEITNOW_P1,
    })
    jobs = get_source("arbeitnow")(session).fetch([])
    assert [j.external_id for j in jobs] == ["dev-1", "dev-2"]
    assert jobs[0].remote is False and jobs[1].remote is True
    assert "full time" in jobs[0].tags


def test_arbeitnow_respects_max_pages():
    session = FakeSession({"https://www.arbeitnow.com/api/job-board-api": ARBEITNOW_P1})
    get_source("arbeitnow")(session, {"max_pages": 1}).fetch([])
    assert len(session.calls) == 1


def test_http_errors_become_source_errors():
    session = FakeSession({"https://remoteok.com/api": FakeResponse({}, status=503)})
    with pytest.raises(SourceError):
        get_source("remoteok")(session).fetch([])


def test_unknown_source():
    with pytest.raises(SourceError, match="Available"):
        get_source("nope")
