from __future__ import annotations

import json
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from statistics import mean
from typing import Any

from .features import transfer_quality_score
from .indicators import fee_to_market, market_minus_fee, transfer_indicator
from .io import ensure_parent, read_csv, write_csv
from .market_features import build_market_features
from .matching import transfer_id_for
from .targets import TARGET_FIELDS, direct_target_rows
from .transfers import Transfer, load_transfers


BASE_DATASET_FIELDS = [
    "claim_id",
    "article_id",
    "published_at",
    "date",
    "published_date",
    "source",
    "journalist",
    "club",
    "subject_club",
    "player",
    "season",
    "direction",
    "subject_direction",
    "transfer_type",
    "is_loan",
    "age",
    "position",
    "market_value_eur",
    "transfer_fee_eur",
    "wage_eur_annual",
    "fee_to_market",
    "market_minus_fee_eur",
    "transfer_quality",
    "transfer_indicator",
    "rumor_strength",
    "rumor_indicator",
    "credibility_score",
    "source_reputation_score",
    "journalist_reputation_score",
    "historical_conversion_score",
    "club_specific_score",
    "rumor_stage_score",
    "article_type_score",
    "time_to_confirmation_score",
    "historical_support_n",
    "match_score",
    "ambiguity_flag",
    "entity_match_indicator",
    "rumor_stage",
    "article_type",
    "source_diversity",
    "rumor_count",
    "max_credibility",
    "avg_credibility",
    "max_rumor_strength",
    "avg_rumor_strength",
    *TARGET_FIELDS,
    "label",
]

NUMERIC_FEATURES = [
    "credibility_score",
    "source_reputation_score",
    "journalist_reputation_score",
    "historical_conversion_score",
    "club_specific_score",
    "rumor_stage_score",
    "article_type_score",
    "time_to_confirmation_score",
    "historical_support_n",
    "match_score",
    "ambiguity_flag",
    "entity_match_indicator",
    "transfer_quality",
    "transfer_indicator",
    "fee_to_market",
    "market_minus_fee_eur",
    "market_value_eur",
    "transfer_fee_eur",
    "wage_eur_annual",
    "age",
    "is_loan",
    "rumor_strength",
    "rumor_indicator",
    "rumor_count",
    "source_diversity",
    "max_credibility",
    "avg_credibility",
    "max_rumor_strength",
    "avg_rumor_strength",
    "public_target_count",
    "has_public_buyer",
    "has_public_seller",
    "pre_stock_return_7d",
    "pre_stock_return_30d",
    "pre_stock_volatility_30d",
    "pre_market_return_30d",
    "stock_context_indicator",
    "event_trading_offset_days",
    "estimation_points",
    "pre_window_ok_30d",
    "pre_raw_return_m1",
    "pre_raw_return_m3",
    "pre_raw_return_m5",
    "pre_raw_return_m10",
    "pre_raw_return_m20",
    "pre_raw_return_m30",
    "pre_market_return_m1",
    "pre_market_return_m3",
    "pre_market_return_m5",
    "pre_market_return_m10",
    "pre_market_return_m20",
    "pre_market_return_m30",
    "pre_abnormal_return_m1",
    "pre_abnormal_return_m3",
    "pre_abnormal_return_m5",
    "pre_abnormal_return_m10",
    "pre_volatility_20d",
    "pre_close_zscore_20d",
    "pre_volume_zscore_20d",
    "relative_volume_20d",
]

CORE_NUMERIC_FEATURES = [
    "credibility_score",
    "source_reputation_score",
    "journalist_reputation_score",
    "historical_conversion_score",
    "club_specific_score",
    "rumor_stage_score",
    "article_type_score",
    "time_to_confirmation_score",
    "historical_support_n",
    "match_score",
    "ambiguity_flag",
    "entity_match_indicator",
    "transfer_quality",
    "transfer_indicator",
    "fee_to_market",
    "market_minus_fee_eur",
    "market_value_eur",
    "transfer_fee_eur",
    "wage_eur_annual",
    "age",
    "is_loan",
    "rumor_strength",
    "rumor_indicator",
    "public_target_count",
    "has_public_buyer",
    "has_public_seller",
    "pre_stock_return_7d",
    "pre_stock_return_30d",
    "pre_stock_volatility_30d",
    "pre_market_return_30d",
    "stock_context_indicator",
    "event_trading_offset_days",
    "estimation_points",
    "pre_window_ok_30d",
    "pre_raw_return_m3",
    "pre_raw_return_m10",
    "pre_raw_return_m20",
    "pre_market_return_m3",
    "pre_market_return_m10",
    "pre_market_return_m20",
    "pre_abnormal_return_m3",
    "pre_abnormal_return_m10",
    "pre_volatility_20d",
    "pre_close_zscore_20d",
    "pre_volume_zscore_20d",
    "relative_volume_20d",
]

