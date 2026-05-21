from __future__ import annotations

from pathlib import Path

from .io import read_csv, write_csv
from .model import heuristic_market_impact


REPORT_FIELDS = [
    "rank",
    "date",
    "original_transfer_date",
    "date_note",
    "season",
    "club",
    "player",
    "direction",
    "transfer_type",
    "transfer_quality",
    "rumor_count",
    "max_rumor_strength",
    "observed_car_m1_p1",
    "observed_label",
    "heuristic_predicted_car",
    "heuristic_label",
    "confidence",
    "interpretation",
]


def parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def date_note(row: dict[str, str]) -> str:
    event_date_source = row.get("event_date_source", "")
    if event_date_source == "first_credible_news":
        return "earliest credible news/article date"
    if event_date_source == "proxy_transfer_window":
        return "proxy window date; not exact announcement date"
    source_date = row.get("date", "")
    source = row.get("source", "")
    if source_date.endswith("-07-01") or source_date.endswith("-01-01"):
        return "proxy window date; not exact announcement date"
    if source == "ewenme/transfers":
        return "source has transfer window timing"
    return "exact or source-provided date"


def interpretation(row: dict[str, object]) -> str:
    observed = row.get("observed_label") or ""
    predicted = row.get("heuristic_label") or ""
    rumor_count = int(row.get("rumor_count") or 0)
    if observed:
        return f"Observed {observed} abnormal return; heuristic says {predicted}; {rumor_count} matched rumor/news rows."
    return f"No observed CAR label yet; heuristic says {predicted}; {rumor_count} matched rumor/news rows."


def sort_key(row: dict[str, object]) -> tuple[float, float]:
    observed = abs(float(row.get("observed_car_m1_p1") or 0.0))
    predicted = abs(float(row.get("heuristic_predicted_car") or 0.0))
    return observed, predicted


def build_impact_rows(model_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in model_rows:
        transfer_quality = parse_float(item.get("transfer_quality"), 0.5)
        rumor_strength = parse_float(item.get("max_rumor_strength"), 0.5)
        prediction = heuristic_market_impact(
            rumor_strength=rumor_strength,
            transfer_quality=transfer_quality,
            direction=item.get("direction", "in"),
        )
        row = {
            "date": item.get("date", ""),
            "original_transfer_date": item.get("original_transfer_date", ""),
            "date_note": date_note(item),
            "season": item.get("season", ""),
            "club": item.get("club", ""),
            "player": item.get("player", ""),
            "direction": item.get("direction", ""),
            "transfer_type": item.get("transfer_type", ""),
            "transfer_quality": item.get("transfer_quality", ""),
            "rumor_count": item.get("rumor_count", "0"),
            "max_rumor_strength": item.get("max_rumor_strength", ""),
            "observed_car_m1_p1": item.get("car_m1_p1", ""),
            "observed_label": item.get("label", ""),
            "heuristic_predicted_car": prediction["predicted_car"],
            "heuristic_label": prediction["label"],
            "confidence": prediction["confidence"],
        }
        row["interpretation"] = interpretation(row)
        rows.append(row)
    rows = sorted(rows, key=sort_key, reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def write_markdown_report(path: Path, rows: list[dict[str, object]], source_csv: Path) -> None:
    labeled = [row for row in rows if row.get("observed_car_m1_p1") not in {"", None}]
    positive = sum(1 for row in labeled if row.get("observed_label") == "positive")
    neutral = sum(1 for row in labeled if row.get("observed_label") == "neutral")
    negative = sum(1 for row in labeled if row.get("observed_label") == "negative")
    is_rumor_report = bool(rows and rows[0].get("published_date"))
    with path.open("w", encoding="utf-8") as handle:
        title = "Rumor Stock Impact Report" if is_rumor_report else "Transfer Stock Impact Report"
        handle.write(f"# {title}\n\n")
        handle.write(f"Source model table: `{source_csv}`\n\n")
        row_name = "rumor/article rows" if is_rumor_report else "transfer rows"
        handle.write(f"- Total {row_name}: {len(rows)}\n")
        handle.write(f"- Rows with observed CAR labels: {len(labeled)}\n")
        handle.write(f"- Observed labels: {positive} positive, {neutral} neutral, {negative} negative\n")
        if is_rumor_report:
            handle.write("- Date note: rows use article publication dates as the stock-impact event date.\n")
        else:
            handle.write("- Date warning: some transfer rows may still use source/proxy dates rather than first market-moving rumor dates.\n")
        handle.write("- ML status: this report uses event-study labels plus a transparent heuristic, not a trained ML model.\n\n")
        handle.write("## Top Rows By Observed/Predicted Impact\n\n")
        handle.write("| Rank | Date | Club | Player | Type | Rumors | Observed CAR | Observed | Heuristic CAR | Heuristic | Note |\n")
        handle.write("| --- | --- | --- | --- | --- | ---: | ---: | --- | ---: | --- | --- |\n")
        for row in rows[:25]:
            handle.write(
                "| {rank} | {date} | {club} | {player} | {transfer_type} | {rumor_count} | {observed_car_m1_p1} | {observed_label} | {heuristic_predicted_car} | {heuristic_label} | {date_note} |\n".format(
                    **row
                )
            )
        if is_rumor_report:
            return
        news_rows = [row for row in rows if row.get("date_note") == "earliest credible news/article date"]
        handle.write("\n## Rows Using Inferred News Dates\n\n")
        if not news_rows:
            handle.write("No rows currently use inferred news dates. Run `fetch-event-news`, `score-news`, and `infer-event-dates` to populate this section.\n")
            return
        handle.write("| Date | Original Transfer Date | Club | Player | Rumors | Observed CAR | Observed | Heuristic | Note |\n")
        handle.write("| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |\n")
        for row in news_rows[:50]:
            handle.write(
                "| {date} | {original_transfer_date} | {club} | {player} | {rumor_count} | {observed_car_m1_p1} | {observed_label} | {heuristic_label} | {date_note} |\n".format(
                    **row
                )
            )


def build_report(model_dataset: Path, output_csv: Path, output_markdown: Path) -> list[dict[str, object]]:
    rows = build_impact_rows(read_csv(model_dataset))
    write_csv(output_csv, rows, REPORT_FIELDS)
    output_markdown.parent.mkdir(parents=True, exist_ok=True)
    write_markdown_report(output_markdown, rows, model_dataset)
    return rows
