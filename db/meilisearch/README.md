# Meilisearch Schema

This folder defines the Meilisearch index contract used by the ETL loader.

- `index_settings.json`: index-level settings (`searchableAttributes`, filters, embedders).
- `document_schema.json`: expected shape for uploaded MTG documents.

## Index

- Index UID: `mtg_cards` (default)
- Primary key: `id`
- Embedder name: `bge_m3`
- Embedder source: `userProvided`
- Vector dimensions: `1024` (BGE-M3)
