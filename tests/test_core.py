import csv
import json
from pathlib import Path
import tempfile
from datetime import date, timedelta
import unittest

from transfer_stock.article_store import dedupe_articles, normalize_article_row, normalize_url
from transfer_stock.backtesting import blended_signal_label, blended_signal_score, candidate_for_strategy, dedupe_candidates
from transfer_stock.claims import heuristic_extract_claim
from transfer_stock.config import load_clubs
from transfer_stock.credibility_engine import AggregateStat, credibility_outputs, credibility_row
from transfer_stock.dcaribou import transfer_kind_tags
from transfer_stock.demo import build_demo_payload, transfer_history_rows
from transfer_stock.event_study import cumulative_abnormal_return
from transfer_stock.ewenme import canonical_season, fee_cleaned_to_eur
from transfer_stock.features import credibility_score, transfer_quality_score
from transfer_stock.market_features import compute_market_features_for_event
from transfer_stock.matching import single_match, transfer_id_for, TransferCandidate
from transfer_stock.ml_v2 import LEAKY_FIELDS, parse_datetime_to_date, unmatched_claim_row, usable_rows as usable_rows_v2
from transfer_stock.news_sources import NewsSource, render_source_url, source_supports_club
from transfer_stock.stock import PriceBar
from transfer_stock.targets import direct_target_rows
from transfer_stock.transfers import Transfer, filter_loans, infer_season


