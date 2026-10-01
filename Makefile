.PHONY: install test lint run serve demo

install:
	pip install -e ".[dev]"

test:
	pytest --cov=jobradar --cov-report=term-missing

lint:
	ruff check .

run:
	jobradar run

serve:
	jobradar serve

demo:
	jobradar demo && jobradar serve
