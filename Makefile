.PHONY: setup hooks check test db-up db-down db-reset db-test

setup:
	cd bot && uv sync

hooks:
	pre-commit install

db-up:
	supabase start

db-down:
	supabase stop

db-reset:
	supabase db reset

db-test:
	supabase test db

test:
	cd bot && uv run pytest tests/unit -q

check:
	cd bot && uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run lint-imports && uv run pytest tests/unit -q
	supabase test db
