import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import (
    RecommendationItem,
    RecommendationRequest,
    RecommendationResponse,
    RelatedRequest,
)


@dataclass(frozen=True)
class Product:
    product_id: str
    category: str
    price_bucket: int | None
    popularity: float
    tags: frozenset[str]


class BundleError(RuntimeError):
    pass


class RecommendationEngine:
    def __init__(self, bundle_path: str | None = None) -> None:
        default_path = Path(__file__).resolve().parents[1] / "data" / "bundle.json"
        self.bundle_path = Path(bundle_path) if bundle_path else default_path
        self.resolved_bundle_path = self.bundle_path
        self.ready = False
        self.error: str | None = None
        self.model_version = "unavailable"
        self.feature_version = "unavailable"
        self.strategy_version = "unavailable"
        self.products: dict[str, Product] = {}
        self.user_affinities: dict[str, dict[str, float]] = {}
        self.default_strategy: str | None = None
        self.ranker_promoted = False
        self.recently_bought: dict[str, frozenset[str]] = {}
        self.recent_top: list[str] = []
        self.global_top: list[str] = []
        self.category_top: dict[str, list[str]] = {}
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(self.bundle_path.read_text(encoding="utf-8"))
            if raw.get("schema_version") == "recobridge-production-alias-v1":
                alias_root = self.bundle_path.resolve().parent
                resolved = (alias_root / str(raw["path"])).resolve()
                if alias_root not in resolved.parents:
                    raise BundleError("production alias resolves outside its model root")
                expected = str(raw.get("bundle_sha256", ""))
                actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
                if not expected or actual != expected:
                    raise BundleError("production alias bundle checksum mismatch")
                raw = json.loads(resolved.read_text(encoding="utf-8"))
                self.resolved_bundle_path = resolved
            required = {"model_version", "feature_version", "strategy_version", "products"}
            missing = required.difference(raw)
            if missing:
                raise BundleError(f"bundle missing fields: {', '.join(sorted(missing))}")

            products = {}
            for item in raw["products"]:
                product = Product(
                    product_id=str(item["product_id"]),
                    category=str(item["category"]),
                    price_bucket=(
                        int(item["price_bucket"])
                        if item.get("price_bucket") is not None
                        else next(
                            (
                                int(str(tag).split(":", 1)[1])
                                for tag in item.get("tags", [])
                                if str(tag).startswith("price:")
                            ),
                            None,
                        )
                    ),
                    popularity=float(item["popularity"]),
                    tags=frozenset(str(tag) for tag in item.get("tags", [])),
                )
                products[product.product_id] = product
            if not products:
                raise BundleError("catalog is empty")

            self.model_version = str(raw["model_version"])
            self.feature_version = str(raw["feature_version"])
            self.strategy_version = str(raw["strategy_version"])
            self.products = products
            self.user_affinities = {
                str(user_id): {str(category): float(weight) for category, weight in weights.items()}
                for user_id, weights in raw.get("user_affinities", {}).items()
            }
            self.default_strategy = (
                str(raw["default_strategy"]) if raw.get("default_strategy") else None
            )
            self.ranker_promoted = bool(raw.get("ranker_promoted", False))
            self.recently_bought = {
                str(user_id): frozenset(str(product_id) for product_id in product_ids)
                for user_id, product_ids in raw.get("recently_bought", {}).items()
            }
            rankings = raw.get("rankings", {})
            self.recent_top = [str(product_id) for product_id in rankings.get("recent_top", [])]
            self.global_top = [str(product_id) for product_id in rankings.get("global_top", [])]
            self.category_top = {
                str(category): [str(product_id) for product_id in product_ids]
                for category, product_ids in rankings.get("category_top", {}).items()
            }
            self.ready = True
            self.error = None
        except (OSError, ValueError, KeyError, TypeError, BundleError) as exc:
            self.ready = False
            self.error = str(exc)

    def _ensure_ready(self) -> None:
        if not self.ready:
            raise BundleError(self.error or "recommendation bundle is unavailable")

    @staticmethod
    def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
        union = left | right
        return len(left & right) / len(union) if union else 0.0

    def recommend(self, payload: RecommendationRequest, request_id: str) -> RecommendationResponse:
        started = time.perf_counter()
        self._ensure_ready()
        affinities = self.user_affinities.get(payload.user_id or "")
        personalized = bool(affinities)
        seed = self.products.get(payload.context.product_id or "")
        use_affinities = personalized and payload.strategy != "popular"
        use_context = payload.strategy in {"hybrid", "xgboost"}

        candidate_products: list[Product]
        if self.recent_top or self.global_top:
            candidate_ids: list[str] = []

            def add(values: list[str]) -> None:
                for product_id in values:
                    if product_id not in candidate_ids:
                        candidate_ids.append(product_id)

            add(self.recent_top[:60])
            if use_affinities:
                for category, _ in sorted(
                    (affinities or {}).items(), key=lambda pair: pair[1], reverse=True
                )[:3]:
                    add(self.category_top.get(category, [])[:20])
            if use_context and payload.context.category_id:
                add(self.category_top.get(payload.context.category_id, [])[:60])
            add(self.global_top)
            bought = self.recently_bought.get(payload.user_id or "", frozenset())
            candidate_products = [
                self.products[product_id]
                for product_id in candidate_ids
                if product_id in self.products
                and product_id not in bought
                and (seed is None or product_id != seed.product_id)
            ][:200]
        else:
            candidate_products = list(self.products.values())

        ranked: list[tuple[Product, float, str]] = []
        for product in candidate_products:
            if seed and product.product_id == seed.product_id:
                continue
            score = product.popularity * 0.55
            reason = "RECENT_POPULAR"

            affinity = (affinities or {}).get(product.category, 0.0) if use_affinities else 0.0
            if affinity:
                score += affinity * 0.35
                reason = "USER_CATEGORY_AFFINITY"
            if use_context and payload.context.category_id and product.category == payload.context.category_id:
                score += 0.2
                reason = "CONTEXT_CATEGORY_MATCH"
            if use_context and seed:
                similarity = self._jaccard(seed.tags, product.tags)
                score += similarity * 0.25
                if similarity > 0:
                    reason = "ITEM_SIMILARITY"

            ranked.append((product, min(score, 0.99), reason))

        ranked.sort(key=lambda row: (-row[1], row[0].product_id))
        items = [
            RecommendationItem(
                product_id=product.product_id,
                category_id=product.category,
                price_bucket=product.price_bucket,
                score=round(score, 4),
                rank=index,
                reason_code=reason,
            )
            for index, (product, score, reason) in enumerate(ranked[: payload.top_k], start=1)
        ]
        latency_ms = max(1, round((time.perf_counter() - started) * 1000))
        if not personalized:
            strategy_used = "recent_popular"
        elif payload.strategy == "xgboost" and not self.ranker_promoted:
            strategy_used = self.default_strategy or "baseline_hybrid"
        elif self.default_strategy:
            strategy_used = self.default_strategy
        elif payload.strategy == "xgboost":
            strategy_used = "baseline_hybrid"
        else:
            strategy_used = payload.strategy
        return RecommendationResponse(
            request_id=request_id,
            model_version=self.model_version,
            feature_version=self.feature_version,
            strategy_used=strategy_used,
            degraded=not personalized or (payload.strategy == "xgboost" and not self.ranker_promoted),
            items=items,
            latency_ms=latency_ms,
        )

    def related(self, payload: RelatedRequest, request_id: str) -> RecommendationResponse:
        started = time.perf_counter()
        self._ensure_ready()
        seed = self.products.get(payload.product_id)
        degraded = seed is None

        if self.category_top or self.global_top:
            candidate_ids: list[str] = []
            if seed:
                candidate_ids.extend(self.category_top.get(seed.category, []))
            candidate_ids.extend(self.recent_top)
            candidate_ids.extend(self.global_top)
            seen: set[str] = set()
            candidate_products = []
            for product_id in candidate_ids:
                if product_id == payload.product_id or product_id in seen:
                    continue
                seen.add(product_id)
                product = self.products.get(product_id)
                if product is not None:
                    candidate_products.append(product)
                if len(candidate_products) == 200:
                    break
        else:
            candidate_products = list(self.products.values())

        ranked: list[tuple[Product, float, str]] = []
        for product in candidate_products:
            if product.product_id == payload.product_id:
                continue
            score = product.popularity * 0.4
            reason = "RECENT_POPULAR"
            if seed:
                if product.category == seed.category:
                    score += 0.35
                    reason = "SAME_CATEGORY"
                similarity = self._jaccard(seed.tags, product.tags)
                score += similarity * 0.45
                if similarity > 0:
                    reason = "ITEM_SIMILARITY"
            ranked.append((product, min(score, 0.99), reason))

        ranked.sort(key=lambda row: (-row[1], row[0].product_id))
        items = [
            RecommendationItem(
                product_id=product.product_id,
                category_id=product.category,
                price_bucket=product.price_bucket,
                score=round(score, 4),
                rank=index,
                reason_code=reason,
            )
            for index, (product, score, reason) in enumerate(ranked[: payload.top_k], start=1)
        ]
        return RecommendationResponse(
            request_id=request_id,
            model_version=self.model_version,
            feature_version=self.feature_version,
            strategy_used="item_similarity" if seed else "recent_popular",
            degraded=degraded,
            items=items,
            latency_ms=max(1, round((time.perf_counter() - started) * 1000)),
        )

    def versions(self) -> dict[str, Any]:
        return {
            "model_version": self.model_version,
            "feature_version": self.feature_version,
            "strategy_version": self.strategy_version,
        }
