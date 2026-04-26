# TODO - Controle de Issues (Semantic Layer, RRF Fusion, Storage e Organização do Código)

## Objetivo
Organizar o trabalho como controle de issues, com implementação faseada, dependências explícitas, critérios de aceite e checklist por issue.

## Escopo geral
- Camada Semântica pós-ETL para expansão de query.
- Retrieval com RRF Fusion (FTS + Vector) no backend.
- Integração da expansão no backend de busca.
- Migração de artefatos ETL para domínio `storage/` com versionamento.
- Emulação local de bucket com MinIO (paridade com produção).
- Unificação de componentes compartilhados ETL/API.
- Padronização arquitetural de código (estilo repomix).

## Não escopo (nesta fase)
- UI de administração da camada semântica.
- Curadoria manual por painel.
- Treino de modelo próprio de reranker/expansão.

---

## Prioridade e Dependências entre Issues
1. **Issue 1 - Contratos base (semantic layer + RRF + configuração + storage)**
2. **Issue 2 - Builder da Camada Semântica (pós-ETL)**
Dependência: Issue 1
3. **Issue 3 - Retrieval com RRF Fusion (FTS + Vector)**
Dependência: Issue 1
4. **Issue 4 - Integração da Camada Semântica no Backend (`/v1/search`)**
Dependência: Issues 2 e 3
5. **Issue 5 - Qualidade, métricas e rollout seguro**
Dependência: Issues 3 e 4
6. **Issue 6 - Migração para domínio `storage/` + MinIO/S3**
Dependência: Issues 1 e 2
7. **Issue 7 - Unificação ETL/API em pacote compartilhado**
Dependência: Issues 4 e 6
8. **Issue 8 - Padronização de arquitetura/estilo (repomix)**
Dependência: Issue 7

---

## Issue 1 - Contratos base (semantic layer + RRF + configuração + storage)

### O que já temos
- Pipeline ETL funcional (Scryfall -> batches -> ingest).
- Endpoint de busca `/v1/search` ativo.
- Retrieval atual com uma chamada híbrida (`q + vector + semanticRatio`) e rerank opcional.
- Logging estruturado com padrão ENTER/EXIT.

### O que falta
- Contrato fechado do índice `mtg_domain_semantic_layer`.
- Contrato de configuração da expansão de query.
- Contrato de RRF Fusion (parâmetros, metadados e comportamento).
- Contrato de paths de artefatos no domínio `storage/`.

### Fases de implementação
1. **Fase 1.1 - Contrato do índice de camada semântica**
Definir documento, campos, tipos, ordenação de `expansions` e `dataset_version`.
2. **Fase 1.2 - Contrato de configuração da expansão**
Adicionar variáveis em `.env.example` para feature flag e hiperparâmetros de expansão.
3. **Fase 1.3 - Contrato de configuração do RRF**
Definir `SEARCH_FUSION_MODE`, `SEARCH_RRF_K`, `SEARCH_RRF_WINDOW` e parâmetros por request.
4. **Fase 1.4 - Contrato de metadados de resposta**
Definir `fusion_mode`, `rrf_k`, `rrf_window`, `query_expansion_applied`, `expanded_terms`.
5. **Fase 1.5 - Contrato de storage**
Definir `storage/` como raiz lógica e padrão agnóstico de backend (`file://` e `s3://`).

### Critérios de aceite
- Contratos de semantic layer, RRF e metadados documentados e sem ambiguidades.
- Configs mínimas definidas e versionadas em `.env.example`.
- Mapeamento de paths legado -> novo definido formalmente.

### Checklist da issue
- [x] Definir schema do índice `mtg_domain_semantic_layer`.
- [x] Definir variáveis `QUERY_*` de expansão no `.env.example`.
- [x] Definir variáveis `SEARCH_FUSION_*` e `SEARCH_RRF_*` no `.env.example`.
- [x] Definir contrato de metadados de resposta para fusão e expansão.
- [x] Definir política oficial de paths em `storage/`.
- [x] Definir regra de compatibilidade de 1 ciclo para paths legados.

---

## Issue 2 - Builder da Camada Semântica (pós-ETL)

### O que já temos
- `mtg_cards` indexado no Meilisearch.
- Pipeline de ETL e geração de batches já operacional.

### O que falta
- Job dedicado para construir expansões semânticas.
- Persistência em índice dedicado e artefatos versionados do builder.

