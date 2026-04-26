# Issue 5 - Qualidade, Métricas e Rollout

Status: entregue.

## Resolução

Foram adicionados mecanismos de qualidade operacional para a busca:

- dataset de avaliação;
- benchmark comparativo entre baseline, `rrf` e combinações com expansão;
- métricas por etapa da busca;
- rollout progressivo por percentual;
- target de produção sem `--reload`.

## Evidência no histórico

- Commit: `d8fa771`
- Arquivos principais:
  - `app/src/api/search.py`
  - `app/src/config.py`
  - `app/src/models/search.py`
  - `scripts/012__api-quality-benchmark.sh`
  - `scripts/013__api-rollout-simulation.sh`
  - `scripts/014__api-prod-target-check.sh`
  - `scripts/data/issue5_eval_queries.tsv`

## Decisões consolidadas

- O `meta` passou a carregar tempos de embedding, expansão, retrieval e rerank.
- `SEARCH_RRF_ROLLOUT_PERCENT` e `QUERY_EXPANSION_ROLLOUT_PERCENT` controlam rollout gradual.
- O target `api_prod` foi adicionado para execução quente sem `--reload`.
- O benchmark foi estruturado como contrato repetível via script.
