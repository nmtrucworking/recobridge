from collections import Counter

import numpy as np
import pandas as pd
import pytest
from scipy.spatial import cKDTree

from recobridge_ml.train import (
    RANKING_FEATURES,
    USER_FEATURES,
    CatalogEmbeddingIndex,
    CandidateState,
    QueryBatch,
    _build_batch,
    _candidates_for_user,
    _evaluate,
    _paired_bootstrap_relative_gain,
    _query_metrics,
)


def _state() -> CandidateState:
    return CandidateState(
        global_top=[11, 12, 13],
        recent_top=[],
        global_score={11: 3.0, 12: 2.0, 13: 1.0},
        recent_score={},
        cluster_top={},
        cluster_score={},
        category_top={},
        category_score={},
        user_categories={"u1": Counter()},
        user_items={"u1": {11: Counter({"BUY": 1}), 12: Counter({"BUY": 1})}},
        user_recent_items={"u1": [12, 11]},
        user_recent_buys={"u1": {12}},
        user_last_category={"u1": 7},
        user_mean_price={"u1": 2.0},
        item_category={11: 7, 12: 7, 13: 8},
        item_price={11: 2, 12: 2, 13: 1},
        item_neighbors={},
    )


def test_candidate_filter_removes_only_recently_bought_items() -> None:
    products, _ = _candidates_for_user("u1", _state(), cluster=0)

    assert 12 not in products
    assert 11 in products
    assert 13 in products


def test_evaluation_uses_target_labels_and_candidate_order() -> None:
    batch = QueryBatch(
        x=np.zeros((2, len(RANKING_FEATURES)), dtype=np.float32),
        y=np.asarray([0, 2], dtype=np.float32),
        groups=[2],
        users=["u1"],
        product_ids=[np.asarray([1, 2], dtype=np.int64)],
        target_labels=[{2: 2}],
        candidate_recall=1.0,
        skipped_without_candidate_positive=0,
    )

    metrics = _evaluate(batch, np.asarray([0.0, 1.0]), catalog_size=10)

    assert metrics["ndcg_at_10"] == 1.0
    assert metrics["recall_at_10"] == 1.0
    assert metrics["mrr_at_10"] == 1.0
    assert metrics["candidate_recall_at_200"] == 1.0
    assert metrics["confidence_intervals"]["ndcg_at_10"]["lower"] == 1.0
    assert metrics["confidence_intervals"]["ndcg_at_10"]["upper"] == 1.0


def test_candidate_diagnostics_respect_recent_purchase_filter() -> None:
    features = pd.DataFrame([{"user_id": "u1", **{name: 0.0 for name in USER_FEATURES}}])

    batch = _build_batch(
        _state(),
        {"u1": {11: 2, 12: 2, 13: 1}},
        features,
        {"u1": 0},
        {"u1": 0.25},
        training=False,
    )

    assert batch.candidate_recall == pytest.approx(2 / 3)
    assert batch.candidate_eligible_recall_at_200 == 1.0
    assert batch.filtered_positive_labels == 1
    assert batch.candidate_query_coverage_at_100 == 1.0
    assert batch.source_recall_at_200["global"] == pytest.approx(2 / 3)


def test_paired_bootstrap_reports_deterministic_gain() -> None:
    comparison = _paired_bootstrap_relative_gain(
        np.asarray([1.0, 1.0]),
        np.asarray([0.5, 0.5]),
        seed=42,
        samples=100,
    )

    assert comparison["point_estimate"] == 1.0
    assert comparison["lower"] == 1.0
    assert comparison["upper"] == 1.0
    assert comparison["samples"] == 100


def test_query_metrics_reject_score_length_mismatch() -> None:
    batch = QueryBatch(
        x=np.zeros((2, len(RANKING_FEATURES)), dtype=np.float32),
        y=np.asarray([0, 2], dtype=np.float32),
        groups=[2],
        users=["u1"],
        product_ids=[np.asarray([1, 2], dtype=np.int64)],
        target_labels=[{2: 2}],
        candidate_recall=1.0,
        skipped_without_candidate_positive=0,
    )

    with pytest.raises(ValueError, match="Expected 2 scores"):
        _query_metrics(batch, np.asarray([1.0]), 10)


def test_embedding_index_returns_nearest_products_and_excludes_seed() -> None:
    product_ids = np.asarray([10, 20, 30, 40], dtype=np.int64)
    vectors = np.asarray(
        [[0.0, 0.0], [1.0, 1.0], [20.0, 20.0], [2.0, 2.0]], dtype=np.float32
    )
    index = CatalogEmbeddingIndex(product_ids, vectors, cKDTree(vectors))

    neighbors = index.resolve([10], k=2)

    assert neighbors[10] == [20, 40]
    assert 10 not in neighbors[10]
