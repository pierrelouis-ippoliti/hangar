.PHONY: setup check qdrant-up qdrant-down reproduce clean-data

QDRANT_READY_URL := http://127.0.0.1:6333/readyz

# Install every dependency group from the lock file, then the git hooks.
setup:
	uv sync --locked --all-groups
	uv run --locked pre-commit install

# Lint, format check, types, import rules and tests. CI runs this target.
check:
	uv run --locked ruff check
	uv run --locked ruff format --check
	uv run --locked mypy
	uv run --locked lint-imports
	uv run --locked pytest --cov=hangar --cov-report=term-missing

# Start Qdrant and wait up to 30 seconds until it is ready.
qdrant-up:
	docker compose up -d qdrant
	@for i in $$(seq 30); do \
		curl -sf $(QDRANT_READY_URL) > /dev/null && echo "Qdrant is ready." && exit 0; \
		sleep 1; \
	done; \
	echo "Qdrant did not become ready in 30 seconds." >&2; exit 1

qdrant-down:
	docker compose down

# Rebuild everything from a clean clone.
reproduce: setup qdrant-up
	uv run --locked dvc repro

# Delete downloaded documents, pipeline outputs and the Qdrant volume.
clean-data:
	@printf "Delete data/ and the Qdrant volume? [y/N] "; \
	read -r answer; \
	if [ "$$answer" = "y" ] || [ "$$answer" = "Y" ]; then \
		rm -rf data; \
		docker compose down -v; \
		echo "Deleted data/ and the Qdrant volume."; \
	else \
		echo "Nothing deleted."; \
	fi