CATEGORICAL_FEATURES = [
    "club",
    "direction",
    "transfer_type",
    "position",
    "rumor_stage",
    "article_type",
    "target_role",
    "target_entity_type",
]

LEAKY_FIELDS = {
    "raw_return_0_p1",
    "raw_return_0_p3",
    "raw_return_0_p5",
    "raw_return_0_p10",
    "market_return_0_p1",
    "market_return_0_p3",
    "market_return_0_p5",
    "market_return_0_p10",
    "abnormal_return_0_p1",
    "abnormal_return_0_p3",
    "abnormal_return_0_p5",
    "abnormal_return_0_p10",
    "post_volatility_20d",
    "volatility_shift_20d",
    "event_close_zscore_20d",
    "event_volume_zscore_20d",
    "target_abnormal_return_p3",
    "target_label_p3",
    "label",
}

LABELS = ["negative", "neutral", "positive"]


def import_ml_dependencies() -> dict[str, Any]:
    try:
        from sklearn.feature_extraction import DictVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, log_loss
        from sklearn.preprocessing import StandardScaler
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Stage 6 requires scikit-learn. Install it with: pip install -e '.[ml_pipeline]'"
        ) from exc
    try:
        from xgboost import XGBClassifier
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Stage 6 requires xgboost. Install it with: pip install -e '.[ml_pipeline]'"
        ) from exc
    return {
        "DictVectorizer": DictVectorizer,
        "LogisticRegression": LogisticRegression,
        "accuracy_score": accuracy_score,
        "confusion_matrix": confusion_matrix,
        "f1_score": f1_score,
        "log_loss": log_loss,
        "StandardScaler": StandardScaler,
        "XGBClassifier": XGBClassifier,
    }


def parse_float(value: Any, default: float = 0.0) -> float:
    if value in {"", None}:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_int(value: Any, default: int = 0) -> int:
    if value in {"", None}:
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def parse_datetime_to_date(value: str) -> date | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z") and "-" in text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    for fmt in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    if len(text) >= 10:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None
    return None


def season_start(season: str) -> int:
    left = season.split("-", 1)[0]
    return int(left) if left.isdigit() else 0


def transfer_index(transfers_path: Path) -> dict[str, Transfer]:
    return {transfer_id_for(transfer): transfer for transfer in load_transfers(transfers_path)}


def rumor_indicator_from_components(row: dict[str, str]) -> float:
    return round(
        clamp(
            0.40 * parse_float(row.get("credibility_score"), 0.5)
            + 0.20 * parse_float(row.get("historical_conversion_score"), 0.5)
            + 0.20 * parse_float(row.get("rumor_stage_score"), 0.4)
            + 0.10 * parse_float(row.get("article_type_score"), 0.5)
            + 0.10 * parse_float(row.get("time_to_confirmation_score"), 0.5)
        ),
        4,
    )


def entity_match_indicator(row: dict[str, str]) -> float:
    score = parse_float(row.get("match_score"), 0.0)
    ambiguity = parse_int(row.get("ambiguity_flag"), 0)
    return round(clamp(score / 1.2) * (0.85 if ambiguity else 1.0), 4)


def transfer_row(transfer: Transfer) -> dict[str, str]:
    return {
        "date": transfer.date.isoformat(),
        "club": transfer.club,
        "player": transfer.player,
        "direction": transfer.direction,
        "age": "" if transfer.age is None else str(transfer.age),
        "position": transfer.position,
        "market_value_eur": "" if transfer.market_value_eur is None else str(transfer.market_value_eur),
        "transfer_fee_eur": "" if transfer.transfer_fee_eur is None else str(transfer.transfer_fee_eur),
        "wage_eur_annual": "" if transfer.wage_eur_annual is None else str(transfer.wage_eur_annual),
        "transfer_type": transfer.transfer_type,
        "is_loan": "1" if transfer.is_loan else "0",
        "season": transfer.season,
    }


def claim_season_from_date(claim: dict[str, str]) -> str:
    published_date = parse_datetime_to_date(claim.get("published_at", ""))
    if published_date is None:
        return ""
    year = published_date.year
    if published_date.month >= 7:
        return f"{year}-{str(year + 1)[-2:]}"
    return f"{year - 1}-{str(year)[-2:]}"


