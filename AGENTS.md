# Repository Guidelines

## Project Structure & Module Organization
This repository is organized by ETL and infrastructure responsibilities:
- `etl/`: pipeline code (`scryfall/`, `meilisearch/`), CLIs (`run_scryfall_etl.py`, `run_meilisearch_ingest.py`), and path/logging utilities.
- `etl/data/`: local artifacts (`scryfall/raw`, `scryfall/processed`, `scryfall/state`, `meilisearch/batches`, `meilisearch/state`).
- `db/`: Meilisearch Docker stack and index settings.
- Root config: `pyproject.toml`, `Makefile`, `.env`, `.env.example`.

Prefer small modules with explicit boundaries: extract/transform/load logic should stay separated.

## Build, Test, and Development Commands
Run commands from the repository root.
- `make project_init`: create `.venv`, install Poetry, and install dependencies.
- `make meilisearch_up`: start Meilisearch (`db/docker-compose.meilisearch.yml`).
- `make scryfall_etl`: download/normalize Scryfall data and generate card batches.
- `make meilisearch_etl`: vectorize batches and upload to Meilisearch.
- `.venv/bin/python -m etl.run_scryfall_etl --help`: list Scryfall CLI options.
- `.venv/bin/python -m etl.run_meilisearch_ingest --help`: list ingest CLI options.

## Coding Style & Naming Conventions
- Python target is 3.13; use type hints for new/changed functions.
- Formatting/linting is enforced with Ruff (`line-length = 100`, rules `E,F,I,UP,B`).
- Use 4-space indentation.
- Naming: `snake_case` for modules/functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants.
- ETL output naming is standardized: `scryfall_cards_*` and `scryfall_rullings_*` (`*_latest` or `*_<YYYY-MM-DD>`).

## ETL Rules & Techniques
- Use centralized path resolution only via `etl/paths.py` (`EtlPaths.for_today`), not hardcoded paths.
- Keep pipelines idempotent by checking state files before reprocessing unchanged datasets.
- Scryfall pipeline is responsible for splitting cards into `batch_XXXXXX.jsonl`; ingest pipeline consumes existing batches.
- Ingest progress must be checkpointed in `etl/data/meilisearch/state/ingest_cards_state.json` with per-batch status (`pending`, `vectorized`, `uploaded`, `failed`).
- Use atomic JSON state writes (`*.tmp` then replace) to avoid partial state corruption.
- Logging must use `etl/logging_utils.py` formatter: `{timestamp} | {logger:<50} | {level:<10} | {message}` with ENTER/EXIT step logs and DEBUG context.

## Commit & Pull Request Guidelines
There is no established commit history yet. Use Conventional Commit-style messages:
- `feat: add card lookup client`
- `fix: handle scryfall non-200 responses`

For PRs, include:
- What changed and why.
- How it was tested (commands run).
- Linked issue/task.
- Sample request/response or screenshots when behavior/UI changes.

## Security & Configuration Tips
- Never commit secrets; keep them in `.env`.
- Update `.env.example` when adding new environment variables.
- Prefer locked dependency updates through Poetry to keep environments reproducible.
