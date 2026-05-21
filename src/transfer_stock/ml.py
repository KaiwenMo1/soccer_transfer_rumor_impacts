from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, pstdev

from .io import ensure_parent, read_csv, write_csv


FEATURES = [
    "transfer_indicator",
    "rumor_indicator",
    "stock_context_indicator",
    "fee_to_market",
    "pre_stock_return_7d",
    "pre_stock_return_30d",
    "pre_stock_volatility_30d",
    "pre_market_return_30d",
    "transfer_quality",
    "rumor_count",
    "source_diversity",
    "max_credibility",
    "avg_credibility",
    "max_rumor_strength",
    "avg_rumor_strength",
    "direction",
    "transfer_type",
    "is_loan",
    "club",
]

NUMERIC_FEATURES = [
    "transfer_indicator",
    "rumor_indicator",
    "stock_context_indicator",
    "fee_to_market",
    "pre_stock_return_7d",
    "pre_stock_return_30d",
    "pre_stock_volatility_30d",
    "pre_market_return_30d",
    "transfer_quality",
    "rumor_count",
    "source_diversity",
    "max_credibility",
    "avg_credibility",
    "max_rumor_strength",
    "avg_rumor_strength",
    "is_loan",
]

CATEGORICAL_FEATURES = ["direction", "transfer_type", "club"]


def season_start(season: str) -> int:
    left = season.split("-", 1)[0]
    return int(left) if left.isdigit() else 0


def parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def usable_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if row.get("label") and row.get("car_m1_p1") not in {"", None}]