def base_claim_features(claim: dict[str, str]) -> dict[str, object]:
    rumor_ind = rumor_indicator_from_components(claim)
    return {
        "claim_id": claim.get("claim_id", ""),
        "article_id": claim.get("article_id", ""),
        "published_at": claim.get("published_at", ""),
        "source": claim.get("source", ""),
        "journalist": claim.get("journalist", ""),
        "credibility_score": parse_float(claim.get("credibility_score"), 0.0),
        "source_reputation_score": parse_float(claim.get("source_reputation_score"), 0.0),
        "journalist_reputation_score": parse_float(claim.get("journalist_reputation_score"), 0.0),
        "historical_conversion_score": parse_float(claim.get("historical_conversion_score"), 0.0),
        "club_specific_score": parse_float(claim.get("club_specific_score"), 0.0),
        "rumor_stage_score": parse_float(claim.get("rumor_stage_score"), 0.0),
        "article_type_score": parse_float(claim.get("article_type_score"), 0.0),
        "time_to_confirmation_score": parse_float(claim.get("time_to_confirmation_score"), 0.0),
        "historical_support_n": parse_int(claim.get("historical_support_n"), 0),
        "match_score": parse_float(claim.get("match_score"), 0.0),
        "ambiguity_flag": parse_int(claim.get("ambiguity_flag"), 0),
        "entity_match_indicator": entity_match_indicator(claim),
        "rumor_stage": claim.get("rumor_stage", "unclear"),
        "article_type": claim.get("article_type", "report"),
        "source_diversity": 1,
        "rumor_count": 1,
        "max_credibility": parse_float(claim.get("credibility_score"), 0.0),
        "avg_credibility": parse_float(claim.get("credibility_score"), 0.0),
        "label": "",
        "rumor_indicator": rumor_ind,
        "rumor_strength": rumor_ind,
        "max_rumor_strength": rumor_ind,
        "avg_rumor_strength": rumor_ind,
    }


def unmatched_claim_row(claim: dict[str, str], published_date: date) -> dict[str, object]:
    base_row = {
        **base_claim_features(claim),
        "date": published_date.isoformat(),
        "published_date": published_date.isoformat(),
        "club": claim.get("primary_club", ""),
        "subject_club": claim.get("primary_club", ""),
        "player": claim.get("primary_player", ""),
        "season": claim_season_from_date(claim),
        "direction": claim.get("transfer_direction", "unclear"),
        "subject_direction": claim.get("transfer_direction", "unclear"),
        "transfer_type": "unclear",
        "is_loan": 0,
        "age": "",
        "position": "",
        "market_value_eur": "",
        "transfer_fee_eur": "",
        "wage_eur_annual": "",
        "fee_to_market": 0.0,
        "market_minus_fee_eur": 0.0,
        "transfer_quality": 0.0,
        "transfer_indicator": 0.0,
        "buyer_club": "",
        "seller_club": "",
        "target_club": "",
        "target_role": "",
        "target_direction": "",
        "target_entity_type": "",
        "target_ticker": "",
        "target_market_symbol": "",
        "prediction_scope": "none",
        "public_target_count": 0,
        "has_public_buyer": 0,
        "has_public_seller": 0,
    }
    return base_row


def claim_dataset_rows(
    scored_claim_paths: list[Path],
    transfers_path: Path,
    clubs: dict[str, Any],
) -> list[dict[str, object]]:
    transfers_by_id = transfer_index(transfers_path)
    rows: list[dict[str, object]] = []
    for scored_path in scored_claim_paths:
        for claim in read_csv(scored_path):
            if not parse_bool(claim.get("is_transfer_related")):
                continue
            published_date = parse_datetime_to_date(claim.get("published_at", ""))
            if published_date is None:
                continue
            matched_transfer_id = claim.get("matched_transfer_id", "")
            if not matched_transfer_id:
                rows.append(unmatched_claim_row(claim, published_date))
                continue
            transfer = transfers_by_id.get(matched_transfer_id)
            if transfer is None:
                rows.append(unmatched_claim_row(claim, published_date))
                continue
            transfer_fields = transfer_row(transfer)
            base_row = {
                **base_claim_features(claim),
                "date": published_date.isoformat(),
                "published_date": published_date.isoformat(),
                "club": transfer.club,
                "subject_club": transfer.club,
                "player": transfer.player,
                "season": transfer.season,
                "direction": transfer.direction,
                "subject_direction": transfer.direction,
                "transfer_type": transfer.transfer_type,
                "is_loan": int(transfer.is_loan),
                "age": "" if transfer.age is None else transfer.age,
                "position": transfer.position,
                "market_value_eur": "" if transfer.market_value_eur is None else transfer.market_value_eur,
                "transfer_fee_eur": "" if transfer.transfer_fee_eur is None else transfer.transfer_fee_eur,
                "wage_eur_annual": "" if transfer.wage_eur_annual is None else transfer.wage_eur_annual,
                "fee_to_market": fee_to_market(transfer_fields),
                "market_minus_fee_eur": market_minus_fee(transfer_fields),
                "transfer_quality": transfer_quality_score(transfer),
                "transfer_indicator": transfer_indicator(transfer_fields),
            }
            rows.extend(direct_target_rows(base_row, transfer, clubs))
    return rows


