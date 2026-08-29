# AI Retrieval Architecture — WarrantyOS Part 2.6

## Overview

WarrantyOS retrieval architecture combines structured feature matching with semantic text embeddings to ground AI decision making in historical case outcomes and policy rules.

```
+------------------------------------------------------------------------+
|                              Claim Input                               |
+------------------------------------------------------------------------+
                                    |
            +-----------------------+-----------------------+
            |                                               |
            v                                               v
+-----------------------+                       +------------------------+
|  Historical Case RAG  |                       |  Policy Knowledge RAG  |
|  (6-Feature Scoring)  |                       |   (PolicyRetriever)    |
+-----------------------+                       +------------------------+
            |                                               |
            +-----------------------+-----------------------+
                                    |
                                    v
                        +------------------------+
                        |  AI Analysis Context   |
                        |   (Sanitized, No PII)  |
                        +------------------------+
```

## Explicit Historical Scoring Model

Historical case similarity uses an explicit weighted scoring model:

| Feature Component | Weight | Description |
|---|---|---|
| `semantic_similarity` | **0.40** | Cosine similarity between claim and case canonical text embeddings |
| `product_category` | **0.20** | Exact product category match (e.g. Washing Machine vs Washing Machine) |
| `product_family` | **0.15** | Exact product model match |
| `fault_similarity` | **0.15** | Token overlap / Jaccard similarity of fault description |
| `evidence_similarity` | **0.05** | Evidence completeness profile match |
| `claim_metadata_similarity` | **0.05** | Ownership and retailer metadata alignment |

## Vector Dimension Validation

- Default embedding dimension: **16** (`AI_EMBEDDING_DIMENSION=16`).
- Dimension mismatch safeguard: If query vector length != expected dimension, `VectorDimensionMismatchError` is raised with error code `VECTOR_DIMENSION_MISMATCH`.
- `MemoryVectorStore` is active by default; `PgVectorStore` can be enabled via `AI_VECTOR_STORE=pgvector`.
