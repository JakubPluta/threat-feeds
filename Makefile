.PHONY: install test lint snapshot

install:  ## create .venv with the project and dev tools
	uv sync

test:  ## no network; the SQL tests start a local Spark and are skipped without Java
	uv run pytest

lint:
	uv run ruff check .

snapshot:  ## download the four feeds once into snapshots/<snapshot_id>/
	uv run python -m threat_feeds.downloader
