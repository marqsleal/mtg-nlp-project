# Issue 4 - Integração da Camada Semântica

Status: entregue.

## Resolução

A query original passou a ser enriquecida com expansões extraídas do índice semântico antes do retrieval.

- lookup da semântica por termo;
- cache TTL;
- fallback para a query original quando a expansão falha;
- metadados de expansão na resposta;
- reranker com warmup opcional no startup.

## Evidência no histórico

- Commit: `e06eb7c`
- Arquivos principais:
  - `app/src/services/domain_semantic_layer_service.py`
  - `app/src/api/search.py`
  - `app/src/main.py`
  - `app/src/config.py`
  - `app/src/services/reranker_service.py`
  - `scripts/010__api-search-expansion-off.sh`
  - `scripts/011__api-search-expansion-on.sh`

## Decisões consolidadas

- A expansão é controlada por config e por request.
- O `meta` retorna `query_expansion_applied`, `expanded_terms` e `expanded_query`.
- A expansão acontece antes do embedding e do retrieval.
- O reranker ficou com default operacional desligado e warmup opcional.
