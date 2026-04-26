# ETL Pipelines

Este diretório contém duas pipelines separadas:

- `scryfall`: extrai dados brutos, transforma para formato normalizado e gera batches.
- `meilisearch`: consome batches prontos, vetoriza com sentence-transformers e envia ao Meilisearch.

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
2. Faz download do dataset (`oracle_cards` por padrão).
3. Transforma para schema normalizado.
4. Salva `cards` e opcionalmente `rullings`.
5. Gera batches de cards para ingestão no Meilisearch.

Comando recomendado:

```bash
python etl/run_scryfall_etl.py --dataset oracle_cards --with-rulings --batch-docs 500
```

## Pipeline Meilisearch

Script: `etl/run_meilisearch_ingest.py`

Passos:

1. Lê batches prontos de `etl/data/meilisearch/batches/input/cards/`.
2. Vetoriza lote a lote com o modelo configurado (`bge_small_en_v15` por padrão).
3. Salva batch vetorizado em `.../batches/vectorized/cards/`.
4. Envia o batch ao índice no Meilisearch.
5. Atualiza estado por batch (`pending`, `vectorized`, `uploaded`, `failed`).

Comando recomendado:

```bash
python etl/run_meilisearch_ingest.py --meili-api-key change_this_master_key --max-batches 1
```

Perfis de embedding disponíveis via `--model-profile`:

- `bge_small_en_v15` (default): `BAAI/bge-small-en-v1.5` (384 dims), muito leve para CPU e uso majoritariamente em inglês.
- `bge_m3`: `BAAI/bge-m3` (1024 dims), melhor baseline de qualidade, mais pesado.
- `multilingual_e5_small`: `intfloat/multilingual-e5-small` (384 dims), alternativa multilíngue leve.
- `paraphrase_multilingual_minilm_l12_v2`: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dims), opção rápida com qualidade geralmente menor.

Exemplo com modelo leve multilíngue:

```bash
python etl/run_meilisearch_ingest.py \
  --model-profile multilingual_e5_small \
  --meili-api-key change_this_master_key \
  --max-batches 1
```

Notas de operação:

- O pipeline atualiza automaticamente `embedders` no índice do Meilisearch com `source=userProvided` e a dimensão correta do modelo.
- Para usar outro modelo, selecione apenas `--model-profile` dentre os perfis configurados em `etl/meilisearch/embedding_profiles.py`.
- Ajustes de performance no CLI:
  - `--encode-batch-size` controla o batch interno do `SentenceTransformer` (default `256`).
  - `--cpu-threads` define threads de CPU para inferência (default: número de CPUs).
  - `--upload-wait-tasks-every` reduz bloqueio de upload aguardando tarefas em janelas (default `8`).

## Execução via Make

- `make scryfall_etl`
- `make meilisearch_etl`