### Fases de implementação
1. **Fase 2.1 - Estrutura de código**
Criar `etl/meilisearch/semantic_layer.py` e `etl/run_semantic_layer_build.py`.
2. **Fase 2.2 - Pipeline do builder**
Tokenização/normalização, TF/DF/IDF, geração de candidatos (PMI + opcional semântico), score final, top-N.
3. **Fase 2.3 - Persistência no Meilisearch**
Criar/atualizar índice `mtg_domain_semantic_layer`, upsert por lotes e idempotência por `dataset_version`.
4. **Fase 2.4 - Artefatos do builder**
Persistir saída em `storage/semantic_layer/<dataset_version>/`.
5. **Fase 2.5 - Operação**
Adicionar target de execução no `Makefile`.

### Critérios de aceite
- Índice criado e populado com documentos por termo e expansões ordenadas.
- Execução local completa sem erro.
- Artefatos do builder versionados em `storage/semantic_layer/<dataset_version>/`.

### Checklist da issue
- [x] Criar módulo ETL do builder.
- [x] Criar CLI `run_semantic_layer_build.py`.
- [x] Criar/validar settings do índice `mtg_domain_semantic_layer`.
- [x] Adicionar alvo de execução no `Makefile`.
- [x] Persistir artefatos versionados da camada semântica.

---

## Issue 3 - Retrieval com RRF Fusion (FTS + Vector)

### O que já temos
- Endpoint `/v1/search` com retrieval híbrido por `semanticRatio`.
- Serviço Meilisearch e serviços de embedding/reranker existentes.

### O que falta
- Busca em duas listas independentes (FTS e Vector).
- Serviço de fusão RRF com parâmetros configuráveis.
- Modo de execução selecionável (`hybrid` atual vs `rrf`).

### Fases de implementação
1. **Fase 3.1 - Cliente de busca dual**
Adicionar no serviço de busca chamadas separadas para FTS e Vector.
2. **Fase 3.2 - Serviço de fusão RRF**
Implementar fusão por rank (`1 / (k + rank)`), janela (`window`) e deduplicação por `id`.
3. **Fase 3.3 - Integração no endpoint**
Selecionar estratégia por configuração/request (`hybrid` ou `rrf`).
4. **Fase 3.4 - Metadados de fusão**
Retornar no `meta` os parâmetros de fusão e indicadores de execução.

### Critérios de aceite
- Modo `rrf` funcional sem quebrar modo `hybrid` existente.
- Resultado final ordenado por score de fusão com deduplicação correta.
- Metadados de fusão presentes no contrato de resposta.

### Checklist da issue
- [x] Implementar busca FTS dedicada no serviço Meilisearch.
- [x] Implementar busca Vector dedicada no serviço Meilisearch.
- [x] Implementar `RrfFusionService`/função de fusão.
- [x] Integrar seleção de modo de retrieval (`hybrid` | `rrf`) no endpoint.
- [x] Adicionar metadados de fusão (`fusion_mode`, `rrf_k`, `rrf_window`).
- [ ] Adicionar testes unitários da lógica de fusão (ranking e dedup). (postergado)

---

## Issue 4 - Integração da Camada Semântica no Backend (`/v1/search`)

### O que já temos
- Endpoint `/v1/search` com retrieval e reranking.
- Base para integração de modos de retrieval (issue de RRF).

### O que falta
- Serviço de expansão por camada semântica.
- Parâmetros de expansão por request.
- Encadeamento formal: query original -> expansão -> retrieval (hybrid/rrf) -> rerank.

### Fases de implementação
1. **Fase 4.1 - Serviço de expansão**
Criar `DomainSemanticLayerService` com normalização, lookup, agregação, limites e cache TTL.
2. **Fase 4.2 - Enriquecimento de query**
Aplicar expansão quando habilitada por config/request e respeitar limiares de score.
3. **Fase 4.3 - Integração com retrieval**
Executar expansão antes do modo de retrieval selecionado (`hybrid` ou `rrf`).
4. **Fase 4.4 - Metadados e fallback**
Adicionar metadados de expansão no `meta` e fallback para query original em falha.
5. **Fase 4.5 - Warmup e latência inicial**
Lazy load de reranker, default operacional de rerank e warmup explícito.

### Critérios de aceite
- Busca funciona com expansão ligada/desligada sem regressão funcional.
- Expansão funciona em ambos os modos de retrieval (`hybrid` e `rrf`).
- Fallback para query original em falha da camada semântica.
- Metadados de expansão disponíveis conforme contrato.