def build_stage6_dataset(
    scored_claim_paths: list[Path],
    transfers_path: Path,
    base_output_path: Path,
    market_output_path: Path,
    clubs: dict[str, Any],
) -> list[dict[str, object]]:
    base_rows = claim_dataset_rows(scored_claim_paths, transfers_path, clubs)
    write_csv(base_output_path, base_rows, BASE_DATASET_FIELDS)
    return build_market_features(base_output_path, market_output_path, clubs)


def active_numeric_features(rows: list[dict[str, str]], preset: str = "full") -> list[str]:
    source = NUMERIC_FEATURES if preset == "full" else CORE_NUMERIC_FEATURES
    return [feature for feature in source if feature not in LEAKY_FIELDS and any(feature in row for row in rows)]


def active_categorical_features(rows: list[dict[str, str]]) -> list[str]:
    return [feature for feature in CATEGORICAL_FEATURES if feature not in LEAKY_FIELDS and any(feature in row for row in rows)]


def usable_rows(rows: list[dict[str, str]], target_label_field: str = "target_label_p3") -> list[dict[str, str]]:
    usable: list[dict[str, str]] = []
    for row in rows:
        if row.get("prediction_scope", "direct") != "direct":
            continue
        if row.get("market_feature_status") not in {"ok", "limited_history"}:
            continue
        if row.get(target_label_field) not in LABELS:
            continue
        usable.append(row)
    return usable


def temporal_split(rows: list[dict[str, str]], train_end_season: str) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    train_end = season_start(train_end_season)
    train = [row for row in rows if season_start(row.get("season", "")) <= train_end]
    test = [row for row in rows if season_start(row.get("season", "")) > train_end]
    return train, test


def sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(rows, key=lambda row: (row.get("published_date", row.get("date", "")), row.get("club", ""), row.get("player", "")))


def feature_dict_from_row(row: dict[str, str], numeric_features: list[str], categorical_features: list[str]) -> dict[str, object]:
    features: dict[str, object] = {}
    for feature in numeric_features:
        raw = row.get(feature, "")
        missing = 1.0 if raw in {"", None} else 0.0
        features[feature] = parse_float(raw, 0.0)
        features[f"{feature}__missing"] = missing
    for feature in categorical_features:
        value = (row.get(feature, "") or "unknown").strip() or "unknown"
        features[feature] = value
    return features


def encode_labels(rows: list[dict[str, str]], target_label_field: str) -> list[int]:
    label_to_int = {label: index for index, label in enumerate(LABELS)}
    return [label_to_int[row[target_label_field]] for row in rows]


def class_weights(rows: list[dict[str, str]], target_label_field: str) -> list[float]:
    counts = Counter(row[target_label_field] for row in rows)
    total = len(rows)
    if not counts or total == 0:
        return []
    n_classes = len(LABELS)
    return [total / (n_classes * counts[row[target_label_field]]) for row in rows]


def split_train_validation(rows: list[dict[str, str]], target_label_field: str, min_validation_rows: int = 12) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    ordered = sort_rows(rows)
    if len(ordered) < max(min_validation_rows * 2, 30):
        return ordered, []
    split_at = max(int(len(ordered) * 0.8), len(ordered) - min_validation_rows)
    split_at = min(split_at, len(ordered) - min_validation_rows)
    return ordered[:split_at], ordered[split_at:]


