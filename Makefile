BASE_URL ?= http://localhost:8000
API_KEY  ?= $(shell grep -m1 API_KEY_SECRET npc_engine/.env 2>/dev/null | cut -d= -f2)

.PHONY: eval scenarios test

eval:
	@echo "Running eval cases against $(BASE_URL) ..."
	cd npc_engine && python ../evals/runner.py \
		--base-url $(BASE_URL) \
		--api-key "$(API_KEY)" \
		--cases ../evals/cases \
		--reports ../evals/reports

scenarios:
	pytest tests/scenarios/ -v --scenarios-only -p no:cacheprovider

test:
	cd npc_engine && python -m pytest tests/unit/ -v
