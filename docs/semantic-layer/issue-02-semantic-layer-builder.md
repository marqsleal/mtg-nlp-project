# Issue 2 - Builder da Camada Semântica

Status: entregue.

## Resolução

Foi criado um job dedicado para construir a camada semântica a partir dos documentos indexados em `mtg_cards`.

- leitura da fonte no Meilisearch;
- tokenização e normalização;
- cálculo de TF/DF/IDF;
- geração de expansões com PMI/NPMI;
- persistência no índice `mtg_domain_semantic_layer`;
- artefatos versionados em `storage/semantic_layer/<dataset_version>/`.

## Evidência no histórico

- Commit: `72ff443`
- Arquivos principais:
  - `etl/meilisearch/semantic_layer.py`
  - `etl/run_semantic_layer_build.py`
  - `Makefile`
  - `scripts/005__meilisearch-semantic-layer-stats.sh`
  - `scripts/006__meilisearch-semantic-layer-search.sh`
  - `scripts/007__meilisearch-semantic-layer-document.sh`

## Decisões consolidadas

- A camada semântica é reconstruída como etapa própria, pós-ETL.
- O documento do índice usa `term` como unidade semântica e `expansions` como lista ordenada.
- Os artefatos de saída ficam versionados por `dataset_version`.
- O builder é validado por scripts de leitura e busca no Meilisearch.