def majority_baseline(train_rows: list[dict[str, str]], eval_rows: list[dict[str, str]], target_label_field: str) -> dict[str, object]:
    counts = Counter(row[target_label_field] for row in train_rows)
    majority = counts.most_common(1)[0][0]
    total = sum(counts.values())
    probs = {label: counts.get(label, 0) / total for label in LABELS}
    prediction_rows = []
    for row in eval_rows:
        prediction_rows.append(
            {
                "actual_label": row[target_label_field],
                "predicted_label": majority,
                "prob_negative": probs.get("negative", 0.0),
                "prob_neutral": probs.get("neutral", 0.0),
                "prob_positive": probs.get("positive", 0.0),
                "prediction_confidence": max(probs.values()) if probs else 0.0,
            }
        )
    return evaluate_prediction_rows(prediction_rows)


def brier_multiclass(rows: list[dict[str, object]]) -> float | None:
    if not rows:
        return None
    label_to_index = {label: index for index, label in enumerate(LABELS)}
    total = 0.0
    for row in rows:
        actual = str(row["actual_label"])
        actual_index = label_to_index[actual]
        probs = [
            float(row.get("prob_negative", 0.0)),
            float(row.get("prob_neutral", 0.0)),
            float(row.get("prob_positive", 0.0)),
        ]
        for index, prob in enumerate(probs):
            target = 1.0 if index == actual_index else 0.0
            total += (prob - target) ** 2
    return round(total / len(rows), 6)


def calibration_bins(rows: list[dict[str, object]], bins: int = 5) -> list[dict[str, object]]:
    if not rows:
        return []
    bucketed: list[list[dict[str, object]]] = [[] for _ in range(bins)]
    for row in rows:
        confidence = float(row.get("prediction_confidence", 0.0))
        index = min(int(confidence * bins), bins - 1)
        bucketed[index].append(row)
    output = []
    for index, bucket in enumerate(bucketed):
        if not bucket:
            continue
        avg_conf = mean(float(item.get("prediction_confidence", 0.0)) for item in bucket)
        accuracy = mean(1.0 if item["actual_label"] == item["predicted_label"] else 0.0 for item in bucket)
        output.append(
            {
                "bin": index,
                "count": len(bucket),
                "avg_confidence": round(avg_conf, 4),
                "accuracy": round(accuracy, 4),
            }
        )
    return output


def evaluate_prediction_rows(prediction_rows: list[dict[str, object]]) -> dict[str, object]:
    if not prediction_rows:
        return {"n": 0}
    metrics = import_ml_dependencies()
    accuracy_score = metrics["accuracy_score"]
    confusion_matrix = metrics["confusion_matrix"]
    f1_score = metrics["f1_score"]
    log_loss = metrics["log_loss"]
    y_true = [str(row["actual_label"]) for row in prediction_rows]
    y_pred = [str(row["predicted_label"]) for row in prediction_rows]
    y_prob = []
    for row in prediction_rows:
        probs = [
            float(row.get("prob_negative", 0.0)),
            float(row.get("prob_neutral", 0.0)),
            float(row.get("prob_positive", 0.0)),
        ]
        total = sum(probs)
        if total > 0:
            probs = [value / total for value in probs]
        y_prob.append(probs)
    return {
        "n": len(prediction_rows),
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "macro_f1": round(float(f1_score(y_true, y_pred, average="macro", zero_division=0)), 4),
        "log_loss": round(float(log_loss(y_true, y_prob, labels=LABELS)), 6),
        "brier_multiclass": brier_multiclass(prediction_rows),
        "class_balance": dict(Counter(y_true)),
        "predicted_counts": dict(Counter(y_pred)),
        "confusion_matrix": {
            "labels": LABELS,
            "matrix": confusion_matrix(y_true, y_pred, labels=LABELS).tolist(),
        },
        "calibration": calibration_bins(prediction_rows),
    }


def legacy_repo_baselines(train_rows: list[dict[str, str]], test_rows: list[dict[str, str]], target_label_field: str) -> dict[str, object]:
    from .ml import fit_knn, fit_model, predict_one, predict_one_knn

    legacy_train = []
    legacy_test = []
    for row in train_rows:
        legacy_row = dict(row)
        legacy_row["label"] = row[target_label_field]
        legacy_row["car_m1_p1"] = row.get("target_abnormal_return_p3", "0")
        legacy_train.append(legacy_row)
    for row in test_rows:
        legacy_row = dict(row)
        legacy_row["label"] = row[target_label_field]
        legacy_row["car_m1_p1"] = row.get("target_abnormal_return_p3", "0")
        legacy_test.append(legacy_row)

    baselines: dict[str, object] = {}
    for name, model, predictor in [
        ("legacy_nb", fit_model(legacy_train), predict_one),
        ("legacy_knn_1", fit_knn(legacy_train, k=1), predict_one_knn),
    ]:
        prediction_rows = []
        for row in legacy_test:
            predicted, confidence, probabilities = predictor(model, row)
            prediction_rows.append(
                {
                    "actual_label": row["label"],
                    "predicted_label": predicted,
                    "prediction_confidence": confidence,
                    "prob_negative": probabilities.get("negative", 0.0),
                    "prob_neutral": probabilities.get("neutral", 0.0),
                    "prob_positive": probabilities.get("positive", 0.0),
                }
            )
        baselines[name] = evaluate_prediction_rows(prediction_rows)
    return baselines


