# ETL Pipelines

Este diretório contém duas pipelines separadas:

- `scryfall`: extrai dados brutos, transforma para formato normalizado e gera batches.
- `meilisearch`: consome batches prontos, vetoriza com BGE-M3 e envia ao Meilisearch.

## Fluxo Geral

1. Rodar pipeline Scryfall.
2. Scryfall salva snapshots (`cards` e `rullings`) e gera batches de cards.
3. Rodar pipeline Meilisearch para vetorizar e carregar batches.

## Estrutura de Dados

- `etl/data/scryfall/raw`: arquivos bulk baixados da API.
- `etl/data/scryfall/processed`: snapshots normalizados (`jsonl`/`parquet`).
- `etl/data/scryfall/state`: estado de idempotência do ETL.
- `etl/data/meilisearch/batches/input/cards`: batches gerados pelo Scryfall.
- `etl/data/meilisearch/batches/vectorized/cards`: batches vetorizados.
- `etl/data/meilisearch/state/ingest_cards_state.json`: checkpoint da ingestão.
- `etl/data/meilisearch/processed`: alias de vetorizações mais recentes.

## Pipeline Scryfall

Script: `etl/run_scryfall_etl.py`

Passos:

1. Busca metadados de bulk (`/bulk-data`).
2. Faz download do dataset (`unique_artwork` por padrão).
3. Transforma para schema normalizado.
4. Salva `cards` e opcionalmente `rullings`.
5. Gera batches de cards para ingestão no Meilisearch.

Comando recomendado:

```bash
python etl/run_scryfall_etl.py --dataset unique_artwork --with-rulings --batch-docs 500
```

## Pipeline Meilisearch

Script: `etl/run_meilisearch_ingest.py`

Passos:

1. Lê batches prontos de `etl/data/meilisearch/batches/input/cards/`.
2. Vetoriza lote a lote com `BAAI/bge-m3`.
3. Salva batch vetorizado em `.../batches/vectorized/cards/`.
4. Envia o batch ao índice no Meilisearch.
5. Atualiza estado por batch (`pending`, `vectorized`, `uploaded`, `failed`).

Comando recomendado:

```bash
python etl/run_meilisearch_ingest.py --meili-api-key change_this_master_key --max-batches 1
```

## Execução via Make

- `make scryfall_etl`
- `make meilisearch_etl`
