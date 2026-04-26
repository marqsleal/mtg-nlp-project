# MTG NLP Project
Projeto de ciência de dados e utilizando base de conhecimento de Magic: The Gathering para aplicar busca semântica em texto de cartas.


## ETL
Pipeline de dados para cartas de Magic: The Gathering usando Scryfall como origem, vetorização com `BAAI/bge-m3` e carga em Meilisearch.

O ETL é dividido em duas etapas independentes:

1. `scryfall_etl`: baixa o bulk da Scryfall, normaliza para schema interno e gera batches de cards.
2. `meilisearch_etl`: consome os batches prontos, vetoriza e envia para o índice do Meilisearch.

## Estrutura de Pastas

- `etl/scryfall/`: extração + transformação.
- `etl/meilisearch/`: vetorização + ingestão no índice.
- `etl/data/scryfall/{raw,processed,state}`: snapshots brutos/processados e estado.
- `etl/data/meilisearch/batches/{input,vectorized}/cards`: batches de entrada e vetorizados.
- `etl/data/meilisearch/state/ingest_cards_state.json`: checkpoint por batch.
- `db/`: docker-compose e configurações do Meilisearch.

## Como Rodar

Pré-requisitos:
- Python 3.13
- Docker
- `.env` com `MEILISEARCH_API_KEY`

Comandos principais:

```bash
make project_init
make meilisearch_up
make scryfall_etl
make meilisearch_etl
```

## API de Busca Semântica

Subir API local:

```bash
make api_dev
```

Endpoint:

- `POST /v1/search`

Payload mínimo:

```json
{
  "query": "counter target spell"
}
```

Payload com hiperparâmetros (opcionais):

```json
{
  "query": "draw cards",
  "limit": 5,
  "offset": 0,
  "filter": ["lang = en", "rarity = uncommon"],
  "semantic_ratio": 1.0,
  "show_ranking_score": true,
  "min_ranking_score": 0.2
}
```

Execução direta via módulo:

```bash
.venv/bin/python -m etl.run_scryfall_etl --dataset unique_artwork --with-rulings --batch-docs 500
.venv/bin/python -m etl.run_meilisearch_ingest --meili-api-key "$MEILISEARCH_API_KEY" --max-batches 1
```
