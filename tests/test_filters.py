from datetime import datetime, timedelta, timezone

from jobradar.filters import FilterConfig, apply, check, score


def test_keyword_word_boundaries(make_job):
    cfg = FilterConfig(keywords=["java"])
    assert not check(make_job(title="JavaScript Engineer", tags=[], description=""), cfg).passed
    assert check(make_job(title="Java Engineer", tags=[], description=""), cfg).passed


def test_symbols_in_keywords(make_job):
    cfg = FilterConfig(keywords=["c++", "node.js"])
    assert check(make_job(title="C++ Developer", tags=[]), cfg).passed
    assert check(make_job(title="Backend", tags=["node.js"]), cfg).passed


def test_exclusions_and_blocklist(make_job):
    cfg = FilterConfig(exclude_keywords=["senior"], blocked_companies=["BadCo"])
    assert check(make_job(title="Senior Python Dev"), cfg).reason == "excluded keyword 'senior'"
    assert check(make_job(company="badco"), cfg).reason == "blocked company"


def test_location_remote_salary_age(make_job):
    assert not check(make_job(remote=False), FilterConfig(remote_only=True)).passed
    assert not check(make_job(location="Berlin"), FilterConfig(locations=["uk"])).passed
    assert not check(make_job(salary_max=30000), FilterConfig(min_salary=50000)).passed
    # Jobs without salary info are kept rather than silently dropped.
    assert check(make_job(), FilterConfig(min_salary=50000)).passed
    old = make_job(posted_at=datetime.now(timezone.utc) - timedelta(days=30))
    assert check(old, FilterConfig(max_age_days=14)).reason == "too old"


def test_title_match_scores_higher_than_description(make_job):
    cfg = FilterConfig(keywords=["django"])
    in_title, _ = score(make_job(title="Django Developer", tags=[]), cfg)
    in_desc, _ = score(make_job(title="Developer", tags=[], description="Some django work"), cfg)
    assert in_title > in_desc


def test_apply_sorts_and_reports_rejections(make_job):
    cfg = FilterConfig(keywords=["python", "django"], exclude_keywords=["php"])
    jobs = [
        make_job(external_id="1", title="Python Django Engineer"),
        make_job(external_id="2", title="Data Analyst", tags=["python"]),
        make_job(external_id="3", title="PHP Developer", tags=["php"]),
    ]
    kept, rejected = apply(jobs, cfg)
    assert [j.external_id for j in kept] == ["1", "2"]
    assert kept[0].matched_keywords == ["python", "django"]
    assert rejected == {"excluded keyword 'php'": 1}


def test_min_score(make_job):
    cfg = FilterConfig(keywords=["python"], min_score=99)
    kept, rejected = apply([make_job(title="Dev", tags=[], description="python")], cfg)
    assert kept == [] and rejected == {"score below minimum": 1}


def test_from_dict_ignores_unknown_keys():
    cfg = FilterConfig.from_dict({"keywords": ["x"], "unknown": 1})
    assert cfg.keywords == ["x"]
