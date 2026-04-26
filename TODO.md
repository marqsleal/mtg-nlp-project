# TODO - Camada Semântica (domain semantic layer) (Pós-ETL) + Integração no Backend

## Objetivo
Implementar um job pós-ETL que constrói uma Camada Semântica (domain semantic layer) de expansão de queries a partir das cartas indexadas, persiste no Meilisearch e integra isso no backend de busca semântica para melhorar assertividade com baixo custo operacional.

## Escopo
- Construção da Camada Semântica (domain semantic layer) em etapa pós-ETL.
- Persistência em índice dedicado do Meilisearch (`mtg_domain_semantic_layer`).
- Uso da Camada Semântica (domain semantic layer) no backend (`POST /v1/search`) com feature flag e hiperparâmetros.
- Observabilidade, validação de qualidade e rollout seguro.

## Não escopo (nesta fase)
- UI específica de administração da Camada Semântica (domain semantic layer).
- Curadoria manual via painel.
- Treino de modelo próprio de reranker/expansão.

---

## Fase 0 - Decisões de Contrato

### 0.1 Índice da Camada Semântica (domain semantic layer)
- Nome: `mtg_domain_semantic_layer`.
- Primary key: `id`.
- Campos do documento:
  - `id` (string): termo base normalizado.
  - `term` (string): termo base.
  - `df` (int): document frequency.
  - `tf` (int): term frequency.
  - `idf` (float): inverse document frequency.
  - `expansions` (array): lista ordenada por score.
    - `term` (string)
    - `score` (float)
    - `kind` (`pmi` | `semantic` | `manual`)
  - `updated_at` (datetime iso)
  - `dataset_version` (string; ex.: bulk_updated_at/data do ETL)

### 0.2 Configuração
Adicionar em `.env.example`:
- `QUERY_SEMANTIC_LAYER_INDEX_UID=mtg_domain_semantic_layer`
- `QUERY_EXPANSION_ENABLED=true`
- `QUERY_EXPANSION_MAX_TERMS=5`
- `QUERY_EXPANSION_MIN_SCORE=0.30`
- `QUERY_EXPANSION_CACHE_TTL_SECONDS=600`

### 0.3 Critérios mínimos
- Top 3-5 expansões por termo.
- Sem expansão para termos com baixa confiança.
- Expansão aplicada apenas no retrieval (rerank mantém decisão final).

---

## Fase 1 - Job Pós-ETL (Builder da Camada Semântica)

### 1.1 Estrutura de código
Criar módulo:
- `etl/meilisearch/semantic_layer.py`
- `etl/run_semantic_layer_build.py`

### 1.2 Pipeline do builder
1. Ler documentos de `mtg_cards` (campos textuais relevantes).
2. Normalizar tokens (lowercase, trim, ruído/pontuação controlada, preservar tokens MTG úteis).
3. Gerar estatísticas:
   - TF
   - DF
   - IDF
4. Gerar candidatos de expansão por:
   - coocorrência PMI (base)
   - opcional: similaridade semântica para desempate/refino
5. Calcular score final dos candidatos (fórmula ponderada).
6. Truncar para top-N expansões por termo.
7. Persistir documentos no índice `mtg_domain_semantic_layer`.

### 1.3 Persistência no Meilisearch
- Garantir criação do índice `mtg_domain_semantic_layer`.
- Definir settings apropriados (searchable/filterable/sortable mínimos).
- Upsert de documentos em lotes.
- Rebuild idempotente (mesma versão substitui conteúdo anterior).

### 1.4 Execução operacional
- Adicionar alvo no `Makefile`:
  - `make semantic_layer_build`
- Encadear no fluxo pós-ETL (manual inicialmente; automatizar depois).

### 1.5 Critérios de aceite
- Índice `mtg_domain_semantic_layer` criado/populado.
- Documento por termo com `expansions` ordenadas.
- Execução completa sem erro em ambiente local.

---

## Fase 2 - Integração no Backend

### 2.1 Serviço de expansão
Criar:
- `app/src/services/domain_semantic_layer_service.py`

Responsabilidades:
- Normalizar query de entrada.
- Consultar `mtg_domain_semantic_layer` por token/n-grama.
- Agregar expansões por score.
- Aplicar limites (`max_terms`, `min_score`).
- Montar query enriquecida final.
- Cache em memória por termo (TTL).

### 2.2 Ajustes no endpoint `/v1/search`
Adicionar no request (opcional):
- `query_expansion` (bool)
- `expansion_max_terms` (int)
- `expansion_min_score` (float)

