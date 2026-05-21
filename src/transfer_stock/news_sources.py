from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib.parse import quote_plus

from .config import CONFIG_DIR, Club, load_yaml


TRANSFER_KEYWORDS = (
    "transfer",
    "sign",
    "signing",
    "signed",
    "bid",
    "deal",
    "agreed",
    "agreement",
    "talks",
    "medical",
    "loan",
    "window",
    "rumour",
    "rumor",
    "rumours",
    "rumors",
    "gerucht",
    "geruchten",
    "bod",
    "akkoord",
    "huur",
    "verhuur",
    "medische keuring",
    "transfere",
    "transferência",
    "transferências",
    "mercado",
    "proposta",
    "propostas",
    "acordo",
    "negociações",
    "emprestimo",
    "empréstimo",
    "reforço",
    "saída",
)

SOURCE_PRESETS: dict[str, tuple[str, ...]] = {
    "fast_no_api": (
        "guardian_rss",
        "bbc_football_rss",
        "google_news_global_en",
    ),
    "balanced_no_api": (
        "guardian_rss",
        "bbc_football_rss",
        "google_news_global_en",
        "google_news_ajax_nl",
        "google_news_portugal_pt",
        "fundus_uk",
        "fundus_de",
        "fundus_it",
        "fundus_nl",
        "fundus_pt",
        "fundus_fr",
    ),
    "wide_no_api": (
        "guardian_rss",
        "bbc_football_rss",
        "google_news_global_en",
        "google_news_ajax_nl",
        "google_news_portugal_pt",
        "google_news_germany_de",
        "google_news_italy_it",
        "google_news_france_fr",
        "google_news_scotland_en",
        "fundus_uk",
        "fundus_de",
        "fundus_it",
        "fundus_nl",
        "fundus_pt",
        "fundus_fr",
    ),
    "fundus_only": (
        "fundus_uk",
        "fundus_de",
        "fundus_it",
        "fundus_nl",
        "fundus_pt",
        "fundus_fr",
    ),
    "api_plus_no_api": (
        "guardian_api",
        "gnews_api",
        "guardian_rss",
        "bbc_football_rss",
        "google_news_global_en",
        "google_news_ajax_nl",
        "google_news_portugal_pt",
        "fundus_uk",
        "fundus_de",
        "fundus_it",
        "fundus_nl",
        "fundus_pt",
        "fundus_fr",
    ),
}

METHOD_PRESETS: dict[str, tuple[str, ...]] = {
    "fast_no_api": ("rss",),
    "balanced_no_api": ("rss", "fundus"),
    "wide_no_api": ("rss", "fundus"),
    "fundus_only": ("fundus",),
    "api_plus_no_api": ("provider", "rss", "fundus"),
}


@dataclass(frozen=True)
class NewsSource:
    key: str
    name: str
    kind: str
    url: str
    enabled: bool = True
    provider: str = ""
    section: str = ""
    language: str = "English"
    crawl_method: str = ""
    query_template: str = ""
    hl: str = ""
    gl: str = ""
    ceid: str = ""
    club_keys: tuple[str, ...] = ()
    publisher_groups: tuple[str, ...] = ()


def load_news_sources(path=CONFIG_DIR / "news_sources.yml") -> dict[str, NewsSource]:
    raw = load_yaml(path).get("sources", {})
    sources: dict[str, NewsSource] = {}
    for key, item in raw.items():
        sources[key] = NewsSource(
            key=key,
            name=item.get("name", key),
            kind=item["kind"],
            url=item.get("url", ""),
            enabled=bool(item.get("enabled", True)),
            provider=item.get("provider", ""),
            section=item.get("section", ""),
            language=item.get("language", "English"),
            crawl_method=item.get("crawl_method", ""),
            query_template=item.get("query_template", ""),
            hl=item.get("hl", ""),
            gl=item.get("gl", ""),
            ceid=item.get("ceid", ""),
            club_keys=tuple(item.get("club_keys", [])),
            publisher_groups=tuple(item.get("publisher_groups", [])),
        )
    return sources


def select_sources(sources: dict[str, NewsSource], requested: list[str] | None) -> list[NewsSource]:
    if not requested:
        return [source for source in sources.values() if source.enabled]
    lookup: dict[str, NewsSource] = {}
    for source in sources.values():
        lookup[source.key.lower()] = source
        lookup[source.name.lower()] = source
    selected: list[NewsSource] = []
    seen = set()
    for item in requested:
        source = lookup.get(item.lower())
        if source is None:
            raise ValueError(f"Unknown source selection: {item}")
        if source.key in seen:
            continue
        seen.add(source.key)
        selected.append(source)
    return [source for source in selected if source.enabled]


def source_preset_names() -> list[str]:
    return sorted(SOURCE_PRESETS.keys())


def select_source_preset(sources: dict[str, NewsSource], preset: str | None) -> list[NewsSource]:
    if not preset:
        return [source for source in sources.values() if source.enabled]
    keys = SOURCE_PRESETS.get(preset)
    if keys is None:
        raise ValueError(f"Unknown source preset: {preset}")
    return select_sources(sources, list(keys))


def methods_for_preset(preset: str | None) -> list[str] | None:
    if not preset:
        return None
    methods = METHOD_PRESETS.get(preset)
    if methods is None:
        raise ValueError(f"Unknown source preset: {preset}")
    return list(methods)


def club_query_terms(club: Club) -> list[str]:
    return [term for term in dict.fromkeys((club.name, *club.aliases)) if term]


def source_supports_club(source: NewsSource, club: Club) -> bool:
    if not source.club_keys:
        return True
    return club.key in source.club_keys


def render_source_url(source: NewsSource, club: Club) -> str:
    if not source.query_template:
        return source.url
    club_terms = " OR ".join(f'"{term}"' for term in club_query_terms(club))
    query = source.query_template.format(
        club_name=club.name,
        club_terms=club_terms,
    )
    return source.url.format(
        query=quote_plus(query),
        hl=source.hl,
        gl=source.gl,
        ceid=source.ceid,
    )


def mentions_transfer(text: str) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in TRANSFER_KEYWORDS)


def mentions_club(text: str, club: Club) -> bool:
    lowered = text.lower()
    return any(alias.lower() in lowered for alias in club_query_terms(club))


def club_matches_text(text: str, clubs: Iterable[Club]) -> list[str]:
    lowered = text.lower()
    matches = []
    for club in clubs:
        if any(alias.lower() in lowered for alias in club_query_terms(club)):
            matches.append(club.name)
    return list(dict.fromkeys(matches))
