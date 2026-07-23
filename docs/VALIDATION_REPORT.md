# Validation Report

| Check | Result |
|---|---|
| Internal Markdown links | PASS |
| OpenAPI YAML parse | PASS (`3.1.0`) |
| JSON syntax | PASS |
| Recommendation request example vs schema | PASS |
| Recommendation response example vs schema | PASS |
| Mermaid rendering | NOT EXECUTED — syntax reviewed manually; render in GitHub/Markdown viewer before release |
| Runtime/API implementation | PASS — 9 FastAPI tests; OpenAPI path/security surface checked |
| Frontend integration | PASS — 3 consumer/render tests, ESLint, Vinext production build and live BFF request |
| PostgreSQL event ingestion | PASS — service health, durable feedback/exposure, replay dedup and DB query |
| Dataset physical schema inspection | PASS — six Synerise Parquet files inspected and curated for 1,000/20,000-user profiles |
| ML training and evaluation | PASS — release XGBRanker/baselines/K-Means bundles, checksums, bootstrap metrics and candidate diagnostics generated |
| Ranker promotion | BLOCKED — release Recall@200 = 0.064998, below the fixed 0.70 gate |
| Governed production fallback | PASS — strongest validation baseline `category_popular` published via checksum-protected `production.json` |
| API performance | PASS — p95 = 6.069 ms over 1,000 ASGI requests; threshold = 200 ms |

## Known limitations

- XGBRanker is not promoted because candidate Recall@200 fails the fixed gate; production truthfully uses the strongest baseline fallback.
- Quantized-embedding retrieval was evaluated as an ablation and rejected because it did not improve smoke Recall@200 and reduced validation metrics.
- The OpenAPI document was parsed and example schemas were validated locally; a dedicated OpenAPI linter should be added to CI.
- Mermaid diagrams must be rendered in the repository or documentation platform to catch renderer-specific incompatibilities.
- The web production artifact built and ran end-to-end locally.
