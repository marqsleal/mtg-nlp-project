# Issue 3 - RRF Fusion

Status: entregue.

## Resolução

A busca passou a suportar fusão `RRF` entre duas listas independentes:

- FTS;
- Vector.

A fusão foi implementada com deduplicação por `id` e exposição de metadados de ranking.

## Evidência no histórico

- Commit: `d1ac7a7`
- Arquivos principais:
  - `app/src/api/search.py`
  - `app/src/services/meilisearch_service.py`
  - `app/src/services/rrf_fusion_service.py`
  - `scripts/008__api-search-hybrid.sh`
  - `scripts/009__api-search-rrf.sh`

## Decisões consolidadas

- `fusion_mode` seleciona `hybrid` ou `rrf`.
- O resultado final do `rrf` carrega `_rrfScore`, `_rrfFtsRank` e `_rrfVectorRank`.
- A paginação é aplicada após a fusão.
- A busca híbrida antiga foi preservada como caminho compatível.