class CoreTests(unittest.TestCase):
    def test_transfer_quality_score_bounds(self):
        transfer = Transfer(
            date=date(2024, 7, 1),
            club="Manchester United",
            player="Example Player",
            direction="in",
            from_club="A",
            to_club="B",
            age=23,
            position="Forward",
            market_value_eur=50_000_000,
            transfer_fee_eur=35_000_000,
            wage_eur_annual=8_000_000,
            source="test",
            source_url="",
        )
        self.assertLessEqual(0, transfer_quality_score(transfer))
        self.assertGreaterEqual(1, transfer_quality_score(transfer))

    def test_credibility_keyword_adjustment(self):
        config = {
            "default_source_score": 0.5,
            "sources": {"Fabrizio Romano": 0.95},
            "keywords": {"here we go": 0.12},
        }
        self.assertGreater(credibility_score("Here we go for the transfer", "Unknown", config), 0.5)
        self.assertEqual(credibility_score("Deal update", "Fabrizio Romano", config), 0.95)

    def test_event_study_returns_none_without_estimation_window(self):
        start = date(2024, 1, 1)
        bars = [
            PriceBar(start + timedelta(days=i), 10 + i, 10 + i, 10 + i, 10 + i, 1000)
            for i in range(5)
        ]
        self.assertIsNone(cumulative_abnormal_return(bars, bars, start + timedelta(days=3)))

    def test_infer_football_season(self):
        self.assertEqual(infer_season(date(2024, 7, 1)), "2024-25")
        self.assertEqual(infer_season(date(2025, 6, 30)), "2024-25")
        self.assertEqual(canonical_season("2024/2025"), "2024-25")

    def test_fee_cleaned_to_eur(self):
        self.assertEqual(fee_cleaned_to_eur("1.5"), 1_500_000)
        self.assertIsNone(fee_cleaned_to_eur("NA"))

    def test_filter_loans(self):
        base = Transfer(
            date=date(2024, 7, 1),
            club="Manchester United",
            player="Permanent Player",
            direction="in",
            from_club="A",
            to_club="B",
            age=23,
            position="Forward",
            market_value_eur=50_000_000,
            transfer_fee_eur=35_000_000,
            wage_eur_annual=8_000_000,
            source="test",
            source_url="",
        )
        loan = Transfer(
            date=date(2024, 7, 1),
            club="Manchester United",
            player="Loan Player",
            direction="in",
            from_club="A",
            to_club="B",
            age=23,
            position="Forward",
            market_value_eur=50_000_000,
            transfer_fee_eur=0,
            wage_eur_annual=8_000_000,
            source="test",
            source_url="",
            transfer_type="loan",
            is_loan=True,
        )
        self.assertEqual(len(filter_loans([base, loan], "include")), 2)
        self.assertEqual(len(filter_loans([base, loan], "exclude")), 1)
        self.assertEqual(len(filter_loans([base, loan], "only")), 1)

    def test_dcaribou_tags_loan_and_return_pairs(self):
        rows = [
            {
                "player_id": "1",
                "player_name": "Jadon Sancho",
                "transfer_date": "2024-08-30",
                "from_club_id": "mu",
                "to_club_id": "che",
                "transfer_fee": "0",
            },
            {
                "player_id": "1",
                "player_name": "Jadon Sancho",
                "transfer_date": "2025-06-30",
                "from_club_id": "che",
                "to_club_id": "mu",
                "transfer_fee": "0",
            },
            {
                "player_id": "2",
                "player_name": "Permanent Player",
                "transfer_date": "2025-07-01",
                "from_club_id": "a",
                "to_club_id": "b",
                "transfer_fee": "15000000",
            },
        ]
        self.assertEqual(transfer_kind_tags(rows), ["loan", "loan_return", "permanent"])

    def test_normalize_url_strips_tracking(self):
        self.assertEqual(
            normalize_url("https://example.com/story/?utm_source=test&ref=abc&id=7#frag"),
            "https://example.com/story?id=7",
        )

    def test_normalize_article_row_adds_schema_fields(self):
        clubs = load_clubs()
        row = normalize_article_row(
            {
                "seen_at": "2026-05-19T12:00:00+00:00",
                "published_at": "2026-05-18T12:00:00Z",
                "source": "The Guardian / Test Reporter",
                "title": "Manchester United in transfer talks for Example Player",
                "url": "https://example.com/story?utm_source=test",
                "snippet": "Manchester United are in transfer talks.",
                "player": "Example Player",
            },
            clubs,
            crawl_method="provider_api",
            provider="guardian_api",
        )
        self.assertEqual(row["normalized_url"], "https://example.com/story")
        self.assertEqual(row["journalist"], "Test Reporter")
        self.assertIn("Manchester United", row["club_candidates"])
        self.assertIn("Example Player", row["player_candidates"])
        self.assertEqual(row["provider"], "guardian_api")

    def test_transfer_history_rows_excludes_future_and_loan_returns(self):
        clubs = load_clubs()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "transfers.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "date",
                        "original_transfer_date",
                        "event_date_source",
                        "event_date_confidence",
                        "season",
                        "club",
                        "player",
                        "direction",
                        "from_club",
                        "to_club",
                        "age",
                        "position",
                        "market_value_eur",
                        "transfer_fee_eur",
                        "wage_eur_annual",
                        "transfer_type",
                        "is_loan",
                        "source",
                        "source_url",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "date": "2025-06-30",
                        "original_transfer_date": "2025-06-30",
                        "event_date_source": "exact_transfer_date",
                        "event_date_confidence": "0.85",
                        "season": "2024-25",
                        "club": "Manchester United",
                        "player": "Jadon Sancho",
                        "direction": "in",
                        "from_club": "Chelsea",
                        "to_club": "Manchester United",
                        "age": "25",
                        "position": "Winger",
                        "market_value_eur": "30000000",
                        "transfer_fee_eur": "0",
                        "wage_eur_annual": "",
                        "transfer_type": "loan_return",
                        "is_loan": "1",
                        "source": "test",
                        "source_url": "",
                    }
                )
                writer.writerow(
                    {
                        "date": "2026-06-30",
                        "original_transfer_date": "2026-06-30",
                        "event_date_source": "exact_transfer_date",
                        "event_date_confidence": "0.85",
                        "season": "2025-26",
                        "club": "Manchester United",
                        "player": "Rasmus Hojlund",
                        "direction": "in",
                        "from_club": "Napoli",
                        "to_club": "Manchester United",
                        "age": "23",
                        "position": "Forward",
                        "market_value_eur": "55000000",
                        "transfer_fee_eur": "0",
                        "wage_eur_annual": "",
                        "transfer_type": "loan_return",
                        "is_loan": "1",
                        "source": "test",
                        "source_url": "",
                    }
                )
                writer.writerow(
                    {
                        "date": "2025-07-10",
                        "original_transfer_date": "2025-07-10",
                        "event_date_source": "exact_transfer_date",
                        "event_date_confidence": "0.85",
                        "season": "2025-26",
                        "club": "Manchester United",
                        "player": "Bryan Mbeumo",
                        "direction": "in",
                        "from_club": "Brentford",
                        "to_club": "Manchester United",
                        "age": "25",
                        "position": "Forward",
                        "market_value_eur": "55000000",
                        "transfer_fee_eur": "65000000",
                        "wage_eur_annual": "",
                        "transfer_type": "permanent",
                        "is_loan": "0",
                        "source": "test",
                        "source_url": "",
                    }
                )
            rows = transfer_history_rows(clubs, path)
            self.assertTrue(all(row["player"] != "Jadon Sancho" for row in rows))
            self.assertTrue(all(row["player"] != "Rasmus Hojlund" for row in rows))
            self.assertTrue(any(row["player"] == "Bryan Mbeumo" for row in rows))

    def test_templated_news_source_renders_locale_query(self):
        clubs = load_clubs()
        ajax = clubs["ajax"]
        source = NewsSource(
            key="google_news_ajax_nl",
            name="Google News Ajax NL",
            kind="rss",
            url="https://news.google.com/rss/search?q={query}&hl={hl}&gl={gl}&ceid={ceid}",
            language="Dutch",
            query_template="({club_terms}) (transfer OR geruchten)",
            hl="nl",
            gl="NL",
            ceid="NL:nl",
            club_keys=("ajax",),
        )
        self.assertTrue(source_supports_club(source, ajax))
        rendered = render_source_url(source, ajax)
        self.assertIn("news.google.com/rss/search", rendered)
        self.assertIn("hl=nl", rendered)
        self.assertIn("ceid=NL:nl", rendered)

    def test_dedupe_articles_keeps_first_copy(self):
        rows = [
            {"url": "https://example.com/a?utm_source=x", "title": "A", "published_at": "2026-05-01T10:00:00Z"},
            {"url": "https://example.com/a", "title": "A", "published_at": "2026-05-01T11:00:00Z"},
            {"url": "https://example.com/b", "title": "B", "published_at": "2026-05-01T11:00:00Z"},
        ]
        deduped = dedupe_articles(rows)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0]["url"], "https://example.com/a?utm_source=x")

    def test_claim_extraction_official_incoming_transfer(self):
        clubs = load_clubs()
        row = {
            "article_id": "a1",
            "published_at": "2026-05-18T12:00:00Z",
            "source": "The Guardian / Jamie Jackson",
            "journalist": "Jamie Jackson",
            "title": "Manchester United confirm agreement to sign Matheus Cunha from Wolves for £62.5m",
            "url": "https://example.com/cunha",
            "snippet": "Manchester United have confirmed the deal.",
            "club_candidates": ["Manchester United"],
            "player_candidates": ["Matheus Cunha"],
        }
        claim = heuristic_extract_claim(row, clubs, ["Matheus Cunha"])
        self.assertEqual(claim["primary_player"], "Matheus Cunha")
        self.assertEqual(claim["primary_club"], "Manchester United")
        self.assertEqual(claim["transfer_direction"], "in")
        self.assertEqual(claim["rumor_stage"], "official")
        self.assertEqual(claim["is_transfer_related"], 1)

    def test_claim_extraction_outgoing_transfer(self):
        clubs = load_clubs()
        row = {
            "article_id": "a2",
            "published_at": "2026-05-18T12:00:00Z",
            "source": "The Guardian / Jacob Steinberg",
            "title": "Chelsea close in on deal for Manchester United's Alejandro Garnacho",
            "url": "https://example.com/garnacho",
            "snippet": "Chelsea are advancing talks for the winger.",
            "club_candidates": ["Manchester United"],
            "player_candidates": ["Alejandro Garnacho"],
        }
        claim = heuristic_extract_claim(row, clubs, ["Alejandro Garnacho"])
        self.assertEqual(claim["primary_player"], "Alejandro Garnacho")
        self.assertEqual(claim["primary_club"], "Manchester United")
        self.assertEqual(claim["transfer_direction"], "out")
        self.assertEqual(claim["rumor_stage"], "advanced")
        self.assertEqual(claim["is_transfer_related"], 1)

    def test_claim_extraction_outgoing_replace_signal(self):
        clubs = load_clubs()
        row = {
            "article_id": "a2b",
            "published_at": "Wed, 20 May 2026 23:25:00 GMT",
            "source": "Google News Global EN",
            "title": "Man United transfer news: chance to sign affordable star to replace Casemiro",
            "url": "https://example.com/casemiro-replace",
            "snippet": "United may need a new midfielder if Casemiro leaves.",
            "club_candidates": ["Manchester United"],
            "player_candidates": ["Casemiro"],
        }
        claim = heuristic_extract_claim(row, clubs, ["Casemiro"])
        self.assertEqual(claim["primary_player"], "Casemiro")
        self.assertEqual(claim["primary_club"], "Manchester United")
        self.assertEqual(claim["transfer_direction"], "out")
        self.assertEqual(claim["is_transfer_related"], 1)

    def test_claim_extraction_rejects_live_blog_noise(self):
        clubs = load_clubs()
        row = {
            "article_id": "a3",
            "published_at": "2026-05-18T12:00:00Z",
            "source": "The Guardian / Simon Burnton",
            "title": "Tottenham v Leeds: Premier League - live",
            "url": "https://example.com/live",
            "snippet": "Minute-by-minute report from a bottom-half clash.",
            "club_candidates": ["Manchester United"],
            "player_candidates": [],
        }
        claim = heuristic_extract_claim(row, clubs, [])
        self.assertEqual(claim["is_transfer_related"], 0)
        self.assertEqual(claim["rumor_stage"], "unclear")

    def test_match_claim_exact_player_club(self):
        clubs = load_clubs()
        transfer = Transfer(
            date=date(2025, 8, 7),
            club="Manchester United",
            player="Benjamin Sesko",
            direction="in",
            from_club="RB Leipzig",
            to_club="Manchester United",
            age=22,
            position="Centre-Forward",
            market_value_eur=70_000_000,
            transfer_fee_eur=76_500_000,
            wage_eur_annual=None,
            source="test",
            source_url="",
            season="2025-26",
            transfer_type="permanent",
            is_loan=False,
        )
        claim = {
            "claim_id": "c1",
            "article_id": "a1",
            "published_at": "2025-08-06T10:00:00Z",
            "primary_player": "Benjamin Sesko",
            "primary_club": "Manchester United",
            "transfer_direction": "in",
            "transfer_type": "permanent",
            "rumor_stage": "agreed",
            "is_transfer_related": 1,
            "transfer_fee_eur_estimate": 76_000_000,
            "club_candidates": ["Manchester United"],
        }
        result = single_match(claim, [TransferCandidate(transfer_id_for(transfer), transfer)], clubs)
        self.assertEqual(result.matched_player, "Benjamin Sesko")
        self.assertEqual(result.matched_club, "Manchester United")
        self.assertEqual(result.ambiguity_flag, 0)
        self.assertGreater(result.match_score, 0.6)

    def test_match_claim_flags_ambiguity(self):
        clubs = load_clubs()
        transfer_one = Transfer(
            date=date(2025, 8, 7),
            club="Manchester United",
            player="Benjamin Sesko",
            direction="in",
            from_club="RB Leipzig",
            to_club="Manchester United",
            age=22,
            position="Centre-Forward",
            market_value_eur=70_000_000,
            transfer_fee_eur=76_500_000,
            wage_eur_annual=None,
            source="test",
            source_url="",
            season="2025-26",
            transfer_type="permanent",
            is_loan=False,
        )
        transfer_two = Transfer(
            date=date(2025, 8, 10),
            club="Manchester United",
            player="B. Sesko",
            direction="in",
            from_club="RB Leipzig",
            to_club="Manchester United",
            age=22,
            position="Centre-Forward",
            market_value_eur=70_000_000,
            transfer_fee_eur=76_000_000,
            wage_eur_annual=None,
            source="test",
            source_url="",
            season="2025-26",
            transfer_type="permanent",
            is_loan=False,
        )
        claim = {
            "claim_id": "c2",
            "article_id": "a2",
            "published_at": "2025-08-06T10:00:00Z",
            "primary_player": "Benjamin Sesko",
            "primary_club": "Manchester United",
            "transfer_direction": "in",
            "transfer_type": "permanent",
            "rumor_stage": "agreed",
            "is_transfer_related": 1,
            "club_candidates": ["Manchester United"],
        }
        result = single_match(
            claim,
            [
                TransferCandidate(transfer_id_for(transfer_one), transfer_one),
                TransferCandidate(transfer_id_for(transfer_two), transfer_two),
            ],
            clubs,
            ambiguity_delta=0.2,
        )
        self.assertEqual(result.ambiguity_flag, 1)

    def test_match_claim_rejects_unrelated_claim(self):
        clubs = load_clubs()
        transfer = Transfer(
            date=date(2025, 8, 7),
            club="Manchester United",
            player="Benjamin Sesko",
            direction="in",
            from_club="RB Leipzig",
            to_club="Manchester United",
            age=22,
            position="Centre-Forward",
            market_value_eur=70_000_000,
            transfer_fee_eur=76_500_000,
            wage_eur_annual=None,
            source="test",
            source_url="",
            season="2025-26",
            transfer_type="permanent",
            is_loan=False,
        )
        claim = {
            "claim_id": "c3",
            "article_id": "a3",
            "published_at": "2025-08-06T10:00:00Z",
            "primary_player": "",
            "primary_club": "Manchester United",
            "transfer_direction": "unclear",
            "transfer_type": "unclear",
            "rumor_stage": "unclear",
            "is_transfer_related": 0,
            "club_candidates": ["Manchester United"],
        }
        result = single_match(claim, [TransferCandidate(transfer_id_for(transfer), transfer)], clubs)
        self.assertEqual(result.matched_transfer_id, "")
        self.assertEqual(result.match_reason, "not_transfer_related")

    def test_match_claim_does_not_snap_to_old_season_transfer(self):
        clubs = load_clubs()
        old_transfer = Transfer(
            date=date(2022, 8, 19),
            club="Manchester United",
            player="Casemiro",
            direction="in",
            from_club="Real Madrid",
            to_club="Manchester United",
            age=30,
            position="Midfielder",
            market_value_eur=60_000_000,
            transfer_fee_eur=70_000_000,
            wage_eur_annual=None,
            source="test",
            source_url="",
            season="2022-23",
            transfer_type="permanent",
            is_loan=False,
        )
        claim = {
            "claim_id": "c3b",
            "article_id": "a3b",
            "published_at": "Wed, 20 May 2026 20:16:00 GMT",
            "primary_player": "Casemiro",
            "primary_club": "Manchester United",
            "transfer_direction": "out",
            "transfer_type": "permanent",
            "rumor_stage": "advanced",
            "is_transfer_related": 1,
            "club_candidates": ["Manchester United"],
        }
        result = single_match(claim, [TransferCandidate(transfer_id_for(old_transfer), old_transfer)], clubs)
        self.assertEqual(result.matched_transfer_id, "")
        self.assertEqual(result.match_reason, "no_candidates")

    def test_unmatched_public_sell_claim_still_maps_to_direct_target(self):
        clubs = load_clubs()
        claim = {
            "claim_id": "c3c",
            "article_id": "a3c",
            "published_at": "Wed, 20 May 2026 23:25:00 GMT",
            "primary_player": "Casemiro",
            "primary_club": "Manchester United",
            "transfer_direction": "out",
            "rumor_stage": "advanced",
            "is_transfer_related": 1,
            "source": "Google News Global EN",
            "journalist": "",
            "club_candidates": ["Manchester United"],
        }
        row = unmatched_claim_row(claim, date(2026, 5, 20), clubs)
        self.assertEqual(row["prediction_scope"], "direct")
        self.assertEqual(row["target_club"], "Manchester United")
        self.assertEqual(row["target_role"], "seller")

    def test_credibility_row_rewards_supported_official_claim(self):
        config = {
            "default_source_score": 0.5,
            "sources": {"The Guardian": 0.84},
        }
        claim = {
            "claim_id": "c4",
            "article_id": "a4",
            "published_at": "2025-08-06T10:00:00Z",
            "source": "The Guardian / Jamie Jackson",
            "journalist": "Jamie Jackson",
            "title": "Manchester United confirm agreement to sign Matheus Cunha from Wolves",
            "primary_player": "Matheus Cunha",
            "primary_club": "Manchester United",
            "rumor_stage": "official",
            "transfer_direction": "in",
            "is_transfer_related": 1,
        }
        match = {
            "matched_transfer_id": "t1",
            "match_score": "0.98",
            "match_reason": "exact_player|exact_club|date_near",
            "ambiguity_flag": "0",
        }
        source_stats = {
            "The Guardian / Jamie Jackson": AggregateStat(
                key="The Guardian / Jamie Jackson",
                n_claims=8,
                n_matched=7,
                match_rate=0.875,
                avg_match_score=0.91,
            )
        }
        journalist_stats = {
            "Jamie Jackson": AggregateStat(
                key="Jamie Jackson",
                n_claims=6,
                n_matched=5,
                match_rate=0.8333,
                avg_match_score=0.88,
            )
        }
        club_stats = {
            "Manchester United||Jamie Jackson": AggregateStat(
                key="Manchester United||Jamie Jackson",
                n_claims=4,
                n_matched=4,
                match_rate=1.0,
                avg_match_score=0.9,
            )
        }
        row = credibility_row(
            claim,
            match,
            config,
            source_stats,
            journalist_stats,
            club_stats,
            {"t1": {"date": "2025-08-07"}},
        )
        self.assertEqual(row["article_type"], "official")
        self.assertGreater(row["credibility_score"], 0.8)
        self.assertEqual(row["historical_support_n"], 14)
        self.assertNotIn("unmatched_claim", row["credibility_notes"])

    def test_credibility_row_penalizes_live_blog_noise(self):
        config = {
            "default_source_score": 0.5,
            "sources": {"The Guardian": 0.84},
        }
        claim = {
            "claim_id": "c5",
            "article_id": "a5",
            "published_at": "2025-08-06T10:00:00Z",
            "source": "The Guardian / Simon Burnton",
            "journalist": "Simon Burnton",
            "title": "Premier League clockwatch and transfer rumours live",
            "primary_player": "",
            "primary_club": "Manchester United",
            "rumor_stage": "unclear",
            "transfer_direction": "unclear",
            "is_transfer_related": 0,
        }
        row = credibility_row(
            claim,
            {},
            config,
            {},
            {},
            {},
            {},
        )
        self.assertEqual(row["article_type"], "live_blog")
        self.assertLessEqual(row["credibility_score"], 0.2)
        self.assertIn("not_transfer_related", row["credibility_notes"])
        self.assertIn("live_blog_penalty", row["credibility_notes"])

    def test_credibility_outputs_can_use_historical_stats_context(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            live_claims = base / "live_claims.jsonl"
            live_matches = base / "live_matches.csv"
            hist_claims = base / "hist_claims.jsonl"
            hist_matches = base / "hist_matches.csv"
            transfers = base / "transfers.csv"
            output_dir = base / "credibility"

            live_claims.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "claim_id": "live-1",
                                "article_id": "a1",
                                "published_at": "2026-05-20T10:00:00Z",
                                "source": "Trusted Source / Reporter One",
                                "journalist": "Reporter One",
                                "title": "Manchester United in advanced talks for Example Player",
                                "primary_player": "Example Player",
                                "primary_club": "Manchester United",
                                "rumor_stage": "advanced",
                                "transfer_direction": "in",
                                "is_transfer_related": 1,
                            }
                        )
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            hist_claims.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "claim_id": "hist-1",
                                "article_id": "a2",
                                "published_at": "2025-08-01T10:00:00Z",
                                "source": "Trusted Source / Reporter One",
                                "journalist": "Reporter One",
                                "title": "Manchester United agree deal for Example Player",
                                "primary_player": "Example Player",
                                "primary_club": "Manchester United",
                                "rumor_stage": "agreed",
                                "transfer_direction": "in",
                                "is_transfer_related": 1,
                            }
                        )
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            for path, rows in (
                (
                    live_matches,
                    [{"claim_id": "live-1", "matched_transfer_id": "", "match_score": "0.0", "match_reason": "unmatched", "ambiguity_flag": "0"}],
                ),
                (
                    hist_matches,
                    [{"claim_id": "hist-1", "matched_transfer_id": "transfer-1", "match_score": "0.92", "match_reason": "exact_player", "ambiguity_flag": "0"}],
                ),
            ):
                with path.open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=["claim_id", "matched_transfer_id", "match_score", "match_reason", "ambiguity_flag"],
                    )
                    writer.writeheader()
                    writer.writerows(rows)

            with transfers.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "date",
                        "original_transfer_date",
                        "event_date_source",
                        "event_date_confidence",
                        "season",
                        "club",
                        "player",
                        "direction",
                        "from_club",
                        "to_club",
                        "age",
                        "position",
                        "market_value_eur",
                        "transfer_fee_eur",
                        "wage_eur_annual",
                        "transfer_type",
                        "is_loan",
                        "source",
                        "source_url",
                    ],
                )
                writer.writeheader()

            outputs = credibility_outputs(
                live_claims,
                live_matches,
                transfers,
                output_dir,
                stats_claim_paths=[hist_claims],
                stats_match_paths=[hist_matches],
            )
            with outputs["scored_claims_csv"].open("r", encoding="utf-8", newline="") as handle:
                scored_rows = list(csv.DictReader(handle))
            self.assertEqual(len(scored_rows), 1)
            self.assertEqual(scored_rows[0]["journalist"], "Reporter One")
            self.assertEqual(scored_rows[0]["historical_support_n"], "4")

    def test_market_features_align_to_next_trading_day(self):
        dates = [
            date(2024, 1, 1),
            date(2024, 1, 2),
            date(2024, 1, 4),
            date(2024, 1, 5),
            date(2024, 1, 6),
            date(2024, 1, 7),
        ]
        stock_bars = [
            PriceBar(day, 100 + i, 100 + i, 100 + i, 100 + i, 1_000 + i * 10)
            for i, day in enumerate(dates)
        ]
        market_bars = [
            PriceBar(day, 200 + i, 200 + i, 200 + i, 200 + i, 2_000 + i * 10)
            for i, day in enumerate(dates)
        ]
        result = compute_market_features_for_event(
            date(2024, 1, 3),
            stock_bars,
            market_bars,
            estimation_days=2,
            gap_days=1,
            lookback_days=2,
        )
        self.assertEqual(result["event_trading_date"], "2024-01-04")
        self.assertEqual(result["event_trading_offset_days"], 1)

    def test_market_features_compute_positive_post_event_signal(self):
        start = date(2024, 1, 1)
        stock_bars = []
        market_bars = []
        stock_close = 100.0
        market_close = 100.0
        for i in range(45):
            day = start + timedelta(days=i)
            if i >= 30:
                stock_close *= 1.02
            volume = 2_500 if i == 30 else 1_000
            stock_bars.append(PriceBar(day, stock_close, stock_close, stock_close, stock_close, volume))
            market_bars.append(PriceBar(day, market_close, market_close, market_close, market_close, 1_500))
        result = compute_market_features_for_event(
            start + timedelta(days=30),
            stock_bars,
            market_bars,
            estimation_days=20,
            gap_days=3,
            lookback_days=20,
        )
        self.assertEqual(result["market_feature_status"], "ok")
        self.assertGreater(float(result["abnormal_return_0_p3"]), 0.05)
        self.assertEqual(result["target_label_p3"], "positive")
        self.assertGreater(float(result["relative_volume_20d"]), 2.0)

    def test_stage6_parse_datetime_handles_gdelt_and_iso(self):
        self.assertEqual(parse_datetime_to_date("20230607T170000Z"), date(2023, 6, 7))
        self.assertEqual(parse_datetime_to_date("2025-08-06T11:16:51Z"), date(2025, 8, 6))

    def test_stage6_usable_rows_uses_new_target(self):
        rows = [
            {"season": "2024-25", "market_feature_status": "ok", "target_label_p3": "positive", "prediction_scope": "direct"},
            {"season": "2024-25", "market_feature_status": "missing_stock_bars", "target_label_p3": "negative"},
            {"season": "2025-26", "market_feature_status": "ok", "target_label_p3": "", "prediction_scope": "direct"},
            {"season": "2025-26", "market_feature_status": "ok", "target_label_p3": "positive", "prediction_scope": "none"},
        ]
        usable = usable_rows_v2(rows, target_label_field="target_label_p3")
        self.assertEqual(len(usable), 1)
        self.assertEqual(usable[0]["target_label_p3"], "positive")

    def test_stage6_leaky_fields_exclude_post_event_targets(self):
        self.assertIn("abnormal_return_0_p3", LEAKY_FIELDS)
        self.assertIn("target_label_p3", LEAKY_FIELDS)
        self.assertIn("volatility_shift_20d", LEAKY_FIELDS)

    def test_backtest_candidate_selects_high_confidence_model_signal(self):
        row = {
            "split": "test",
            "event_trading_date": "2025-08-07",
            "club": "Manchester United",
            "player": "Benjamin Sesko",
            "predicted_label": "positive",
            "prob_positive": "0.72",
            "prob_negative": "0.11",
            "credibility_score": "0.81",
            "direction": "in",
            "rumor_stage": "agreed",
        }
        candidate = candidate_for_strategy(
            row,
            "model_long_positive",
            positive_threshold=0.55,
            negative_threshold=0.55,
            credibility_threshold=0.65,
        )
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.side, "long")
        self.assertGreater(candidate.score, 0.7)

    def test_backtest_dedupe_keeps_highest_score_per_club_day(self):
        rows = [
            {
                "split": "test",
                "event_trading_date": "2025-08-07",
                "club": "Manchester United",
                "player": "Player A",
                "predicted_label": "positive",
                "prob_positive": "0.60",
                "credibility_score": "0.70",
                "direction": "in",
                "rumor_stage": "advanced",
            },
            {
                "split": "test",
                "event_trading_date": "2025-08-07",
                "club": "Manchester United",
                "player": "Player B",
                "predicted_label": "positive",
                "prob_positive": "0.83",
                "credibility_score": "0.74",
                "direction": "in",
                "rumor_stage": "agreed",
            },
        ]
        candidates = [
            candidate_for_strategy(
                row,
                "model_long_positive",
                positive_threshold=0.55,
                negative_threshold=0.55,
                credibility_threshold=0.65,
            )
            for row in rows
        ]
        deduped = dedupe_candidates([item for item in candidates if item is not None])
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0].player, "Player B")

    def test_blended_signal_score_tracks_direction_and_model_edge(self):
        incoming = {
            "direction": "in",
            "transfer_indicator": "0.70",
            "credibility_score": "0.78",
            "rumor_stage_score": "0.82",
            "stock_context_indicator": "0.63",
            "prob_negative": "0.10",
            "prob_positive": "0.55",
        }
        outgoing = {
            **incoming,
            "direction": "out",
            "prob_negative": "0.58",
            "prob_positive": "0.09",
        }
        self.assertGreater(blended_signal_score(incoming), 0)
        self.assertLess(blended_signal_score(outgoing), 0)
        self.assertEqual(blended_signal_label(incoming), "positive")
        self.assertEqual(blended_signal_label(outgoing), "negative")

    def test_direct_target_rows_expand_buyer_and_seller_for_public_clubs(self):
        clubs = load_clubs()
        transfer = Transfer(
            date=date(2025, 7, 10),
            club="Juventus",
            player="Example Player",
            direction="in",
            from_club="Lazio",
            to_club="Juventus",
            age=24,
            position="Centre-Forward",
            market_value_eur=40_000_000,
            transfer_fee_eur=45_000_000,
            wage_eur_annual=7_000_000,
            source="test",
            source_url="",
            season="2025-26",
            transfer_type="permanent",
            is_loan=False,
        )
        base_row = {
            "club": transfer.club,
            "direction": transfer.direction,
            "player": transfer.player,
            "season": transfer.season,
            "transfer_type": transfer.transfer_type,
            "age": transfer.age,
            "position": transfer.position,
            "market_value_eur": transfer.market_value_eur,
            "transfer_fee_eur": transfer.transfer_fee_eur,
            "wage_eur_annual": transfer.wage_eur_annual,
        }
        rows = direct_target_rows(base_row, transfer, clubs)
        self.assertEqual(len(rows), 2)
        by_role = {row["target_role"]: row for row in rows}
        self.assertEqual(by_role["buyer"]["target_club"], "Juventus")
        self.assertEqual(by_role["buyer"]["direction"], "in")
        self.assertEqual(by_role["seller"]["target_club"], "Lazio")
        self.assertEqual(by_role["seller"]["direction"], "out")
        self.assertEqual(by_role["seller"]["prediction_scope"], "direct")
        self.assertEqual(by_role["seller"]["public_target_count"], 2)

    def test_direct_target_rows_keep_no_public_target_as_intelligence_only(self):
        clubs = load_clubs()
        transfer = Transfer(
            date=date(2025, 7, 10),
            club="Chelsea",
            player="Example Player",
            direction="in",
            from_club="Wolves",
            to_club="Chelsea",
            age=24,
            position="Centre-Forward",
            market_value_eur=40_000_000,
            transfer_fee_eur=45_000_000,
            wage_eur_annual=7_000_000,
            source="test",
            source_url="",
            season="2025-26",
            transfer_type="permanent",
            is_loan=False,
        )
        base_row = {"club": "Chelsea", "direction": "in", "player": "Example Player", "season": "2025-26"}
        rows = direct_target_rows(base_row, transfer, clubs)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["prediction_scope"], "none")
        self.assertEqual(rows[0]["target_club"], "")

    def test_demo_payload_exposes_multiple_seasons_and_target_scope(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            predictions_path = base / "predictions.csv"
            metrics_path = base / "metrics.json"
            backtest_summary_path = base / "backtests.csv"
            backtest_trades_path = base / "trades.csv"
            transfers_path = base / "transfers.csv"
            journalist_stats_path = base / "journalist_stats.csv"
            source_stats_path = base / "source_stats.csv"
            club_journalist_stats_path = base / "club_journalist_stats.csv"

            prediction_rows = [
                {
                    "claim_id": "c1",
                    "article_id": "a1",
                    "published_at": "2021-07-01T12:00:00Z",
                    "date": "2021-07-01",
                    "published_date": "2021-07-01",
                    "source": "example.com",
                    "journalist": "Reporter One",
                    "club": "Manchester United",
                    "player": "Jadon Sancho",
                    "season": "2021-22",
                    "direction": "in",
                    "transfer_type": "permanent",
                    "age": "21",
                    "position": "Left Winger",
                    "market_value_eur": "100000000",
                    "transfer_fee_eur": "85000000",
                    "credibility_score": "0.82",
                    "transfer_indicator": "0.71",
                    "rumor_indicator": "0.68",
                    "stock_context_indicator": "0.55",
                    "rumor_stage_score": "0.92",
                    "match_score": "0.95",
                    "entity_match_indicator": "0.95",
                    "rumor_stage": "official",
                    "split": "train",
                    "actual_label": "positive",
                    "predicted_label": "positive",
                    "prediction_confidence": "0.77",
                    "prob_negative": "0.08",
                    "prob_neutral": "0.20",
                    "prob_positive": "0.72",
                    "target_abnormal_return_p3": "0.041",
                    "pre_market_return_30d": "0.010",
                    "pre_volatility_20d": "0.021",
                },
                {
                    "claim_id": "c2",
                    "article_id": "a2",
                    "published_at": "2025-08-01T12:00:00Z",
                    "date": "2025-08-01",
                    "published_date": "2025-08-01",
                    "source": "example.com",
                    "journalist": "Reporter Two",
                    "club": "Juventus",
                    "player": "Example Out",
                    "season": "2025-26",
                    "direction": "out",
                    "transfer_type": "permanent",
                    "age": "24",
                    "position": "Centre-Forward",
                    "market_value_eur": "45000000",
                    "transfer_fee_eur": "52000000",
                    "credibility_score": "0.66",
                    "transfer_indicator": "0.48",
                    "rumor_indicator": "0.59",
                    "stock_context_indicator": "0.43",
                    "rumor_stage_score": "0.74",
                    "match_score": "0.88",
                    "entity_match_indicator": "0.88",
                    "rumor_stage": "advanced",
                    "split": "test",
                    "actual_label": "negative",
                    "predicted_label": "negative",
                    "prediction_confidence": "0.69",
                    "prob_negative": "0.67",
                    "prob_neutral": "0.18",
                    "prob_positive": "0.15",
                    "target_abnormal_return_p3": "-0.028",
                    "pre_market_return_30d": "-0.006",
                    "pre_volatility_20d": "0.026",
                },
            ]
            with predictions_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(prediction_rows[0].keys()))
                writer.writeheader()
                writer.writerows(prediction_rows)

            transfer_rows = [
                {
                    "date": "2021-07-01",
                    "original_transfer_date": "2021-07-01",
                    "event_date_source": "exact_transfer_date",
                    "event_date_confidence": "0.85",
                    "season": "2021-22",
                    "club": "Manchester United",
                    "player": "Jadon Sancho",
                    "direction": "in",
                    "from_club": "Borussia Dortmund",
                    "to_club": "Manchester United",
                    "age": "21",
                    "position": "Left Winger",
                    "market_value_eur": "100000000",
                    "transfer_fee_eur": "85000000",
                    "wage_eur_annual": "",
                    "transfer_type": "permanent",
                    "is_loan": "0",
                    "source": "test",
                    "source_url": "",
                },
                {
                    "date": "2025-08-01",
                    "original_transfer_date": "2025-08-01",
                    "event_date_source": "exact_transfer_date",
                    "event_date_confidence": "0.85",
                    "season": "2025-26",
                    "club": "Juventus",
                    "player": "Example Out",
                    "direction": "out",
                    "from_club": "Juventus",
                    "to_club": "Chelsea",
                    "age": "24",
                    "position": "Centre-Forward",
                    "market_value_eur": "45000000",
                    "transfer_fee_eur": "52000000",
                    "wage_eur_annual": "",
                    "transfer_type": "permanent",
                    "is_loan": "0",
                    "source": "test",
                    "source_url": "",
                },
            ]
            with transfers_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(transfer_rows[0].keys()))
                writer.writeheader()
                writer.writerows(transfer_rows)

            metrics_path.write_text(
                json.dumps(
                    {
                        "n_test_rows": 1,
                        "dataset_path": "data/processed/modeling/stage6_claims_market.csv",
                        "train_end_season": "2024-25",
                        "models": {"xgboost": {"test": {"accuracy": 0.47, "macro_f1": 0.31}}},
                    }
                ),
                encoding="utf-8",
            )
            with backtest_summary_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["strategy", "n_trades", "win_rate", "avg_trade_return", "portfolio_total_return", "sharpe_like", "max_drawdown"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "strategy": "heuristic_long_short",
                        "n_trades": "4",
                        "win_rate": "0.5",
                        "avg_trade_return": "0.01",
                        "portfolio_total_return": "0.04",
                        "sharpe_like": "1.2",
                        "max_drawdown": "-0.02",
                    }
                )
            with backtest_trades_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["club", "player", "trade_return"])
                writer.writeheader()
                writer.writerow({"club": "Juventus", "player": "Example Out", "trade_return": "-0.028"})

            with journalist_stats_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["journalist", "n_claims", "n_matched", "match_rate", "smoothed_rate", "avg_match_score"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "journalist": "Reporter One",
                        "n_claims": "8",
                        "n_matched": "6",
                        "match_rate": "0.75",
                        "smoothed_rate": "0.71",
                        "avg_match_score": "0.86",
                    }
                )

            with source_stats_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["source", "n_claims", "n_matched", "match_rate", "smoothed_rate", "avg_match_score"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "source": "example.com",
                        "n_claims": "12",
                        "n_matched": "8",
                        "match_rate": "0.6667",
                        "smoothed_rate": "0.69",
                        "avg_match_score": "0.81",
                    }
                )

            with club_journalist_stats_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["club", "journalist", "n_claims", "n_matched", "match_rate", "smoothed_rate", "avg_match_score"],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "club": "Manchester United",
                        "journalist": "Reporter One",
                        "n_claims": "4",
                        "n_matched": "3",
                        "match_rate": "0.75",
                        "smoothed_rate": "0.73",
                        "avg_match_score": "0.84",
                    }
                )

            payload = build_demo_payload(
                predictions_path,
                metrics_path,
                backtest_summary_path,
                backtest_trades_path,
                transfers_path=transfers_path,
                journalist_stats_path=journalist_stats_path,
                source_stats_path=source_stats_path,
                club_journalist_stats_path=club_journalist_stats_path,
            )

            self.assertEqual(payload["latest_season"], "2025-26")
            self.assertEqual(payload["available_seasons"], ["2025-26", "2021-22"])
            self.assertIn("2021-22", payload["signals_by_season"])
            self.assertIn("2025-26", payload["season_summaries"])
            self.assertEqual(payload["season_summaries"]["2021-22"]["signal_count"], 1)

            latest_signal = payload["current_signals"][0]
            self.assertEqual(latest_signal["target_club"], "Juventus")
            self.assertEqual(latest_signal["target_role"], "seller")
            self.assertEqual(latest_signal["prediction_scope"], "direct")
            self.assertEqual(latest_signal["target_ticker"], "JUVE.MI")
            self.assertEqual(payload["live_watchlist"][0]["group_key"], latest_signal["group_key"])
            self.assertIn("days_stale", payload["live_watchlist_meta"])
            self.assertEqual(payload["leaderboards"]["journalists"][0]["journalist"], "Reporter One")
            self.assertEqual(payload["leaderboards"]["sources"][0]["source"], "example.com")
            self.assertEqual(payload["leaderboards"]["club_journalists"][0]["club"], "Manchester United")


if __name__ == "__main__":
    unittest.main()