Comportamento:
1. Query original -> expansão (se habilitado).
2. Retrieval com query enriquecida + vector/hybrid.
3. Reranking permanece após retrieval.
4. Resposta inclui metadados de expansão (debug controlado).

### 2.3 Metadados de resposta
Adicionar em `meta`:
- `query_expansion_applied` (bool)
- `expanded_terms` (lista curta)
- `expanded_query` (opcional; controlado por flag interna)

### 2.4 Critérios de aceite
- Endpoint funciona com expansão ligada/desligada.
- Sem regressão quando expansão desabilitada.
- Latência adicional dentro de limite aceitável (ex.: +5 a +20ms com cache quente).

### 2.5 Warmup e latência de primeira requisição
1. Inicialização preguiçosa (lazy) do reranker:
   - carregar modelo de rerank apenas quando `rerank=true`.
   - manter busca híbrida funcional mesmo sem reranker carregado.
2. Default operacional de rerank:
   - manter `rerank=false` por padrão para reduzir custo inicial.
   - permitir override por request.
3. Warmup explícito no startup:
   - executar query sintética interna após subir app para aquecer embedding/meilisearch.
   - opcionalmente aquecer reranker via flag dedicada de startup.

---

## Fase 3 - Qualidade e Métricas

### 3.1 Conjunto de avaliação
Criar dataset de queries reais MTG com relevância esperada (top-k).

### 3.2 Métricas
Comparar baseline vs expansão em:
- Recall@k
- MRR
- nDCG@k (opcional)
- latência total
- latência de cold start vs warm start (P50/P95)

### 3.3 Logging estruturado
Adicionar logs `ENTER/EXIT` no builder e no `DomainSemanticLayerService`:
- termos consultados
- quantidade de expansões aplicadas
- tempo de lookup
- cache hit/miss

### 3.4 Critérios de aceite
- Ganho mensurável em pelo menos uma métrica de relevância sem degradar latência além do limite definido.
- Queda observável na latência da primeira busca após warmup controlado.

---

## Fase 4 - Rollout Seguro

### 4.1 Feature flag
- `QUERY_EXPANSION_ENABLED` global.
- Override por request.

### 4.2 Estratégia de rollout
1. Ambiente local/staging com expansão desligada por default.
2. Ativar para testes internos.
3. Ativar progressivamente (por ambiente/percentual).
4. Operar API em modo "processo quente" em produção (sem `--reload`).
5. Minimizar reinícios para preservar modelos em memória.

### 4.3 Fallback
- Em falha do índice da Camada Semântica (domain semantic layer), seguir com query original (não quebrar busca).

---

## Fase 5 - Reestruturação do Repositório (após Camada Semântica)

### 5.1 Objetivo
- Reduzir duplicação entre ETL e API.
- Criar pacotes compartilhados para reutilização (e extensão futura para `app/view`).
- Centralizar configuração de env/logging/clients e simplificar operação via `Makefile`.

### 5.2 Mapa atual de duplicação (API x ETL)
1. Configuração e env:
   - API: `app/src/config.py` (Pydantic Settings).
   - ETL: `etl/run_meilisearch_ingest.py` (argparse + `os.getenv` em múltiplos flags).
2. Cliente Meilisearch/HTTP:
   - API: `app/src/services/meilisearch_service.py`.
   - ETL: `etl/meilisearch/client.py`.
3. Embeddings e perfil de modelo:
   - API: `app/src/services/embedding_service.py`.
   - ETL: `etl/meilisearch/vectorizer.py` + `etl/meilisearch/embedding_profiles.py`.
4. Normalização de texto/query:
   - ETL: `etl/scryfall/transform.py`.
   - API: `app/src/models/search.py` (normalização de query no schema).
5. Logging e observabilidade:
   - ETL: `etl/logging_utils.py`.
   - API reutiliza `etl.logging_utils` em `app/src/main.py`, criando acoplamento indevido (API depende de ETL).
6. Comandos operacionais:
   - `Makefile` mistura targets ETL/API sem namespace de domínio (cresce mal para view e jobs adicionais).

