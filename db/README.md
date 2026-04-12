# Meilisearch (DB)

Este diretório contém a configuração do serviço Meilisearch e o schema de índice usado pela ingestão.

## Arquivos

- `docker-compose.meilisearch.yml`: serviço local do Meilisearch.
- `meilisearch/index_settings.json`: settings do índice (`searchable`, `filterable`, `embedders`).
- `meilisearch/document_schema.json`: contrato esperado para documentos indexados.

## Subir e parar serviço

```bash
make meilisearch_up
make meilisearch_logs
make meilisearch_down
```

O volume persistente local é `db/data/` (ignorado no git).

## Autenticação

Use header:

```http
Authorization: Bearer <MEILISEARCH_API_KEY>
```

## Requests principais

1. Verificar saúde:
```bash
curl -H "Authorization: Bearer $MEILISEARCH_API_KEY" http://127.0.0.1:7700/health
```

2. Habilitar vector store experimental:
```bash
curl -X PATCH -H "Authorization: Bearer $MEILISEARCH_API_KEY" -H "Content-Type: application/json" \
  http://127.0.0.1:7700/experimental-features/ \
  -d '{"vectorStore": true}'
```

3. Criar índice:
```bash
curl -X POST -H "Authorization: Bearer $MEILISEARCH_API_KEY" -H "Content-Type: application/json" \
  http://127.0.0.1:7700/indexes \
  -d '{"uid":"mtg_cards","primaryKey":"id"}'
```

4. Aplicar settings:
```bash
curl -X PATCH -H "Authorization: Bearer $MEILISEARCH_API_KEY" -H "Content-Type: application/json" \
  http://127.0.0.1:7700/indexes/mtg_cards/settings \
  --data-binary @db/meilisearch/index_settings.json
```

5. Acompanhar tasks:
```bash
curl -H "Authorization: Bearer $MEILISEARCH_API_KEY" http://127.0.0.1:7700/tasks?limit=20
```

## Estado das requests (tasks)

Operações assíncronas retornam `taskUid`. O estado fica em `/tasks/{taskUid}`:

- `enqueued`: task na fila
- `processing`: task em execução
- `succeeded`: concluída com sucesso
- `failed`: concluída com erro
- `canceled`: cancelada

Campos úteis:

- `type` (`indexCreation`, `settingsUpdate`, `documentAdditionOrUpdate`)
- `details`
- `error`
- `enqueuedAt`, `startedAt`, `finishedAt`
