# Issue 1 - Contratos Base

Status: entregue.

## Resolução

Esta issue fechou os contratos fundacionais que sustentam a evolução da busca:

- índice `mtg_domain_semantic_layer`;
- contrato de configuração da expansão de query;
- contrato de fusão RRF;
- contrato de `meta` da resposta do `POST /v1/search`;
- política oficial de paths em `storage/`.

## Evidência no histórico

- Commit: `4bc2185`
- Arquivos principais:
  - `.env.example`
  - `app/src/api/search.py`
  - `app/src/config.py`
  - `app/src/models/search.py`
  - `db/meilisearch/domain_semantic_layer_document_schema.json`
  - `db/meilisearch/domain_semantic_layer_settings.json`
  - `docs/contracts/issue-1-contracts.md`

## Decisões consolidadas

- O índice semântico tem primary key `id` e schema dedicado.
- A expansão de query é controlada por variáveis `QUERY_*`.
- A fusão RRF é configurada por `SEARCH_FUSION_MODE`, `SEARCH_RRF_K` e `SEARCH_RRF_WINDOW`.
- O `meta` da busca expõe os parâmetros de fusão e expansão.
- O storage lógico passou a ser `storage/`, com mapeamento legado documentado.
