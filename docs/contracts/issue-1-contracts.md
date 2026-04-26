# Issue 1 Contracts (Semantic Layer, RRF, Response Meta, Storage)

## 1) Semantic Layer Index Contract
- Index UID: `mtg_domain_semantic_layer`
- Primary key: `id`
- Schema source:
  - `db/meilisearch/domain_semantic_layer_document_schema.json`
  - `db/meilisearch/domain_semantic_layer_settings.json`

## 2) Query Expansion Config Contract (`.env`)
- `QUERY_SEMANTIC_LAYER_INDEX_UID`
- `QUERY_EXPANSION_ENABLED`
- `QUERY_EXPANSION_MAX_TERMS`
- `QUERY_EXPANSION_MIN_SCORE`
- `QUERY_EXPANSION_CACHE_TTL_SECONDS`

## 3) Retrieval Fusion (RRF) Config Contract (`.env`)
- `SEARCH_FUSION_MODE` (`hybrid` | `rrf`)
- `SEARCH_RRF_K` (integer > 0)
- `SEARCH_RRF_WINDOW` (integer > 0)

## 4) API Contract (`POST /v1/search`)
### Request additions
- `query_expansion` (bool | null)
- `expansion_max_terms` (int | null)
- `expansion_min_score` (float | null)
- `fusion_mode` (`hybrid` | `rrf` | null)
- `rrf_k` (int | null)
- `rrf_window` (int | null)

### Response `meta` additions
- `fusion_mode` (`hybrid` | `rrf`)
- `rrf_k` (int | null)
- `rrf_window` (int | null)
- `query_expansion_applied` (bool)
- `expanded_terms` (string[])
- `expanded_query` (string | null)

## 5) Storage Path Contract
- Logical root: `storage/`
- Backend-agnostic addressing:
  - local: `file://storage/...`
  - remote: `s3://<bucket>/<prefix>/...`

### Canonical path mapping
- `etl/data/scryfall/raw` -> `storage/scryfall/raw`
- `etl/data/scryfall/processed` -> `storage/scryfall/processed`
- `etl/data/scryfall/state` -> `storage/scryfall/state`
- `etl/data/meilisearch/batches` -> `storage/meilisearch/batches`
- `etl/data/meilisearch/state` -> `storage/meilisearch/state`

### Legacy compatibility rule
- Compatibility window: `1` ciclo de execução.
- During compatibility window:
  - read: allow fallback from legacy path (`etl/data/...`) when `storage/...` is missing
  - write: always write to `storage/...`
