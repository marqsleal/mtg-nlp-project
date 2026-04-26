# Issue 6 - Storage e MinIO

Status: entregue.

## Resolução

A persistência dos artefatos ETL foi migrada para `storage/`, com fallback de leitura do legado por 1 ciclo.

- `storage/` passou a ser o root lógico;
- artefatos da semantic layer ficaram versionados em `storage/semantic_layer/<dataset_version>/`;
- foi criada emulação local com MinIO;
- targets `infra.storage.up/down/logs` foram adicionados no `Makefile`.

## Evidência no histórico

- Commit: `2cec4a5`
- Arquivos principais:
  - `etl/paths.py`
  - `etl/scryfall/pipeline.py`
  - `etl/meilisearch/pipeline.py`
  - `etl/storage.py`
  - `db/docker-compose.storage.yml`
  - `scripts/015__storage-paths-check.sh`
  - `scripts/016__minio-health.sh`
  - `scripts/017__storage-compose-check.sh`

## Decisões consolidadas

- Escritas novas não devem voltar para `etl/data/`.
- Leitura compatível do legado é permitida temporariamente.
- O backend de storage tem contrato único com URI local e compatibilidade `s3://`.
- MinIO é a emulação local da persistência em bucket.