def top_feature_importance(feature_names: list[str], values: list[float], limit: int = 25) -> list[dict[str, object]]:
    pairs = sorted(zip(feature_names, values), key=lambda item: abs(item[1]), reverse=True)[:limit]
    return [{"feature": name, "importance": round(float(value), 6)} for name, value in pairs]


def logistic_feature_importance(model: Any, feature_names: list[str]) -> list[dict[str, object]]:
    coef = model.coef_
    values = [mean(abs(coef[row_idx][col_idx]) for row_idx in range(len(coef))) for col_idx in range(len(feature_names))]
    return top_feature_importance(feature_names, values)


def xgb_feature_importance(model: Any, feature_names: list[str]) -> list[dict[str, object]]:
    values = list(model.feature_importances_)
    return top_feature_importance(feature_names, values)


def evaluate_model_predictions(
    model: Any,
    vectorizer: Any,
    rows: list[dict[str, str]],
    numeric_features: list[str],
    categorical_features: list[str],
    train_end_season: str,
    target_label_field: str,
    transformer: Any | None = None,
) -> dict[str, object]:
    predictions = predict_rows(
        model,
        vectorizer,
        rows,
        numeric_features,
        categorical_features,
        train_end_season,
        target_label_field,
        transformer=transformer,
    )
    return evaluate_prediction_rows(predictions)


def select_xgb_candidate(
    XGBClassifier: Any,
    vectorizer: Any,
    train_rows: list[dict[str, str]],
    val_rows: list[dict[str, str]],
    target_label_field: str,
    train_end_season: str,
) -> tuple[str, list[str], list[str], dict[str, Any], Any, dict[str, object]]:
    candidate_presets = ["full", "core"]
    candidate_params = [
        {
            "n_estimators": 120,
            "max_depth": 2,
            "learning_rate": 0.05,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "reg_lambda": 1.0,
        },
        {
            "n_estimators": 200,
            "max_depth": 3,
            "learning_rate": 0.05,
            "subsample": 0.9,
            "colsample_bytree": 0.9,
            "reg_lambda": 1.0,
        },
        {
            "n_estimators": 240,
            "max_depth": 2,
            "learning_rate": 0.03,
            "subsample": 0.85,
            "colsample_bytree": 0.85,
            "reg_lambda": 2.0,
        },
    ]
    best_choice: tuple[str, list[str], list[str], dict[str, Any], Any, dict[str, object]] | None = None
    best_score = float("-inf")
    selection_rows = val_rows or train_rows
    for preset in candidate_presets:
        numeric_features = active_numeric_features(train_rows, preset=preset)
        categorical_features = active_categorical_features(train_rows)
        train_feature_dicts = [feature_dict_from_row(row, numeric_features, categorical_features) for row in train_rows]
        x_train = vectorizer.fit_transform(train_feature_dicts)
        y_train = encode_labels(train_rows, target_label_field)
        weights_train = class_weights(train_rows, target_label_field)
        eval_feature_dicts = [feature_dict_from_row(row, numeric_features, categorical_features) for row in selection_rows]
        x_eval = vectorizer.transform(eval_feature_dicts)
        y_eval = encode_labels(selection_rows, target_label_field)
        for params in candidate_params:
            model = XGBClassifier(
                objective="multi:softprob",
                num_class=len(LABELS),
                random_state=42,
                eval_metric="mlogloss",
                **params,
            )
            model.fit(x_train, y_train, sample_weight=weights_train, eval_set=[(x_eval, y_eval)], verbose=False)
            eval_metrics = evaluate_model_predictions(
                model,
                vectorizer,
                selection_rows,
                numeric_features,
                categorical_features,
                train_end_season,
                target_label_field,
            )
            score = float(eval_metrics.get("macro_f1", 0.0))
            if score > best_score:
                best_score = score
                best_choice = (preset, numeric_features, categorical_features, params, model, eval_metrics)
    if best_choice is None:
        raise ValueError("Unable to select an XGBoost candidate for Stage 6")
    return best_choice


