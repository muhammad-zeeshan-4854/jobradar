def test_fingerprint_ignores_case_punctuation_and_suffix(make_job):
    a = make_job(source="a", external_id="1", title="Python Developer!", company="Acme Inc.")
    b = make_job(source="b", external_id="99", title="python developer", company="ACME")
    assert a.uid != b.uid
    assert a.fingerprint == b.fingerprint


def test_salary_display(make_job):
    assert make_job(salary_min=50000, salary_max=70000).salary_display == "$50k–$70k"
    assert make_job(salary_min=50000, salary_currency="EUR").salary_display == "€50k"
    assert make_job().salary_display == ""


def test_to_dict_is_serialisable(make_job):
    import json

    data = make_job().to_dict()
    assert json.loads(json.dumps(data))["uid"] == data["uid"]