### Checklist da issue
- [x] Implementar `DomainSemanticLayerService`.
- [x] Integrar expansão no endpoint `/v1/search`.
- [x] Aplicar expansão antes do retrieval (`hybrid`/`rrf`).
- [x] Adicionar cache TTL de expansões.
- [x] Adicionar metadados de expansão no `meta` da resposta.
- [x] Implementar fallback para query original quando semantic layer falhar.
- [x] Implementar lazy load do reranker (`rerank=true`).
- [x] Manter `rerank=false` como default operacional.
- [x] Implementar warmup explícito no startup.

---

## Issue 5 - Qualidade, métricas e rollout seguro

### O que já temos
- Logs estruturados básicos no ETL/API.
- Mecanismo de feature flag previsto para expansão e retrieval.

### O que falta
- Dataset de avaliação de relevância.
- Métricas comparativas entre estratégias de retrieval.
- Plano de rollout com gates objetivos para `rrf` e expansão.

### Fases de implementação
1. **Fase 5.1 - Dataset de avaliação**
Criar conjunto de queries MTG com relevância esperada.
2. **Fase 5.2 - Benchmark comparativo**
Comparar: baseline atual, `rrf`, `expansão+hybrid`, `expansão+rrf`.
3. **Fase 5.3 - Observabilidade da busca**
Adicionar logs de lookup, expansões aplicadas, cache hit/miss, latência por etapa e modo de retrieval.
4. **Fase 5.4 - Rollout progressivo**
Ativar por ambiente/percentual com fallback garantido.

### Critérios de aceite
- Ganho de relevância sem degradação de latência acima do limite acordado.
- Rollout com rollback/fallback documentado e testado.
- Métricas comparativas publicadas por modo de retrieval.

### Checklist da issue
- [x] Criar dataset de avaliação.
- [x] Rodar benchmark baseline vs `rrf` vs combinações com expansão.
- [x] Adicionar logs estruturados do serviço de expansão e da fusão.
- [x] Definir e executar estratégia de rollout progressivo.
- [x] Garantir execução em produção sem `--reload` e com processo quente.

---

## Issue 6 - Migração para domínio `storage/` + MinIO/S3

### O que já temos
- Artefatos em `etl/data/*` com estado de ingest existente.
- Regras de idempotência e escrita atômica já usadas no ETL.

### O que falta
- Migração de persistência para `storage/`.
- Contrato único de storage (`file` e `s3` compatível).
- Emulação local com MinIO no mesmo padrão operacional do Meilisearch.

### Fases de implementação
1. **Fase 6.1 - Migração de paths e compatibilidade**
Migrar leitura/escrita para `storage/...` via `etl/paths.py`, manter fallback legado por 1 ciclo.
2. **Fase 6.2 - Versionamento de artefatos**
Garantir versionamento por `dataset_version`, incluindo camada semântica.
3. **Fase 6.3 - Backend de storage**
Definir abstração única para backend `file` e `s3`.
4. **Fase 6.4 - Emulação local (MinIO)**
Adicionar stack local e targets `infra.storage.up/down/logs`.
5. **Fase 6.5 - Configuração e operação**
Adicionar variáveis `STORAGE_*` no `.env.example` e validar operação local/prod.

### Critérios de aceite
- Sem novas gravações em `etl/data/`.
- Paths legados removidos após janela de compatibilidade.
- Camada semântica versionada em `storage/semantic_layer/<dataset_version>/`.
- Fluxo local com MinIO funcional via `infra.storage.*`.

### Checklist da issue
- [ ] Migrar persistência de `etl/data/` para `storage/`.
- [ ] Migrar todos os paths de leitura/escrita para `storage/...` via `etl/paths.py`.
- [ ] Manter fallback de leitura legado por 1 ciclo.
- [ ] Remover paths legados após o ciclo de compatibilidade.
- [ ] Versionar artefatos da camada semântica em `storage/semantic_layer/<dataset_version>/`.
- [ ] Definir backend de storage (`file` e `s3` compatível) com contrato único.
- [ ] Adicionar stack local de MinIO.
- [ ] Adicionar targets `infra.storage.up/down/logs` no `Makefile`.
- [ ] Adicionar variáveis `STORAGE_*` no `.env.example`.

---

## Issue 7 - Unificação ETL/API em pacote compartilhado

### O que já temos
- Mapeamento de duplicação API x ETL identificado.
- Padrões de config/logging/cliente parcialmente similares.