def temporal_split(rows: list[dict[str, str]], train_end_season: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    train_end = season_start(train_end_season)
    train = [row for row in rows if season_start(row.get("season", "")) <= train_end]
    test = [row for row in rows if season_start(row.get("season", "")) > train_end]
    return train, test


def fit_model(rows: list[dict[str, str]]) -> dict[str, object]:
    labels = sorted({row["label"] for row in rows})
    priors = Counter(row["label"] for row in rows)
    numeric_stats: dict[str, dict[str, tuple[float, float]]] = {}
    categorical_counts: dict[str, dict[str, Counter[str]]] = {}
    categorical_vocab: dict[str, set[str]] = {feature: set() for feature in CATEGORICAL_FEATURES}

    for feature in CATEGORICAL_FEATURES:
        for row in rows:
            categorical_vocab[feature].add(row.get(feature, ""))

    for label in labels:
        label_rows = [row for row in rows if row["label"] == label]
        numeric_stats[label] = {}
        for feature in NUMERIC_FEATURES:
            values = [parse_float(row.get(feature)) for row in label_rows]
            sigma = pstdev(values) if len(values) > 1 else 1.0
            numeric_stats[label][feature] = (mean(values), max(sigma, 1e-4))
        categorical_counts[label] = {}
        for feature in CATEGORICAL_FEATURES:
            categorical_counts[label][feature] = Counter(row.get(feature, "") for row in label_rows)

    serializable_categorical_counts = {
        label: {feature: dict(counts) for feature, counts in feature_counts.items()}
        for label, feature_counts in categorical_counts.items()
    }
    return {
        "labels": labels,
        "class_counts": dict(priors),
        "numeric_stats": numeric_stats,
        "categorical_counts": serializable_categorical_counts,
        "categorical_vocab": {key: sorted(value) for key, value in categorical_vocab.items()},
        "n_train": len(rows),
    }


def log_normal_pdf(value: float, mu: float, sigma: float) -> float:
    variance = sigma * sigma
    return -0.5 * math.log(2 * math.pi * variance) - ((value - mu) ** 2) / (2 * variance)


def predict_one(model: dict[str, object], row: dict[str, str]) -> tuple[str, float, dict[str, float]]:
    labels = list(model["labels"])  # type: ignore[index]
    class_counts = model["class_counts"]  # type: ignore[index]
    numeric_stats = model["numeric_stats"]  # type: ignore[index]
    categorical_counts = model["categorical_counts"]  # type: ignore[index]
    categorical_vocab = model["categorical_vocab"]  # type: ignore[index]
    total = sum(class_counts.values())
    scores: dict[str, float] = {}
    for label in labels:
        score = math.log((class_counts[label] + 1) / (total + len(labels)))
        for feature in NUMERIC_FEATURES:
            mu, sigma = numeric_stats[label][feature]
            score += log_normal_pdf(parse_float(row.get(feature)), mu, sigma)
        for feature in CATEGORICAL_FEATURES:
            counts = categorical_counts[label][feature]
            vocab_size = max(len(categorical_vocab[feature]), 1)
            score += math.log((counts.get(row.get(feature, ""), 0) + 1) / (class_counts[label] + vocab_size))
        scores[label] = score

    max_score = max(scores.values())
    exp_scores = {label: math.exp(score - max_score) for label, score in scores.items()}
    denominator = sum(exp_scores.values())
    probabilities = {label: value / denominator for label, value in exp_scores.items()}
    predicted = max(probabilities, key=probabilities.get)
    return predicted, probabilities[predicted], probabilities


def evaluate(predictions: list[dict[str, object]]) -> dict[str, object]:
    if not predictions:
        return {"n": 0, "accuracy": None, "label_counts": {}, "predicted_counts": {}}
    correct = sum(1 for row in predictions if row["actual_label"] == row["predicted_label"])
    return {
        "n": len(predictions),
        "accuracy": round(correct / len(predictions), 4),
        "label_counts": dict(Counter(str(row["actual_label"]) for row in predictions)),
        "predicted_counts": dict(Counter(str(row["predicted_label"]) for row in predictions)),
    }


def fit_knn(rows: list[dict[str, str]], k: int = 1) -> dict[str, object]:
    ranges: dict[str, tuple[float, float]] = {}
    for feature in NUMERIC_FEATURES:
        values = [parse_float(row.get(feature)) for row in rows]
        low = min(values) if values else 0.0
        high = max(values) if values else 1.0
        if high == low:
            high = low + 1.0
        ranges[feature] = (low, high)
    return {"rows": rows, "ranges": ranges, "k": k, "n_train": len(rows)}


def knn_distance(model: dict[str, object], left: dict[str, str], right: dict[str, str]) -> float:
    ranges = model["ranges"]  # type: ignore[index]
    total = 0.0
    for feature in NUMERIC_FEATURES:
        low, high = ranges[feature]
        left_value = (parse_float(left.get(feature)) - low) / (high - low)
        right_value = (parse_float(right.get(feature)) - low) / (high - low)
        total += (left_value - right_value) ** 2
    for feature in CATEGORICAL_FEATURES:
        total += 0.0 if left.get(feature, "") == right.get(feature, "") else 1.0
    return math.sqrt(total)


def predict_one_knn(model: dict[str, object], row: dict[str, str]) -> tuple[str, float, dict[str, float]]:
    train_rows = model["rows"]  # type: ignore[index]
    k = int(model["k"])  # type: ignore[index]
    neighbors = sorted(train_rows, key=lambda train_row: knn_distance(model, row, train_row))[:k]
    votes = Counter(neighbor["label"] for neighbor in neighbors)
    predicted, count = votes.most_common(1)[0]
    labels = sorted({train_row["label"] for train_row in train_rows})
    probabilities = {label: votes.get(label, 0) / max(len(neighbors), 1) for label in labels}
    return predicted, count / max(len(neighbors), 1), probabilities


def train_and_predict(
    model_dataset: Path,
    predictions_path: Path,
    metrics_path: Path,
    train_end_season: str = "2024-25",
    model_type: str = "nb",
    k: int = 1,
) -> dict[str, object]:
    all_rows = read_csv(model_dataset)
    labeled_rows = usable_rows(all_rows)
    train_rows, test_rows = temporal_split(labeled_rows, train_end_season)
    if not train_rows:
        raise ValueError("No labeled training rows available")
    if model_type == "nb":
        model = fit_model(train_rows)
        predict = predict_one
    elif model_type == "knn":
        model = fit_knn(train_rows, k=k)
        predict = predict_one_knn
    else:
        raise ValueError(f"Unsupported model type: {model_type}")
    prediction_rows: list[dict[str, object]] = []
    train_end = season_start(train_end_season)
    for row in all_rows:
        row_season = season_start(row.get("season", ""))
        is_labeled = row.get("label") and row.get("car_m1_p1") not in {"", None}
        if is_labeled and row_season <= train_end:
            split = "train"
        elif is_labeled and row_season > train_end:
            split = "test"
        elif row_season > train_end:
            split = "live_unlabeled"
        else:
            split = "unlabeled"
        predicted, confidence, probabilities = predict(model, row)
        prediction_rows.append(
            {
                **row,
                "split": split,
                "actual_label": row.get("label", ""),
                "predicted_label": predicted,
                "prediction_confidence": round(confidence, 4),
                "prob_negative": round(probabilities.get("negative", 0.0), 4),
                "prob_neutral": round(probabilities.get("neutral", 0.0), 4),
                "prob_positive": round(probabilities.get("positive", 0.0), 4),
            }
        )

    fields = list(prediction_rows[0].keys()) if prediction_rows else []
    write_csv(predictions_path, prediction_rows, fields)
    metrics = {
        "train_end_season": train_end_season,
        "model_type": model_type,
        "k": k if model_type == "knn" else None,
        "features": FEATURES,
        "train": evaluate([row for row in prediction_rows if row["split"] == "train"]),
        "test": evaluate([row for row in prediction_rows if row["split"] == "test"]),
        "live_unlabeled_count": sum(1 for row in prediction_rows if row["split"] == "live_unlabeled"),
        "unlabeled_count": sum(1 for row in prediction_rows if row["split"] == "unlabeled"),
        "model": model,
        "warning": "Small/noisy dataset; proxy dates and sparse rumor coverage can dominate results.",
    }
    ensure_parent(metrics_path)
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    return metrics
