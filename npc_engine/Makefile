install:
	pip install -r requirements.txt

run:
	uvicorn main:app --reload

test:
	pytest -q

test-cov:
	pytest -q --cov=. --cov-report=term-missing --cov-fail-under=80

lint:
	ruff check .

type:
	mypy .

check: lint type test

seed:
	python data/seed.py
