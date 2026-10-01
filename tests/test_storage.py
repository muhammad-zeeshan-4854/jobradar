import pytest


def test_add_new_dedupes_by_uid_and_fingerprint(store, make_job):
    first = store.add_new([make_job(source="a", external_id="1")])
    again = store.add_new([make_job(source="a", external_id="1")])
    cross_posted = store.add_new([make_job(source="b", external_id="77")])
    assert len(first) == 1 and again == [] and cross_posted == []


def test_status_flow_and_query(store, make_job):
    j1, j2 = make_job(external_id="1"), make_job(external_id="2", title="Go Dev", company="Other")
    store.add_new([j1, j2])
    store.set_status(j1.uid, "applied")
    rows, total = store.query(status="applied")
    assert total == 1 and rows[0]["uid"] == j1.uid

    store.set_status(j2.uid, "hidden")
    _, visible = store.query()
    assert visible == 1  # hidden jobs are excluded by default

    with pytest.raises(ValueError):
        store.set_status(j1.uid, "bogus")


def test_search_and_stats(store, make_job):
    store.add_new([make_job(external_id="1", tags=["python"]),
                   make_job(external_id="2", title="Rust Dev", company="Z", tags=["rust"])])
    rows, total = store.query(search="rust")
    assert total == 1 and rows[0]["tags"] == ["rust"]
    stats = store.stats()
    assert stats["total"] == 2 and stats["by_status"]["new"] == 2
    assert stats["new_this_week"] == 2


def test_runs_are_recorded(store):
    run = store.start_run()
    store.finish_run(run, fetched=5, matched=3, new_jobs=2, notified=2, errors=["x"])
    last = store.recent_runs(1)[0]
    assert last["fetched"] == 5 and last["errors"] == ["x"]