### O que falta
- Pacote compartilhado para reduzir duplicação e imports cruzados.
- Reuso de lógica de retrieval/fusão/contratos no domínio compartilhado.

### Fases de implementação
1. **Fase 7.1 - Pacote compartilhado**
Criar `shared/mtg_shared` com módulos de `config`, `logging`, `meilisearch`, `embeddings`, `text`, `contracts` e `search/fusion`.
2. **Fase 7.2 - Migração API**
Migrar API para `mtg_shared` (config, logging, normalize, clientes e fusão).
3. **Fase 7.3 - Migração ETL**
Migrar ETL para `mtg_shared` mantendo compatibilidade operacional.
4. **Fase 7.4 - DX e Makefile**
Reestruturar targets por domínio e adicionar validações/config-check/warmup.

### Critérios de aceite
- Sem import cruzado `app -> etl` ou `etl -> app`.
- Cliente Meilisearch, perfis de embedding e fusão de retrieval unificados.
- Configuração/logging centralizados no pacote compartilhado.

### Checklist da issue
- [ ] Criar pacote compartilhado `shared/mtg_shared`.
- [ ] Centralizar env/config para ETL/API.
- [ ] Centralizar logging em pacote compartilhado.
- [ ] Unificar cliente Meilisearch e perfis de embedding.
- [ ] Extrair RRF para módulo compartilhado (`search/fusion`).
- [ ] Centralizar cache/prefetch de modelos (embedding + rerank).
- [ ] Reestruturar targets do `Makefile` por namespace.
- [ ] Eliminar imports cruzados entre módulos de aplicação e ETL.

---

## Issue 8 - Padronização de arquitetura/estilo

### O que já temos
- Regras de lint com Ruff e tipagem base com Pydantic.
- Estrutura atual funcional, porém compacta em `app/src/*`.

### O que falta
- Estrutura em camadas alinhada ao padrão alvo (`app/api`, `app/core`, `app/services`, `tests`).
- Separação mais forte de responsabilidades no backend.
- Cobertura de testes por contrato no padrão definido.

### Fases de implementação
1. **Fase 8.1 - Reorganização de diretórios**
Migrar `app/src/*` para layout por camadas.
2. **Fase 8.2 - Separação router x service**
Extrair lógica de orquestração para serviços.
3. **Fase 8.3 - Core técnico**
Consolidar `settings`, `logging`, `errors` e `observability`.
4. **Fase 8.4 - Testes e governança**
Criar suíte mínima de testes de endpoint/contrato/serviço e atualizar guardrails.

### Critérios de aceite
- Estrutura da API em camadas implementada.
- Router com mínima lógica de negócio.
- Suíte mínima de testes criada e executável.
- Documentação e padrões de desenvolvimento atualizados.

### Checklist da issue
- [ ] Migrar árvore `app/src` para estrutura `app/*` em camadas.
- [ ] Atualizar imports e entrypoint da API.
- [ ] Extrair `SearchService` e reduzir lógica no endpoint.
- [ ] Criar `app/core/logging.py` e remover `etl.logging_utils` da API.
- [ ] Criar `app/core/settings.py` como fonte única de configuração.
- [ ] Criar contrato de erros central em `app/core/errors.py`.
- [ ] Padronizar schemas em `app/api/schemas/*`.
- [ ] Criar `tests/` com cenários de endpoint e serviço.
- [ ] Atualizar `AGENTS.md` com guardrails de arquitetura.
- [ ] Atualizar `README.md` com nova estrutura e comandos.
- [ ] Padronizar `Makefile` por domínio.

---

## Critérios mensuráveis (pendentes de definição conjunta)
Esses limites precisam ser fechados antes de concluir as Issues 4 e 5:
- Limite de latência adicional permitido por modo de retrieval (`hybrid`, `rrf`) em P50/P95.
- Meta mínima de ganho de relevância (Recall@k/MRR) por estratégia (`rrf`, `expansão+rrf`).
- Janela exata de compatibilidade de paths legados (número de ciclos ou dias).
- Limites de erro tolerável no rollout progressivo (taxa de fallback/erro por janela).
- Limite de custo operacional de busca (ex.: número máximo de chamadas Meilisearch por request).

---

## Ordem prática recomendada
1. Issue 1
2. Issue 2
3. Issue 3
4. Issue 6 (Fases 6.1 e 6.2 em paralelo ao fim da Issue 2)
5. Issue 4
6. Issue 5
7. Issue 7
8. Issue 8
