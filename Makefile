-include .env

SHELL := /bin/bash

############################################################################################
# GLOBALS                                                                                  #
############################################################################################

PYTHON_INTERPRETER = python
PYTHON_VER = 3.13
PYTHON = $(PYTHON_INTERPRETER)$(PYTHON_VER)
COMPOSE = docker compose
MEILI_COMPOSE = $(COMPOSE) --env-file .env -f db/docker-compose.meilisearch.yml

VENV_NAME = .venv
VENV_BIN = $(VENV_NAME)/bin
VENV_PYTHON = $(VENV_BIN)/python
POETRY = $(VENV_PYTHON) -m poetry

############################################################################################
# COMMANDS                                                                                 #
############################################################################################


## setup
.PHONY: project_init
project_init:
	@echo "Creating Python Virtual Environment"
	@$(PYTHON) -m venv $(VENV_NAME)
	@$(VENV_PYTHON) -m ensurepip --upgrade
	@$(VENV_PYTHON) -m pip install --upgrade pip setuptools wheel
	@echo "Installing Poetry"
	@$(VENV_PYTHON) -m pip install poetry
	@echo "Installing dependencies"
	@$(POETRY) install --no-root
	@echo "Virtual Environment Created!"

.PHONY: poetry_reinstall
poetry_reinstall:
	@echo "Installing dependencies"
	@$(POETRY) lock
	@$(POETRY) install --no-root


## lint/format
.PHONY: lint
lint:
	@$(VENV_PYTHON) -m ruff check $(APP_DIR) $(TEST_DIR)
	@$(VENV_PYTHON) -m ruff format --check $(APP_DIR) $(TEST_DIR)

.PHONY: format
format:
	@$(VENV_PYTHON) -m ruff check --fix $(APP_DIR) $(TEST_DIR)
	@$(VENV_PYTHON) -m ruff format $(APP_DIR) $(TEST_DIR)


# Docker Services
.PHONY: meilisearch_up
meilisearch_up:
	@$(MEILI_COMPOSE) up -d --build

.PHONY: meilisearch_down
meilisearch_down:
	@$(MEILI_COMPOSE) down

.PHONY: meilisearch_logs
meilisearch_logs:
	@$(MEILI_COMPOSE) logs -f meilisearch


## etl
.PHONY: etl_scryfall
etl_scryfall:
	@$(VENV_PYTHON) -m etl.run_scryfall_etl \
	--dataset oracle_cards \
	--force \
	--with-rulings \
	--batch-docs 500

.PHONY: etl_meilisearch
etl_meilisearch:
	@$(VENV_PYTHON) -m etl.run_meilisearch_ingest \
	--max-batches 1 \
	--meili-api-key "$(MEILISEARCH_API_KEY)"

.PHONY: etl_meilisearch_max
etl_meilisearch_max:
	@$(VENV_PYTHON) -m etl.run_meilisearch_ingest \
	--meili-api-key "$(MEILISEARCH_API_KEY)" \
	--model-profile bge_small_en_v15 \
	--batch-size 256 \
	--encode-batch-size 256 \
	--cpu-threads 8 \
	--upload-batch-size 2000 \
	--upload-wait-tasks-every 8

.PHONY: etl_semantic_layer
etl_semantic_layer:
	@$(VENV_PYTHON) -m etl.run_semantic_layer_build \
	--meili-api-key "$(MEILISEARCH_API_KEY)"

.PHONY: api_dev
api_dev:
	@$(VENV_PYTHON) -m uvicorn app.src.main:app --host 0.0.0.0 --port 8000 --reload


## cleanup
.PHONY: clean
clean:
	@echo "Cleaning Python cache files..."
	@find . -type f -name "*.py[co]" -delete
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find . -type d -name ".ruff_cache" -exec rm -rf {} +
	@echo "Cleaning test cache files..."
	@find . -type d -name ".pytest_cache" -exec rm -rf {} +
	@echo "Cleaning build and distribution files..."
	@find . -type d -name "*.egg-info" -exec rm -rf {} +
	@find . -type d -name "build" -exec rm -rf {} +
	@find . -type d -name "dist" -exec rm -rf {} +
	@find . -type d -name ".cache" -exec rm -rf {} +
	@echo "Cleaning Jupyter notebook cache..."
	@find . -type d -name ".ipynb_checkpoints" -exec rm -rf {} +
	@echo "Clean complete!"
