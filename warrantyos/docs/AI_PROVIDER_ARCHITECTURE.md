# AI Provider Architecture — WarrantyOS Part 2.6

## Overview

WarrantyOS implements a provider-agnostic, offline-first AI execution framework. The architecture strictly isolates deterministic warranty eligibility logic from AI recommendations and supports real-time provider fallback and provider truthfulness telemetry.

```
+-------------------------------------------------------------------------+
|                              FastAPI API                                |
+-------------------------------------------------------------------------+
                                    |
                                    v
+-------------------------------------------------------------------------+
|                           AI Orchestrator                               |
+-------------------------------------------------------------------------+
                                    |
            +-----------------------+-----------------------+
            |                       |                       |
            v                       v                       v
+-----------------------+ +-------------------+ +-----------------------+
|    MockAIProvider     | | RocketRideAdapter | |   LocalLLMProvider    |
| (Offline Default v2.6)| |   (SDK Optional)  | |     (Local Stub)      |
+-----------------------+ +-------------------+ +-----------------------+
                                    |
                                    v
                        +-----------------------+
                        |  Configured Fallback  |
                        | (Guarantees Offline)  |
                        +-----------------------+
```

## Provider Selection & Truthfulness

- **Requested Provider**: The provider specified via `AI_PROVIDER` environment variable (e.g. `rocketride`, `local`, or `mock`).
- **Actual Executed Provider**: The provider instance that actually performed the analysis.
- **Fallback Observability**: If a requested real provider SDK is unavailable, the provider registry automatically falls back to `MockAIProvider` with `fallback_used = True` and `fallback_reason = "SDK_NOT_AVAILABLE"`.
- **Truthfulness Guarantee**: The system records `requested_provider` vs `actual_provider` in `ai_executions` telemetry and returns this to the UI, ensuring the dashboard never falsely claims real vendor execution when mock was used.

## Configuration Defaults

```env
AI_PROVIDER=mock
AI_MODEL=mock-v1
AI_PIPELINE_VERSION=2.6
AI_FALLBACK_TO_MOCK=true
AI_EXECUTION_TIMEOUT_SECONDS=30
```
