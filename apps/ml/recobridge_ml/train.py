"""Leakage-aware baseline, clustering, ranking, evaluation, and bundle export."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

import duckdb
import joblib
import numpy as np
import pandas as pd
import scipy
import sklearn
import xgboost
from scipy.spatial import cKDTree
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRanker


FEATURE_VERSION = "recobridge-ranking-v1"
STRATEGY_VERSION = "hybrid-candidates-v1"
EMBEDDING_STRATEGY_VERSION = "hybrid-candidates-v2-experimental"
USER_FEATURES = [
    "buy_count",
    "cart_count",
    "remove_count",
    "search_count",
    "page_count",
    "active_days",
    "unique_items",
    "unique_categories",
    "buy_recency_days",
    "event_recency_days",
    "cart_to_buy_ratio",
    "remove_to_cart_ratio",
]
RANKING_FEATURES = [
    "recent_source_rank",
    "cluster_source_rank",
    "category_source_rank",
    "similarity_source_rank",
    "global_source_rank",
    "item_popularity",
    "item_recent_popularity",
    "item_cluster_popularity",
    "item_category_popularity",
    "user_item_interactions",
    "user_item_buys",
    "user_item_carts",
    "category_affinity",
    "same_last_category",
    "price_affinity",
    "cluster_distance",
    *[f"user_{name}" for name in USER_FEATURES],
]
POSITIVE_EVENTS = ("BUY", "ADD_TO_CART")
EVENT_WEIGHT = {"BUY": 3.0, "ADD_TO_CART": 1.0, "REMOVE_FROM_CART": 0.0}
BOOTSTRAP_SAMPLES = 1000


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    output_root: Path
    profile: str
    seed: int
    version: str
    overwrite: bool
    use_embedding_candidates: bool = False


@dataclass
class CandidateState:
    global_top: list[int]
    recent_top: list[int]
    global_score: dict[int, float]
    recent_score: dict[int, float]
    cluster_top: dict[int, list[int]]
    cluster_score: dict[tuple[int, int], float]
    category_top: dict[int, list[int]]
    category_score: dict[tuple[int, int], float]
    user_categories: dict[str, Counter[int]]
    user_items: dict[str, dict[int, Counter[str]]]
    user_recent_items: dict[str, list[int]]
    user_recent_buys: dict[str, set[int]]
    user_last_category: dict[str, int]
    user_mean_price: dict[str, float]
    item_category: dict[int, int]
    item_price: dict[int, int]
    item_neighbors: dict[int, list[int]]


@dataclass
class QueryBatch:
    x: np.ndarray
    y: np.ndarray
    groups: list[int]
    users: list[str]
    product_ids: list[np.ndarray]
    target_labels: list[dict[int, int]]
    candidate_recall: float
    skipped_without_candidate_positive: int
    candidate_recall_at_100: float = 0.0
    candidate_query_coverage_at_100: float = 0.0
    candidate_query_coverage_at_200: float = 0.0
    candidate_eligible_recall_at_200: float = 0.0
    filtered_positive_labels: int = 0
    unique_candidates_at_200: int = 0
    source_recall_at_200: dict[str, float] = field(default_factory=dict)
    target_query_count: int = 0
    positive_label_count: int = 0


@dataclass
class CatalogEmbeddingIndex:
    product_ids: np.ndarray
    vectors: np.ndarray
    tree: cKDTree
    neighbors_by_product: dict[int, list[int]] = field(default_factory=dict)

    @classmethod
    def load(
        cls, connection: duckdb.DuckDBPyConnection, data_dir: Path
    ) -> CatalogEmbeddingIndex:
        path = (data_dir / "catalog.parquet").as_posix().replace("'", "''")
        catalog = connection.execute(
            f"SELECT product_id, embedding_codes FROM read_parquet('{path}') ORDER BY product_id"
        ).fetchnumpy()
        product_ids = catalog["product_id"].astype(np.int64, copy=False)
        vectors = np.stack(catalog["embedding_codes"]).astype(np.float32, copy=False)
        if vectors.ndim != 2 or len(vectors) != len(product_ids):
            raise ValueError("Catalog embedding matrix is not rectangular")
        return cls(
            product_ids=product_ids,
            vectors=vectors,
            tree=cKDTree(vectors, balanced_tree=False, compact_nodes=False),
        )

    def resolve(self, products: Iterable[int], k: int = 8) -> dict[int, list[int]]:
        requested = sorted({int(product) for product in products})
        missing = [product for product in requested if product not in self.neighbors_by_product]
        if missing:
            product_array = np.asarray(missing, dtype=np.int64)
            positions = np.searchsorted(self.product_ids, product_array)
            valid = positions < len(self.product_ids)
            valid &= self.product_ids[np.minimum(positions, len(self.product_ids) - 1)] == product_array
            valid_products = product_array[valid]
            valid_positions = positions[valid]
            if len(valid_products):
                _, neighbor_positions = self.tree.query(
                    self.vectors[valid_positions],
                    k=min(k + 1, len(self.product_ids)),
                    p=1,
                    eps=0.1,
                    workers=max(1, (os.cpu_count() or 2) - 1),
                )
                neighbor_positions = np.atleast_2d(neighbor_positions)
                for product, row in zip(valid_products, neighbor_positions, strict=True):
                    neighbors: list[int] = []
                    for position in row:
                        neighbor = int(self.product_ids[int(position)])
                        if neighbor != int(product) and neighbor not in neighbors:
                            neighbors.append(neighbor)
                        if len(neighbors) == k:
                            break
                    self.neighbors_by_product[int(product)] = neighbors
            for product in product_array[~valid]:
                self.neighbors_by_product[int(product)] = []
        return {product: self.neighbors_by_product[product] for product in requested}


def _json_default(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Cannot serialize {type(value)!r}")


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=_json_default) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _validate_input(data_dir: Path, profile: str) -> tuple[dict[str, Any], dict[str, Any]]:
    required = [
        "canonical_events.parquet",
        "catalog.parquet",
        "cohort.parquet",
        "data_manifest.json",
        "data_quality_report.json",
        "split_manifest.json",
    ]
    missing = [name for name in required if not (data_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing curated artifacts: {', '.join(missing)}")
    manifest = json.loads((data_dir / "data_manifest.json").read_text(encoding="utf-8"))
    quality = json.loads((data_dir / "data_quality_report.json").read_text(encoding="utf-8"))
    if manifest.get("profile") != profile:
        raise ValueError(f"Data profile is {manifest.get('profile')!r}, expected {profile!r}")
    if quality.get("status") != "pass":
        raise ValueError("Curated data quality gate did not pass")
    for name in ("canonical_events.parquet", "catalog.parquet", "cohort.parquet"):
        expected = manifest.get("artifacts", {}).get(name, {}).get("sha256")
        actual = _sha256(data_dir / name)
        if not expected or actual != expected:
            raise ValueError(f"Checksum mismatch for {name}")
    split = json.loads((data_dir / "split_manifest.json").read_text(encoding="utf-8"))
    return manifest, split


def _timestamp(value: str) -> pd.Timestamp:
    return pd.Timestamp(value).tz_convert("UTC")


def _sql_timestamp(value: pd.Timestamp) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S%z")


def _load_cohort(connection: duckdb.DuckDBPyConnection, data_dir: Path) -> list[str]:
    path = (data_dir / "cohort.parquet").as_posix().replace("'", "''")
    rows = connection.execute(
        f"SELECT CAST(client_id AS VARCHAR) FROM read_parquet('{path}') ORDER BY client_id"
    ).fetchall()
    return [row[0] for row in rows]


def _load_item_events(connection: duckdb.DuckDBPyConnection, data_dir: Path) -> pd.DataFrame:
    path = (data_dir / "canonical_events.parquet").as_posix().replace("'", "''")
    return connection.execute(
        f"""
        SELECT event_time, event_type, user_id, product_id, category_id, price_bucket
        FROM read_parquet('{path}')
        WHERE event_type IN ('BUY', 'ADD_TO_CART', 'REMOVE_FROM_CART')
          AND product_id IS NOT NULL AND is_catalog_match
        ORDER BY event_time, event_id
        """
    ).fetchdf()


def _load_user_features(
    connection: duckdb.DuckDBPyConnection,
    data_dir: Path,
    cohort: list[str],
    cutoff: pd.Timestamp,
) -> pd.DataFrame:
    path = (data_dir / "canonical_events.parquet").as_posix().replace("'", "''")
    cutoff_sql = _sql_timestamp(cutoff)
    aggregated = connection.execute(
        f"""
        SELECT user_id,
               count(*) FILTER (WHERE event_type = 'BUY') AS buy_count,
               count(*) FILTER (WHERE event_type = 'ADD_TO_CART') AS cart_count,
               count(*) FILTER (WHERE event_type = 'REMOVE_FROM_CART') AS remove_count,
               count(*) FILTER (WHERE event_type = 'SEARCH') AS search_count,
               count(*) FILTER (WHERE event_type = 'PAGE_VISIT') AS page_count,
               count(DISTINCT CAST(event_time AS DATE)) AS active_days,
               count(DISTINCT product_id) FILTER (WHERE product_id IS NOT NULL) AS unique_items,
               count(DISTINCT category_id) FILTER (WHERE category_id IS NOT NULL) AS unique_categories,
               date_diff('second', max(event_time) FILTER (WHERE event_type = 'BUY'),
                         TIMESTAMPTZ '{cutoff_sql}') / 86400.0 AS buy_recency_days,
               date_diff('second', max(event_time), TIMESTAMPTZ '{cutoff_sql}') / 86400.0
                   AS event_recency_days
        FROM read_parquet('{path}')
        WHERE event_time < TIMESTAMPTZ '{cutoff_sql}'
        GROUP BY user_id
        """
    ).fetchdf()
    frame = pd.DataFrame({"user_id": cohort}).merge(aggregated, on="user_id", how="left")
    count_columns = USER_FEATURES[:8]
    frame[count_columns] = frame[count_columns].fillna(0.0).astype(float)
    frame["buy_recency_days"] = frame["buy_recency_days"].fillna(3650.0).clip(0, 3650)
    frame["event_recency_days"] = frame["event_recency_days"].fillna(3650.0).clip(0, 3650)
    frame["cart_to_buy_ratio"] = frame["cart_count"] / (frame["buy_count"] + 1.0)
    frame["remove_to_cart_ratio"] = frame["remove_count"] / (frame["cart_count"] + 1.0)
    for column in USER_FEATURES[:10]:
        frame[column] = np.log1p(frame[column].astype(float))
    return frame[["user_id", *USER_FEATURES]]


def _fit_clusters(
    train_users: pd.DataFrame, seed: int
) -> tuple[StandardScaler, KMeans, dict[str, Any]]:
    scaler = StandardScaler()
    scaled = scaler.fit_transform(train_users[USER_FEATURES].to_numpy(dtype=np.float64))
    candidates: list[dict[str, Any]] = []
    models: dict[int, KMeans] = {}
    sample_size = min(5000, len(scaled))
    rng = np.random.default_rng(seed)
    sample_indices = np.sort(rng.choice(len(scaled), sample_size, replace=False))
    for k in (4, 6, 8, 10):
        model = KMeans(n_clusters=k, n_init=10, random_state=seed)
        labels = model.fit_predict(scaled)
        counts = np.bincount(labels, minlength=k)
        minimum_ratio = float(counts.min() / len(labels))
        sample_labels = labels[sample_indices]
        record = {
            "k": k,
            "silhouette": float(silhouette_score(scaled[sample_indices], sample_labels)),
            "davies_bouldin": float(davies_bouldin_score(scaled, labels)),
            "minimum_cluster_ratio": minimum_ratio,
            "cluster_sizes": counts.tolist(),
            "passes_minimum_cluster_ratio": minimum_ratio >= 0.03,
        }
        candidates.append(record)
        models[k] = model
    eligible = [record for record in candidates if record["passes_minimum_cluster_ratio"]]
    if eligible:
        selected = max(eligible, key=lambda record: record["silhouette"])
        rule = "highest_silhouette_with_minimum_cluster_ratio"
        limitation = None
    else:
        selected = min(candidates, key=lambda record: record["davies_bouldin"])
        rule = "lowest_davies_bouldin_fallback"
        limitation = "No k candidate had a minimum cluster containing at least 3% of users."
    report = {
        "feature_names": USER_FEATURES,
        "candidates": candidates,
        "selected_k": selected["k"],
        "selection_rule": rule,
        "limitation": limitation,
        "fit_user_count": len(train_users),
    }
    return scaler, models[selected["k"]], report


def _assign_clusters(
    users: pd.DataFrame, scaler: StandardScaler, model: KMeans
) -> tuple[dict[str, int], dict[str, float]]:
    scaled = scaler.transform(users[USER_FEATURES].to_numpy(dtype=np.float64))
    labels = model.predict(scaled)
    distances = model.transform(scaled).min(axis=1)
    return (
        dict(zip(users["user_id"], labels.astype(int), strict=True)),
        dict(zip(users["user_id"], distances.astype(float), strict=True)),
    )


def _top(counter: Counter[int], n: int) -> list[int]:
    return [int(product_id) for product_id, _ in counter.most_common(n)]


def _candidate_state(
    history: pd.DataFrame,
    cutoff: pd.Timestamp,
    clusters: dict[str, int],
    embedding_index: CatalogEmbeddingIndex | None = None,
) -> CandidateState:
    global_counts: Counter[int] = Counter()
    recent_counts: Counter[int] = Counter()
    cluster_counts: dict[int, Counter[int]] = defaultdict(Counter)
    category_counts: dict[int, Counter[int]] = defaultdict(Counter)
    user_categories: dict[str, Counter[int]] = defaultdict(Counter)
    user_items: dict[str, dict[int, Counter[str]]] = defaultdict(lambda: defaultdict(Counter))
    user_item_last_seen: dict[str, dict[int, pd.Timestamp]] = defaultdict(dict)
    user_recent_buys: dict[str, set[int]] = defaultdict(set)
    user_last_category: dict[str, int] = {}
    user_price_total: Counter[str] = Counter()
    user_price_count: Counter[str] = Counter()
    item_category: dict[int, int] = {}
    item_price: dict[int, int] = {}
    recent_start = cutoff - timedelta(days=14)
    for row in history.itertuples(index=False):
        user = str(row.user_id)
        product = int(row.product_id)
        category = int(row.category_id)
        price = int(row.price_bucket)
        event_type = str(row.event_type)
        weight = EVENT_WEIGHT[event_type]
        item_category[product] = category
        item_price[product] = price
        user_items[user][product][event_type] += 1
        user_last_category[user] = category
        user_price_total[user] += price
        user_price_count[user] += 1
        if weight <= 0:
            continue
        user_item_last_seen[user][product] = row.event_time
        if event_type == "BUY" and row.event_time >= recent_start:
            user_recent_buys[user].add(product)
        global_counts[product] += weight
        category_counts[category][product] += weight
        user_categories[user][category] += weight
        cluster_counts[clusters.get(user, -1)][product] += weight
        if row.event_time >= recent_start:
            recent_counts[product] += weight
    user_recent_items = {
        user: [
            product
            for product, _ in sorted(last_seen.items(), key=lambda pair: pair[1], reverse=True)[:10]
        ]
        for user, last_seen in user_item_last_seen.items()
    }
    neighbor_counts: dict[int, Counter[int]] = defaultdict(Counter)
    for recent_items in user_recent_items.values():
        for index, product in enumerate(recent_items):
            for neighbor in recent_items[index + 1 :]:
                neighbor_counts[product][neighbor] += 1
                neighbor_counts[neighbor][product] += 1
    cooccurrence_neighbors = {product: _top(counts, 20) for product, counts in neighbor_counts.items()}
    embedding_neighbors = (
        embedding_index.resolve(
            product for recent_items in user_recent_items.values() for product in recent_items[:5]
        )
        if embedding_index is not None
        else {}
    )
    item_neighbors: dict[int, list[int]] = {}
    for product in set(cooccurrence_neighbors) | set(embedding_neighbors):
        merged = list(embedding_neighbors.get(product, []))
        merged.extend(
            neighbor
            for neighbor in cooccurrence_neighbors.get(product, [])
            if neighbor not in merged
        )
        item_neighbors[product] = merged[:20]
    return CandidateState(
        global_top=_top(global_counts, 300),
        recent_top=_top(recent_counts, 300),
        global_score=dict(global_counts),
        recent_score=dict(recent_counts),
        cluster_top={key: _top(value, 120) for key, value in cluster_counts.items()},
        cluster_score={
            (cluster, product): float(score)
            for cluster, counts in cluster_counts.items()
            for product, score in counts.items()
        },
        category_top={key: _top(value, 120) for key, value in category_counts.items()},
        category_score={
            (category, product): float(score)
            for category, counts in category_counts.items()
            for product, score in counts.items()
        },
        user_categories=dict(user_categories),
        user_items={user: dict(items) for user, items in user_items.items()},
        user_recent_items=user_recent_items,
        user_recent_buys={user: set(products) for user, products in user_recent_buys.items()},
        user_last_category=user_last_category,
        user_mean_price={
            user: user_price_total[user] / count for user, count in user_price_count.items()
        },
        item_category=item_category,
        item_price=item_price,
        item_neighbors=item_neighbors,
    )


def _add_source(
    ordered: list[int], ranks: dict[int, dict[str, int]], source: str, values: Iterable[int], limit: int
) -> None:
    for rank, product in enumerate(values, start=1):
        if rank > limit:
            break
        product = int(product)
        ranks.setdefault(product, {})[source] = rank
        if product not in ordered:
            ordered.append(product)


def _candidates_for_user(
    user: str, state: CandidateState, cluster: int
) -> tuple[list[int], dict[int, dict[str, int]]]:
    ordered: list[int] = []
    ranks: dict[int, dict[str, int]] = {}
    _add_source(ordered, ranks, "recent", state.recent_top, 60)
    _add_source(ordered, ranks, "cluster", state.cluster_top.get(cluster, []), 60)
    categories = [category for category, _ in state.user_categories.get(user, Counter()).most_common(3)]
    category_values: list[int] = []
    for category in categories:
        category_values.extend(state.category_top.get(category, [])[:20])
    _add_source(ordered, ranks, "category", category_values, 60)
    similarity_values: list[int] = []
    for seed_product in state.user_recent_items.get(user, [])[:5]:
        similarity_values.extend(state.item_neighbors.get(seed_product, [])[:8])
    # Re-orderable products are a safe identity-similarity fallback unless bought recently.
    similarity_values.extend(state.user_recent_items.get(user, []))
    last_category = state.user_last_category.get(user)
    if last_category is not None:
        similarity_values.extend(state.category_top.get(last_category, []))
    _add_source(ordered, ranks, "similarity", similarity_values, 40)
    _add_source(ordered, ranks, "global", state.global_top, 300)
    recently_bought = state.user_recent_buys.get(user, set())
    return [product for product in ordered if product not in recently_bought][:200], ranks


def _target_labels(target: pd.DataFrame) -> dict[str, dict[int, int]]:
    labels: dict[str, dict[int, int]] = defaultdict(dict)
    for row in target.itertuples(index=False):
        relevance = 2 if row.event_type == "BUY" else 1
        user_labels = labels[str(row.user_id)]
        product = int(row.product_id)
        user_labels[product] = max(relevance, user_labels.get(product, 0))
    return dict(labels)


def _rank_value(ranks: dict[str, int], source: str) -> float:
    rank = ranks.get(source)
    return 0.0 if rank is None else 1.0 / rank


def _build_batch(
    state: CandidateState,
    labels: dict[str, dict[int, int]],
    user_features: pd.DataFrame,
    clusters: dict[str, int],
    cluster_distances: dict[str, float],
    *,
    training: bool,
) -> QueryBatch:
    user_feature_map = {
        str(row.user_id): np.asarray([getattr(row, name) for name in USER_FEATURES], dtype=np.float32)
        for row in user_features.itertuples(index=False)
    }
    rows: list[list[float]] = []
    targets: list[int] = []
    groups: list[int] = []
    users: list[str] = []
    query_products: list[np.ndarray] = []
    query_labels: list[dict[int, int]] = []
    recalled_at_100 = 0
    recalled_at_200 = 0
    positives = 0
    filtered_positives = 0
    covered_queries_at_100 = 0
    covered_queries_at_200 = 0
    source_recalled: Counter[str] = Counter()
    unique_candidates: set[int] = set()
    skipped = 0
    for user in sorted(labels):
        truth = labels[user]
        positive_products = set(truth)
        positives += len(positive_products)
        filtered_positives += len(positive_products.intersection(state.user_recent_buys.get(user, set())))
        cluster = clusters.get(user, -1)
        candidates, source_ranks = _candidates_for_user(user, state, cluster)
        if not candidates:
            if training:
                skipped += 1
            continue
        hits_at_100 = positive_products.intersection(candidates[:100])
        hits_at_200 = positive_products.intersection(candidates)
        recalled_at_100 += len(hits_at_100)
        recalled_at_200 += len(hits_at_200)
        covered_queries_at_100 += bool(hits_at_100)
        covered_queries_at_200 += bool(hits_at_200)
        unique_candidates.update(candidates)
        for source in ("recent", "cluster", "category", "similarity", "global"):
            source_recalled[source] += sum(
                product in hits_at_200 and source in source_ranks.get(product, {})
                for product in positive_products
            )
        if training and not hits_at_200:
            skipped += 1
            continue
        user_vector = user_feature_map[user]
        affinity = state.user_categories.get(user, Counter())
        affinity_total = float(sum(affinity.values())) or 1.0
        last_category = state.user_last_category.get(user)
        mean_price = state.user_mean_price.get(user, 0.0)
        for product in candidates:
            category = state.item_category.get(product, -1)
            price = state.item_price.get(product, -1)
            item_counts = state.user_items.get(user, {}).get(product, Counter())
            ranks = source_ranks.get(product, {})
            rows.append(
                [
                    _rank_value(ranks, "recent"),
                    _rank_value(ranks, "cluster"),
                    _rank_value(ranks, "category"),
                    _rank_value(ranks, "similarity"),
                    _rank_value(ranks, "global"),
                    math.log1p(state.global_score.get(product, 0.0)),
                    math.log1p(state.recent_score.get(product, 0.0)),
                    math.log1p(state.cluster_score.get((cluster, product), 0.0)),
                    math.log1p(state.category_score.get((category, product), 0.0)),
                    math.log1p(sum(item_counts.values())),
                    math.log1p(item_counts.get("BUY", 0)),
                    math.log1p(item_counts.get("ADD_TO_CART", 0)),
                    affinity.get(category, 0.0) / affinity_total,
                    float(category == last_category),
                    1.0 / (1.0 + abs(price - mean_price)) if price >= 0 else 0.0,
                    float(cluster_distances.get(user, 0.0)),
                    *user_vector.tolist(),
                ]
            )
            targets.append(truth.get(product, 0))
        groups.append(len(candidates))
        users.append(user)
        query_products.append(np.asarray(candidates, dtype=np.int64))
        query_labels.append(truth)
    query_count = len(labels)
    eligible_positives = positives - filtered_positives
    return QueryBatch(
        x=np.asarray(rows, dtype=np.float32),
        y=np.asarray(targets, dtype=np.float32),
        groups=groups,
        users=users,
        product_ids=query_products,
        target_labels=query_labels,
        candidate_recall=float(recalled_at_200 / positives) if positives else 0.0,
        skipped_without_candidate_positive=skipped,
        candidate_recall_at_100=float(recalled_at_100 / positives) if positives else 0.0,
        candidate_query_coverage_at_100=(
            float(covered_queries_at_100 / query_count) if query_count else 0.0
        ),
        candidate_query_coverage_at_200=(
            float(covered_queries_at_200 / query_count) if query_count else 0.0
        ),
        candidate_eligible_recall_at_200=(
            float(recalled_at_200 / eligible_positives) if eligible_positives else 0.0
        ),
        filtered_positive_labels=filtered_positives,
        unique_candidates_at_200=len(unique_candidates),
        source_recall_at_200={
            source: float(count / positives) if positives else 0.0
            for source, count in sorted(source_recalled.items())
        },
        target_query_count=query_count,
        positive_label_count=positives,
    )


def _strategy_scores(batch: QueryBatch, name: str) -> np.ndarray:
    column = {
        "recent_popular": 0,
        "cluster_popular": 1,
        "category_popular": 2,
        "global_popular": 4,
    }[name]
    return batch.x[:, column]


def _dcg(relevances: Iterable[int], k: int) -> float:
    return sum(
        (2.0**rel - 1.0) / math.log2(index + 2)
        for index, rel in enumerate(relevances)
        if index < k
    )


def _query_metrics(
    batch: QueryBatch, scores: np.ndarray, k: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray, set[int]]:
    if len(scores) != len(batch.y):
        raise ValueError(f"Expected {len(batch.y)} scores, received {len(scores)}")
    offset = 0
    ndcgs: list[float] = []
    recalls: list[float] = []
    reciprocal_ranks: list[float] = []
    recommended: set[int] = set()
    for group_size, products, truth in zip(
        batch.groups, batch.product_ids, batch.target_labels, strict=True
    ):
        group_scores = scores[offset : offset + group_size]
        offset += group_size
        order = np.argsort(-group_scores, kind="stable")[:k]
        ranked_products = products[order]
        ranked_relevance = [truth.get(int(product), 0) for product in ranked_products]
        ideal = sorted(truth.values(), reverse=True)[:k]
        ideal_dcg = _dcg(ideal, k)
        ndcgs.append(_dcg(ranked_relevance, k) / ideal_dcg if ideal_dcg else 0.0)
        positive = set(truth)
        hits = len(positive.intersection(int(product) for product in ranked_products))
        recalls.append(hits / len(positive) if positive else 0.0)
        first = next((index for index, rel in enumerate(ranked_relevance, start=1) if rel > 0), None)
        reciprocal_ranks.append(0.0 if first is None else 1.0 / first)
        recommended.update(int(product) for product in ranked_products)
    return (
        np.asarray(ndcgs, dtype=np.float64),
        np.asarray(recalls, dtype=np.float64),
        np.asarray(reciprocal_ranks, dtype=np.float64),
        recommended,
    )


def _bootstrap_mean_interval(
    values: np.ndarray, *, seed: int, samples: int = BOOTSTRAP_SAMPLES
) -> dict[str, Any]:
    if len(values) == 0:
        return {"lower": 0.0, "upper": 0.0, "confidence": 0.95, "samples": samples}
    if len(values) == 1 or np.all(values == values[0]):
        mean = float(np.mean(values))
        return {"lower": mean, "upper": mean, "confidence": 0.95, "samples": samples}
    rng = np.random.default_rng(seed)
    means = np.empty(samples, dtype=np.float64)
    for index in range(samples):
        means[index] = float(np.mean(values[rng.integers(0, len(values), size=len(values))]))
    lower, upper = np.quantile(means, [0.025, 0.975])
    return {
        "lower": float(lower),
        "upper": float(upper),
        "confidence": 0.95,
        "samples": samples,
    }


def _paired_bootstrap_relative_gain(
    candidate_values: np.ndarray,
    baseline_values: np.ndarray,
    *,
    seed: int,
    samples: int = BOOTSTRAP_SAMPLES,
) -> dict[str, Any]:
    if len(candidate_values) != len(baseline_values):
        raise ValueError("Paired bootstrap inputs must contain the same queries")
    candidate_mean = float(np.mean(candidate_values)) if len(candidate_values) else 0.0
    baseline_mean = float(np.mean(baseline_values)) if len(baseline_values) else 0.0
    point = candidate_mean / baseline_mean - 1.0 if baseline_mean else None
    if not len(candidate_values) or not baseline_mean:
        return {
            "point_estimate": point,
            "lower": None,
            "upper": None,
            "confidence": 0.95,
            "samples": 0,
        }
    rng = np.random.default_rng(seed)
    gains: list[float] = []
    for _ in range(samples):
        indices = rng.integers(0, len(candidate_values), size=len(candidate_values))
        sampled_baseline = float(np.mean(baseline_values[indices]))
        if sampled_baseline:
            gains.append(float(np.mean(candidate_values[indices])) / sampled_baseline - 1.0)
    if not gains:
        lower = upper = None
    else:
        lower_value, upper_value = np.quantile(gains, [0.025, 0.975])
        lower, upper = float(lower_value), float(upper_value)
    return {
        "point_estimate": point,
        "lower": lower,
        "upper": upper,
        "confidence": 0.95,
        "samples": len(gains),
    }


def _evaluate(
    batch: QueryBatch, scores: np.ndarray, catalog_size: int, k: int = 10, *, seed: int = 42
) -> dict[str, Any]:
    ndcgs, recalls, reciprocal_ranks, recommended = _query_metrics(batch, scores, k)
    return {
        "queries": len(batch.groups),
        "target_queries": batch.target_query_count or len(batch.groups),
        "positive_labels": batch.positive_label_count,
        "ndcg_at_10": float(np.mean(ndcgs)) if len(ndcgs) else 0.0,
        "recall_at_10": float(np.mean(recalls)) if len(recalls) else 0.0,
        "mrr_at_10": float(np.mean(reciprocal_ranks)) if len(reciprocal_ranks) else 0.0,
        "query_distribution": {
            "ndcg_at_10_median": float(np.median(ndcgs)) if len(ndcgs) else 0.0,
            "recall_at_10_median": float(np.median(recalls)) if len(recalls) else 0.0,
            "mrr_at_10_median": (
                float(np.median(reciprocal_ranks)) if len(reciprocal_ranks) else 0.0
            ),
        },
        "confidence_intervals": {
            "ndcg_at_10": _bootstrap_mean_interval(ndcgs, seed=seed),
            "recall_at_10": _bootstrap_mean_interval(recalls, seed=seed + 1),
            "mrr_at_10": _bootstrap_mean_interval(reciprocal_ranks, seed=seed + 2),
        },
        "catalog_coverage_at_10": len(recommended) / catalog_size if catalog_size else 0.0,
        "unique_recommended_at_10": len(recommended),
        "candidate_recall_at_100": batch.candidate_recall_at_100,
        "candidate_recall_at_200": batch.candidate_recall,
        "candidate_eligible_recall_at_200": batch.candidate_eligible_recall_at_200,
        "candidate_query_coverage_at_100": batch.candidate_query_coverage_at_100,
        "candidate_query_coverage_at_200": batch.candidate_query_coverage_at_200,
        "candidate_catalog_coverage_at_200": (
            batch.unique_candidates_at_200 / catalog_size if catalog_size else 0.0
        ),
        "unique_candidates_at_200": batch.unique_candidates_at_200,
        "filtered_positive_labels": batch.filtered_positive_labels,
        "source_recall_at_200": batch.source_recall_at_200,
    }


def _slice_events(events: pd.DataFrame, start: pd.Timestamp | None, end: pd.Timestamp) -> pd.DataFrame:
    mask = events["event_time"] < end
    if start is not None:
        mask &= events["event_time"] >= start
    return events.loc[mask].copy()


def _phase(
    connection: duckdb.DuckDBPyConnection,
    settings: Settings,
    cohort: list[str],
    events: pd.DataFrame,
    cutoff: pd.Timestamp,
    target_end: pd.Timestamp,
    scaler: StandardScaler,
    kmeans: KMeans,
    embedding_index: CatalogEmbeddingIndex | None,
    *,
    training: bool,
) -> QueryBatch:
    user_features = _load_user_features(connection, settings.data_dir, cohort, cutoff)
    clusters, distances = _assign_clusters(user_features, scaler, kmeans)
    history = _slice_events(events, None, cutoff)
    target = _slice_events(events, cutoff, target_end)
    target = target[target["event_type"].isin(POSITIVE_EVENTS)]
    state = _candidate_state(history, cutoff, clusters, embedding_index)
    return _build_batch(
        state,
        _target_labels(target),
        user_features,
        clusters,
        distances,
        training=training,
    )


def _prepare_output(settings: Settings) -> Path:
    output = (settings.output_root / settings.version).resolve()
    root = settings.output_root.resolve()
    if root not in output.parents:
        raise ValueError("Model output must remain under the configured output root")
    if output.exists():
        if not settings.overwrite:
            raise FileExistsError(f"Output already exists: {output}; pass --overwrite explicitly")
        shutil.rmtree(output)
    output.mkdir(parents=True)
    return output


def _bundle_checksums(output: Path) -> dict[str, str]:
    files = sorted(path for path in output.iterdir() if path.is_file() and path.name != "checksum.sha256")
    checksums = {path.name: _sha256(path) for path in files}
    (output / "checksum.sha256").write_text(
        "".join(f"{digest}  {name}\n" for name, digest in checksums.items()), encoding="utf-8"
    )
    return checksums


def _build_baseline_serving_bundle(
    state: CandidateState,
    *,
    candidate_model_version: str,
    default_strategy: str,
) -> dict[str, Any]:
    product_ids = set(state.global_top) | set(state.recent_top)
    for products in state.category_top.values():
        product_ids.update(products)
    maximum_popularity = max(state.global_score.values(), default=1.0)
    products = [
        {
            "product_id": str(product_id),
            "category": str(state.item_category.get(product_id, -1)),
            "price_bucket": int(state.item_price.get(product_id, -1)),
            "popularity": float(state.global_score.get(product_id, 0.0) / maximum_popularity),
            "tags": [
                f"category:{state.item_category.get(product_id, -1)}",
                f"price:{state.item_price.get(product_id, -1)}",
            ],
        }
        for product_id in sorted(product_ids)
    ]
    user_affinities: dict[str, dict[str, float]] = {}
    for user, categories in state.user_categories.items():
        selected = categories.most_common(3)
        maximum = float(selected[0][1]) if selected else 1.0
        user_affinities[user] = {
            str(category): float(weight / maximum) for category, weight in selected
        }
    return {
        "schema_version": "recobridge-serving-v1",
        "model_version": f"baseline-{default_strategy}-{candidate_model_version}",
        "candidate_model_version": candidate_model_version,
        "feature_version": FEATURE_VERSION,
        "strategy_version": f"baseline-{default_strategy}-v1",
        "default_strategy": default_strategy,
        "ranker_promoted": False,
        "products": products,
        "user_affinities": user_affinities,
        "recently_bought": {
            user: [str(product_id) for product_id in sorted(product_ids)]
            for user, product_ids in state.user_recent_buys.items()
        },
        "rankings": {
            "recent_top": [str(product_id) for product_id in state.recent_top],
            "global_top": [str(product_id) for product_id in state.global_top],
            "category_top": {
                str(category): [str(product_id) for product_id in products]
                for category, products in state.category_top.items()
            },
        },
    }


def train(settings: Settings) -> dict[str, Any]:
    started = time.perf_counter()
    strategy_version = (
        EMBEDDING_STRATEGY_VERSION if settings.use_embedding_candidates else STRATEGY_VERSION
    )
    data_manifest, split = _validate_input(settings.data_dir, settings.profile)
    output = _prepare_output(settings)
    connection = duckdb.connect()
    try:
        cohort = _load_cohort(connection, settings.data_dir)
        events = _load_item_events(connection, settings.data_dir)
        catalog_path = (settings.data_dir / "catalog.parquet").as_posix().replace("'", "''")
        catalog_size = int(
            connection.execute(f"SELECT count(*) FROM read_parquet('{catalog_path}')").fetchone()[0]
        )
        embedding_index = (
            CatalogEmbeddingIndex.load(connection, settings.data_dir)
            if settings.use_embedding_candidates
            else None
        )
        train_end = _timestamp(split["train_end_exclusive"])
        validation_end = _timestamp(split["test_start_inclusive"])
        test_end = _timestamp(split["test_end_inclusive"]) + timedelta(microseconds=1)
        rank_train_cutoff = train_end - timedelta(days=14)

        cluster_users = _load_user_features(connection, settings.data_dir, cohort, rank_train_cutoff)
        scaler, kmeans, cluster_report = _fit_clusters(cluster_users, settings.seed)
        train_batch = _phase(
            connection,
            settings,
            cohort,
            events,
            rank_train_cutoff,
            train_end,
            scaler,
            kmeans,
            embedding_index,
            training=True,
        )
        if not train_batch.groups or float(np.max(train_batch.y, initial=0)) <= 0:
            raise RuntimeError("No train query contains a positive candidate")
        model = XGBRanker(
            objective="rank:ndcg",
            eval_metric="ndcg@10",
            n_estimators=150,
            learning_rate=0.06,
            max_depth=4,
            min_child_weight=5,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            random_state=settings.seed,
            tree_method="hist",
            n_jobs=max(1, (os.cpu_count() or 2) - 1),
        )
        model.fit(train_batch.x, train_batch.y, group=train_batch.groups, verbose=False)
        validation_batch = _phase(
            connection,
            settings,
            cohort,
            events,
            train_end,
            validation_end,
            scaler,
            kmeans,
            embedding_index,
            training=False,
        )
        test_batch = _phase(
            connection,
            settings,
            cohort,
            events,
            validation_end,
            test_end,
            scaler,
            kmeans,
            embedding_index,
            training=False,
        )
        serving_user_features = _load_user_features(
            connection, settings.data_dir, cohort, test_end
        )
        serving_clusters, _ = _assign_clusters(serving_user_features, scaler, kmeans)
        serving_state = _candidate_state(
            _slice_events(events, None, test_end), test_end, serving_clusters
        )
    finally:
        connection.close()

    strategies = ("global_popular", "recent_popular", "cluster_popular", "category_popular")
    baseline_scores: dict[str, dict[str, np.ndarray]] = {}
    baselines: dict[str, dict[str, Any]] = {}
    for strategy_index, strategy in enumerate(strategies):
        baseline_scores[strategy] = {
            "validation": _strategy_scores(validation_batch, strategy),
            "test": _strategy_scores(test_batch, strategy),
        }
        baselines[strategy] = {
            "validation": _evaluate(
                validation_batch,
                baseline_scores[strategy]["validation"],
                catalog_size,
                seed=settings.seed + strategy_index * 10,
            ),
            "test": _evaluate(
                test_batch,
                baseline_scores[strategy]["test"],
                catalog_size,
                seed=settings.seed + strategy_index * 10 + 1,
            ),
        }
    ranker_scores = {
        "validation": model.predict(validation_batch.x),
        "test": model.predict(test_batch.x),
    }
    ranker = {
        "validation": _evaluate(
            validation_batch, ranker_scores["validation"], catalog_size, seed=settings.seed + 100
        ),
        "test": _evaluate(
            test_batch, ranker_scores["test"], catalog_size, seed=settings.seed + 101
        ),
    }
    strongest = max(baselines, key=lambda name: baselines[name]["validation"]["ndcg_at_10"])
    baseline_validation = baselines[strongest]["validation"]
    baseline_test = baselines[strongest]["test"]
    relative_validation = (
        ranker["validation"]["ndcg_at_10"] / baseline_validation["ndcg_at_10"] - 1.0
        if baseline_validation["ndcg_at_10"]
        else 0.0
    )
    relative_test = (
        ranker["test"]["ndcg_at_10"] / baseline_test["ndcg_at_10"] - 1.0
        if baseline_test["ndcg_at_10"]
        else 0.0
    )
    coverage_ratio = (
        ranker["test"]["catalog_coverage_at_10"] / baseline_test["catalog_coverage_at_10"]
        if baseline_test["catalog_coverage_at_10"]
        else 0.0
    )
    validation_ranker_ndcg = _query_metrics(
        validation_batch, ranker_scores["validation"], 10
    )[0]
    validation_baseline_ndcg = _query_metrics(
        validation_batch, baseline_scores[strongest]["validation"], 10
    )[0]
    test_ranker_ndcg = _query_metrics(test_batch, ranker_scores["test"], 10)[0]
    test_baseline_ndcg = _query_metrics(
        test_batch, baseline_scores[strongest]["test"], 10
    )[0]
    paired_bootstrap = {
        "validation_ndcg_relative_gain": _paired_bootstrap_relative_gain(
            validation_ranker_ndcg,
            validation_baseline_ndcg,
            seed=settings.seed + 200,
        ),
        "test_ndcg_relative_gain": _paired_bootstrap_relative_gain(
            test_ranker_ndcg,
            test_baseline_ndcg,
            seed=settings.seed + 201,
        ),
    }
    gates = {
        "validation_ndcg_relative_gain_at_least_3pct": relative_validation >= 0.03,
        "test_ndcg_relative_loss_no_more_than_1pct": relative_test >= -0.01,
        "candidate_recall_at_200_at_least_0_70": ranker["test"]["candidate_recall_at_200"] >= 0.70,
        "catalog_coverage_at_least_90pct_of_baseline": coverage_ratio >= 0.90,
        "schema_and_checksum_valid": True,
        "api_p95_at_most_200ms": None,
    }
    promotion_eligible = all(value is True for value in gates.values())
    offline_pass = all(
        value is True for key, value in gates.items() if key != "api_p95_at_most_200ms"
    )
    metrics = {
        "model_version": settings.version,
        "feature_version": FEATURE_VERSION,
        "strategy_version": strategy_version,
        "profile": settings.profile,
        "candidate": {
            "train_recall_at_100": train_batch.candidate_recall_at_100,
            "train_recall_at_200": train_batch.candidate_recall,
            "train_eligible_recall_at_200": train_batch.candidate_eligible_recall_at_200,
            "train_query_coverage_at_100": train_batch.candidate_query_coverage_at_100,
            "train_query_coverage_at_200": train_batch.candidate_query_coverage_at_200,
            "train_source_recall_at_200": train_batch.source_recall_at_200,
            "train_unique_candidates_at_200": train_batch.unique_candidates_at_200,
            "train_filtered_positive_labels": train_batch.filtered_positive_labels,
            "train_target_queries": train_batch.target_query_count,
            "train_positive_labels": train_batch.positive_label_count,
            "train_queries": len(train_batch.groups),
            "train_queries_skipped_without_positive_candidate": train_batch.skipped_without_candidate_positive,
        },
        "baselines": baselines,
        "strongest_validation_baseline": strongest,
        "ranker": ranker,
        "comparison": {
            "validation_ndcg_relative_gain": relative_validation,
            "test_ndcg_relative_gain": relative_test,
            "test_coverage_ratio_vs_baseline": coverage_ratio,
            "paired_bootstrap_95pct": paired_bootstrap,
        },
        "promotion_gate": gates,
        "promotion_eligible": promotion_eligible,
        "promotion_note": (
            "All offline gates passed; API p95 still requires integration measurement."
            if offline_pass
            else "Candidate did not pass every offline promotion gate."
        ),
    }

    model.save_model(output / "xgb_model.json")
    joblib.dump(
        {
            "scaler": scaler,
            "kmeans": kmeans,
            "user_feature_names": USER_FEATURES,
            "feature_version": FEATURE_VERSION,
        },
        output / "kmeans_pipeline.joblib",
    )
    _write_json(
        output / "feature_schema.json",
        {
            "version": FEATURE_VERSION,
            "features": [
                {"name": name, "dtype": "float32", "position": position}
                for position, name in enumerate(RANKING_FEATURES)
            ],
            "label": {"0": "unobserved candidate", "1": "add to cart", "2": "buy"},
            "cutoff_safe": True,
        },
    )
    _write_json(
        output / "candidate_config.json",
        {
            "version": strategy_version,
            "recent_popular": 60,
            "cluster_popular": 60,
            "category_affinity": 60,
            "item_similarity": 40,
            "item_similarity_sources": (
                ["quantized_embedding_l1", "history_cooccurrence"]
                if settings.use_embedding_candidates
                else ["history_cooccurrence"]
            ),
            "embedding_index": {
                "enabled": settings.use_embedding_candidates,
                "metric": "manhattan_l1",
                "approximation_epsilon": 0.1,
                "neighbors_per_seed": 8,
                "seed_items_per_user": 5,
                "encoding_limitation": (
                    "Quantized codes are treated as ordinal only for retrieval; release evidence must "
                    "compare candidate recall against the no-embedding ablation."
                ),
            },
            "maximum_after_dedup": 200,
            "refill": "global_popular",
            "recent_window_days": 14,
            "recently_bought_filter": "buys in the 14 days before cutoff",
            "candidate_metrics": [
                "recall_at_100",
                "recall_at_200",
                "query_coverage_at_100",
                "query_coverage_at_200",
                "catalog_coverage_at_200",
                "source_recall_at_200",
            ],
        },
    )
    _write_json(output / "baseline_report.json", baselines)
    _write_json(output / "cluster_report.json", cluster_report)
    _write_json(output / "metrics.json", metrics)
    serving_bundle = _build_baseline_serving_bundle(
        serving_state,
        candidate_model_version=settings.version,
        default_strategy=strongest,
    )
    _write_json(output / "serving_bundle.json", serving_bundle)
    release_decision = {
        "candidate_model_version": settings.version,
        "ranker_status": (
            "offline_pass_awaiting_api_latency" if offline_pass else "rejected_by_offline_gate"
        ),
        "ranker_promotion_eligible": promotion_eligible,
        "default_strategy": strongest,
        "serving_model_version": serving_bundle["model_version"],
        "release_status": "baseline_fallback_pending_api_latency",
        "failed_ranker_gates": [key for key, value in gates.items() if value is False],
        "pending_gates": [key for key, value in gates.items() if value is None],
        "policy": (
            "Serve the strongest validation baseline until the ranker passes every promotion gate."
        ),
    }
    _write_json(output / "release_decision.json", release_decision)
    project_root = Path(__file__).resolve().parents[3]
    manifest = {
        "model_version": settings.version,
        "status": "candidate",
        "promotion_eligible": promotion_eligible,
        "recommended_default_strategy": strongest,
        "serving_model_version": serving_bundle["model_version"],
        "profile": settings.profile,
        "data_version": data_manifest["data_version"],
        "data_manifest_sha256": _sha256(settings.data_dir / "data_manifest.json"),
        "training_cutoff": rank_train_cutoff,
        "validation_cutoff": train_end,
        "test_cutoff": validation_end,
        "feature_version": FEATURE_VERSION,
        "strategy_version": strategy_version,
        "git_commit": _git_commit(project_root),
        "seed": settings.seed,
        "created_at": datetime.now(UTC),
        "duration_seconds": round(time.perf_counter() - started, 3),
        "compatibility": {"python": ">=3.12,<3.14", "recobridge_api": ">=0.1,<0.2"},
        "libraries": {
            "python": platform.python_version(),
            "duckdb": duckdb.__version__,
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scikit_learn": sklearn.__version__,
            "xgboost": xgboost.__version__,
            "joblib": joblib.__version__,
            "scipy": scipy.__version__,
        },
        "training": {
            "objective": "rank:ndcg",
            "qid": "user_id + cutoff",
            "feature_count": len(RANKING_FEATURES),
            "queries": len(train_batch.groups),
            "rows": int(len(train_batch.y)),
            "hyperparameters": model.get_params(),
            "embedding_candidates": settings.use_embedding_candidates,
        },
    }
    _write_json(output / "manifest.json", manifest)
    checksums = _bundle_checksums(output)
    latest = {
        "model_version": settings.version,
        "path": settings.version,
        "status": "candidate",
        "promotion_eligible": promotion_eligible,
        "manifest_sha256": checksums["manifest.json"],
        "updated_at": datetime.now(UTC),
    }
    _write_json(settings.output_root / "latest.json", latest)
    return {"output": output, "manifest": manifest, "metrics": metrics, "checksums": checksums}


def _default_version(profile: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"xgb-{stamp}-{profile}"


def main(argv: list[str] | None = None) -> None:
    ml_root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("smoke", "release"), default="smoke")
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--version")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--enable-embedding-candidates", action="store_true")
    args = parser.parse_args(argv)
    settings = Settings(
        data_dir=(args.data_dir or ml_root / "artifacts" / "data" / args.profile).resolve(),
        output_root=(args.output_root or ml_root / "artifacts" / "models" / args.profile).resolve(),
        profile=args.profile,
        seed=args.seed,
        version=args.version or _default_version(args.profile),
        overwrite=args.overwrite,
        use_embedding_candidates=args.enable_embedding_candidates,
    )
    result = train(settings)
    metrics = result["metrics"]
    print(
        json.dumps(
            {
                "model_version": settings.version,
                "output": str(result["output"]),
                "strongest_baseline": metrics["strongest_validation_baseline"],
                "validation_ndcg_at_10": metrics["ranker"]["validation"]["ndcg_at_10"],
                "test_ndcg_at_10": metrics["ranker"]["test"]["ndcg_at_10"],
                "candidate_recall_at_200": metrics["ranker"]["test"]["candidate_recall_at_200"],
                "promotion_eligible": metrics["promotion_eligible"],
            },
            indent=2,
            default=_json_default,
        )
    )


if __name__ == "__main__":
    main(sys.argv[1:])