### 5.3 Estrutura alvo de pacotes compartilhados
Criar pacote compartilhado (nome sugestão):
- `shared/mtg_shared/`
  - `config/`
    - `base.py` (base settings e helpers de env)
    - `etl.py`
    - `api.py`
  - `logging/`
    - `setup.py` (configuração padrão estruturada)
    - `context.py` (helpers de correlação/request-id)
  - `meilisearch/`
    - `client.py` (wrapper único para auth/retry/task wait)
    - `models.py` (tipos comuns)
  - `embeddings/`
    - `profiles.py` (catálogo único de modelos)
    - `factory.py` (instanciação de encoder)
  - `text/`
    - `normalize.py` (normalização canônica para ingest/query)
  - `contracts/`
    - `search.py` (schemas compartilhados entre API e futuros consumidores)

### 5.4 Ajustes por camada
1. ETL:
   - Migrar uso de config/env para `mtg_shared.config.etl`.
   - Trocar `etl/meilisearch/client.py` por `mtg_shared.meilisearch.client`.
   - Trocar `embedding_profiles.py` por `mtg_shared.embeddings.profiles`.
2. API:
   - Migrar `app/src/config.py` para herdar de `mtg_shared.config.api`.
   - Trocar normalização local por `mtg_shared.text.normalize`.
   - Trocar dependência `etl.logging_utils` por `mtg_shared.logging.setup`.
   - Centralizar paths/caches de modelos (`HF_HOME`, `TRANSFORMERS_CACHE`) e flags de warmup em config compartilhada.
3. View (futuro):
   - Consumir `contracts/search.py` para tipar payloads e reduzir drift de contrato.

### 5.5 Makefile e DX (Developer Experience)
- Reorganizar alvos por namespace:
  - `etl.scryfall`, `etl.ingest`, `etl.semantic_layer`
  - `api.dev`, `api.lint`, `api.test`
  - `infra.meili.up`, `infra.meili.down`, `infra.meili.logs`
- Adicionar alvo de validação de configuração:
  - `config.check` (valida env obrigatório para ETL/API).
- Adicionar alvo único de bootstrap:
  - `dev.bootstrap` (venv + deps + checks básicos).
- Adicionar alvos de modelo e warmup:
  - `models.prefetch` (download/pinning local dos modelos de embedding/rerank)
  - `api.warmup` (executa aquecimento explícito pós-startup)

### 5.6 Estratégia de migração (sem quebrar fluxo)
1. Criar `mtg_shared` com wrappers compatíveis.
2. Migrar API para shared (primeiro, menor risco operacional).
3. Migrar ETL para shared mantendo CLI/flags compatíveis.
4. Remover código legado duplicado após 1 ciclo de validação.

### 5.7 Critérios de aceite
- Sem import cruzado `app -> etl` ou `etl -> app`.
- Configuração e logging vindos de pacote compartilhado.
- Cliente Meilisearch e perfis de embedding unificados.
- `Makefile` com targets agrupados por domínio.
- Testes de regressão ETL e API mantendo comportamento atual.
- Modelos podem ser carregados localmente sem dependência de download no primeiro request.

---

## Checklist de Implementação
- [ ] Criar módulo ETL do builder da Camada Semântica (domain semantic layer).
- [ ] Criar CLI `run_semantic_layer_build.py`.
- [ ] Criar settings e docs do índice `mtg_domain_semantic_layer`.
- [ ] Adicionar alvo `make semantic_layer_build`.
- [ ] Implementar `DomainSemanticLayerService` no backend.
- [ ] Integrar expansão no endpoint `/v1/search`.
- [ ] Adicionar cache TTL de expansões.
- [ ] Adicionar logs estruturados no builder/serviço.
- [ ] Adicionar testes unitários e integração.
- [ ] Validar métricas baseline vs expansão.
- [ ] Implementar lazy load do reranker (`rerank=true`).
- [ ] Manter `rerank=false` como default operacional.
- [ ] Implementar warmup explícito no startup da API.
- [ ] Garantir execução de produção sem `--reload` e com processo quente.
- [ ] Criar pacote compartilhado `shared/mtg_shared`.
- [ ] Centralizar env/config para ETL/API.
- [ ] Centralizar logging em pacote compartilhado.
- [ ] Unificar cliente Meilisearch e perfis de embedding.
- [ ] Centralizar cache/prefetch de modelos (embedding + rerank).
- [ ] Reestruturar targets do `Makefile` por namespace.
- [ ] Eliminar imports cruzados entre módulos de aplicação e ETL.

---

## Ordem Recomendada (prática)
1. Fase 0
2. Fase 1
3. Fase 2 (com flag desligada)
4. Fase 3
5. Fase 4
6. Fase 5