def add_split(row: dict[str, str], train_end_season: str, target_label_field: str) -> str:
    if row.get("prediction_scope", "direct") != "direct":
        return "intelligence_only"
    row_season = season_start(row.get("season", ""))
    train_end = season_start(train_end_season)
    has_target = row.get(target_label_field) in LABELS
    if has_target and row_season <= train_end:
        return "train"
    if has_target and row_season > train_end:
        return "test"
    if row_season > train_end:
        return "live_unlabeled"
    return "unlabeled"


def predict_rows(
    model: Any,
    vectorizer: Any,
    rows: list[dict[str, str]],
    numeric_features: list[str],
    categorical_features: list[str],
    train_end_season: str,
    target_label_field: str,
    transformer: Any | None = None,
) -> list[dict[str, object]]:
    if not rows:
        return []
    prediction_rows: list[dict[str, object]] = []
    eligible_rows = [row for row in rows if row.get("prediction_scope", "direct") == "direct"]
    probabilities = []
    predicted_indices = []
    if eligible_rows:
        feature_dicts = [feature_dict_from_row(row, numeric_features, categorical_features) for row in eligible_rows]
        x = vectorizer.transform(feature_dicts)
        if transformer is not None:
            x = transformer.transform(x)
        probabilities = model.predict_proba(x)
        predicted_indices = model.predict(x)
    eligible_iter = iter(zip(eligible_rows, predicted_indices, probabilities))
    for row in rows:
        if row.get("prediction_scope", "direct") != "direct":
            prediction_rows.append(
                {
                    **row,
                    "split": add_split(row, train_end_season, target_label_field),
                    "actual_label": row.get(target_label_field, ""),
                    "predicted_label": "",
                    "prediction_confidence": "",
                    "prob_negative": "",
                    "prob_neutral": "",
                    "prob_positive": "",
                }
            )
            continue
        _, pred_index, probs = next(eligible_iter)
        pred_label = LABELS[int(pred_index)]
        output = {
            **row,
            "split": add_split(row, train_end_season, target_label_field),
            "actual_label": row.get(target_label_field, ""),
            "predicted_label": pred_label,
            "prediction_confidence": round(float(max(probs)), 4),
            "prob_negative": round(float(probs[0]), 4),
            "prob_neutral": round(float(probs[1]), 4),
            "prob_positive": round(float(probs[2]), 4),
        }
        prediction_rows.append(output)
    return prediction_rows


def train_stage6_models(
    dataset_path: Path,
    metrics_path: Path,
    predictions_dir: Path,
    train_end_season: str = "2024-25",
    target_label_field: str = "target_label_p3",
) -> dict[str, object]:
    deps = import_ml_dependencies()
    DictVectorizer = deps["DictVectorizer"]
    LogisticRegression = deps["LogisticRegression"]
    StandardScaler = deps["StandardScaler"]
    XGBClassifier = deps["XGBClassifier"]

    all_rows = read_csv(dataset_path)
    numeric_features = active_numeric_features(all_rows, preset="full")
    categorical_features = active_categorical_features(all_rows)
    labeled_rows = usable_rows(all_rows, target_label_field=target_label_field)
    train_rows, test_rows = temporal_split(labeled_rows, train_end_season)
    train_rows = sort_rows(train_rows)
    test_rows = sort_rows(test_rows)
    if not train_rows:
        raise ValueError("No labeled training rows found for Stage 6")
    if not test_rows:
        raise ValueError("No labeled test rows found for Stage 6; check the train/test season split")

    train_feature_dicts = [feature_dict_from_row(row, numeric_features, categorical_features) for row in train_rows]
    test_feature_dicts = [feature_dict_from_row(row, numeric_features, categorical_features) for row in test_rows]
    vectorizer = DictVectorizer(sparse=False)
    x_train = vectorizer.fit_transform(train_feature_dicts)
    x_test = vectorizer.transform(test_feature_dicts)
    y_train = encode_labels(train_rows, target_label_field)
    y_test = encode_labels(test_rows, target_label_field)
    weights_train = class_weights(train_rows, target_label_field)
    feature_names = list(vectorizer.get_feature_names_out())

    baseline_metrics = majority_baseline(train_rows, test_rows, target_label_field)

    logistic_scaler = StandardScaler()
    x_train_scaled = logistic_scaler.fit_transform(x_train)
    logistic = LogisticRegression(
        max_iter=2000,
        class_weight="balanced",
        solver="lbfgs",
        random_state=42,
    )
    logistic.fit(x_train_scaled, y_train)
    logistic_predictions = predict_rows(
        logistic,
        vectorizer,
        all_rows,
        numeric_features,
        categorical_features,
        train_end_season,
        target_label_field,
        transformer=logistic_scaler,
    )
    logistic_test = [row for row in logistic_predictions if row["split"] == "test"]
    logistic_train = [row for row in logistic_predictions if row["split"] == "train"]
    logistic_metrics = {
        "train": evaluate_prediction_rows(logistic_train),
        "test": evaluate_prediction_rows(logistic_test),
        "feature_importance": logistic_feature_importance(logistic, feature_names),
    }

    train_core_rows, val_rows = split_train_validation(train_rows, target_label_field)
    xgb_vectorizer = DictVectorizer(sparse=False)
    (
        xgb_feature_preset,
        xgb_numeric_features,
        xgb_categorical_features,
        xgb_params,
        _,
        xgb_validation_metrics,
    ) = select_xgb_candidate(
        XGBClassifier,
        xgb_vectorizer,
        train_core_rows,
        val_rows,
        target_label_field,
        train_end_season,
    )
    xgb_train_feature_dicts = [
        feature_dict_from_row(row, xgb_numeric_features, xgb_categorical_features) for row in train_rows
    ]
    xgb_x_train = xgb_vectorizer.fit_transform(xgb_train_feature_dicts)
    xgb_y_train = encode_labels(train_rows, target_label_field)
    xgb_weights_train = class_weights(train_rows, target_label_field)
    xgb = XGBClassifier(
        objective="multi:softprob",
        num_class=len(LABELS),
        random_state=42,
        eval_metric="mlogloss",
        **xgb_params,
    )
    xgb.fit(xgb_x_train, xgb_y_train, sample_weight=xgb_weights_train, verbose=False)
    xgb_feature_names = list(xgb_vectorizer.get_feature_names_out())
    xgb_predictions = predict_rows(
        xgb,
        xgb_vectorizer,
        all_rows,
        xgb_numeric_features,
        xgb_categorical_features,
        train_end_season,
        target_label_field,
    )
    xgb_test = [row for row in xgb_predictions if row["split"] == "test"]
    xgb_train = [row for row in xgb_predictions if row["split"] == "train"]
    xgb_metrics = {
        "train": evaluate_prediction_rows(xgb_train),
        "test": evaluate_prediction_rows(xgb_test),
        "validation": xgb_validation_metrics,
        "selected_feature_preset": xgb_feature_preset,
        "selected_numeric_features": xgb_numeric_features,
        "selected_categorical_features": xgb_categorical_features,
        "selected_params": xgb_params,
        "feature_importance": xgb_feature_importance(xgb, xgb_feature_names),
    }

    ensure_parent(predictions_dir / "dummy.txt")
    logistic_predictions_path = predictions_dir / "stage6_logistic_predictions.csv"
    xgb_predictions_path = predictions_dir / "stage6_xgboost_predictions.csv"
    prediction_fields = list(logistic_predictions[0].keys()) if logistic_predictions else []
    write_csv(logistic_predictions_path, logistic_predictions, prediction_fields)
    write_csv(xgb_predictions_path, xgb_predictions, prediction_fields)

    metrics = {
        "dataset_path": str(dataset_path),
        "target_label_field": target_label_field,
        "train_end_season": train_end_season,
        "n_all_rows": len(all_rows),
        "n_labeled_rows": len(labeled_rows),
        "n_train_rows": len(train_rows),
        "n_test_rows": len(test_rows),
        "n_validation_rows": len(val_rows),
        "numeric_features": numeric_features,
        "categorical_features": categorical_features,
        "leakage_excluded_fields": sorted(LEAKY_FIELDS),
        "baseline_majority": baseline_metrics,
        "legacy_repo_baselines": legacy_repo_baselines(train_rows, test_rows, target_label_field),
        "models": {
            "logistic": logistic_metrics,
            "xgboost": xgb_metrics,
        },
        "prediction_files": {
            "logistic": str(logistic_predictions_path),
            "xgboost": str(xgb_predictions_path),
        },
        "warning": "Targets use post-rumor abnormal return windows; do not feed post-event columns back into live prediction features.",
    }
    ensure_parent(metrics_path)
    metrics_path.write_text(json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8")
    return metrics
