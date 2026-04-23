"""Unit tests for parseri.py."""

import os
import sys
import tempfile

import pytest
import yaml

# Ensure parseri package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from parseri import (
    _make_name_tuple,
    calculatePoints,
    calculateTotalPoints,
    findNamesFromResults,
    formatTime,
    formatTimeDiff,
    getMinPoints,
    normalizeEventData,
    parseResults,
    resolveAutoParticipants,
    sortByTime,
    updatePointsForParticipants,
)


# ---------------------------------------------------------------------------
# formatTime
# ---------------------------------------------------------------------------

class TestFormatTime:
    def test_minutes_seconds_dot(self):
        t = formatTime("24.49")
        assert t.minute == 24
        assert t.second == 49

    def test_minutes_seconds_colon(self):
        t = formatTime("24:49")
        assert t.minute == 24
        assert t.second == 49

    def test_hours_minutes_seconds_dot(self):
        t = formatTime("1.02.30")
        assert t.hour == 1
        assert t.minute == 2
        assert t.second == 30

    def test_hours_minutes_seconds_colon(self):
        t = formatTime("1:02:30")
        assert t.hour == 1
        assert t.minute == 2
        assert t.second == 30

    def test_empty_string_returns_none(self):
        assert formatTime("") is None

    def test_whitespace_only_returns_none(self):
        assert formatTime("   ") is None


# ---------------------------------------------------------------------------
# formatTimeDiff
# ---------------------------------------------------------------------------

class TestFormatTimeDiff:
    def test_zero(self):
        assert formatTimeDiff(0) == "+0"

    def test_positive_seconds(self):
        assert formatTimeDiff(45) == "+45"

    def test_negative_seconds(self):
        assert formatTimeDiff(-30) == "-30"

    def test_minutes_and_seconds(self):
        assert formatTimeDiff(125) == "+2.05"

    def test_hours_minutes_seconds(self):
        assert formatTimeDiff(3661) == "+1.01.01"

    def test_negative_with_minutes(self):
        assert formatTimeDiff(-90) == "-1.30"


# ---------------------------------------------------------------------------
# parseResults
# ---------------------------------------------------------------------------

class TestParseResults:
    def test_basic_results_with_timediff(self):
        data = "1. Karhu Otso 24.49 +0.00\n2. Niemi Tero 25.10 +0.21\n"
        results = parseResults(data)
        assert len(results) == 2
        assert ("Karhu", "Otso") in results
        assert ("Niemi", "Tero") in results
        assert results[("Karhu", "Otso")]["pos"] == "1."
        assert results[("Karhu", "Otso")]["timediff"] == "+0.00"
        assert results[("Niemi", "Tero")]["timediff"] == "+0.21"

    def test_basic_results_without_timediff(self):
        data = "1. Karhu Otso 24.49\n2. Niemi Tero 25.10\n"
        results = parseResults(data)
        assert len(results) == 2
        assert results[("Karhu", "Otso")]["time"].minute == 24

    def test_dnf_with_dash(self):
        data = "1. Karhu Otso 24.49 +0.00\n- Niemi Tero - -\n"
        results = parseResults(data)
        assert results[("Niemi", "Tero")]["time"] is None
        assert results[("Niemi", "Tero")]["pos"] == "-"

    def test_dnf_ei_aikaa(self):
        data = "Niemi Tero ei aikaa\n"
        results = parseResults(data)
        assert ("Niemi", "Tero") in results
        assert results[("Niemi", "Tero")]["time"] is None
        assert results[("Niemi", "Tero")]["pos"] == "-"

    def test_dnf_ei_aikaa_with_position(self):
        data = "4. Niemi Tero ei aikaa\n"
        results = parseResults(data)
        assert ("Niemi", "Tero") in results
        assert results[("Niemi", "Tero")]["time"] is None

    def test_dnf_ei_aikaa_with_team(self):
        data = "- Niemi Tero TeamX ei aikaa\n"
        results = parseResults(data)
        assert results[("Niemi", "Tero")]["team"] == "TeamX"

    def test_result_with_team(self):
        data = "1. Karhu Otso TeamA 24.49 +0.00\n"
        results = parseResults(data)
        assert results[("Karhu", "Otso")]["team"] == "TeamA"

    def test_empty_lines_skipped(self):
        data = "\n\n1. Karhu Otso 24.49\n\n"
        results = parseResults(data)
        assert len(results) == 1

    def test_time_with_hours(self):
        data = "1. Karhu Otso 1.02.30\n"
        results = parseResults(data)
        t = results[("Karhu", "Otso")]["time"]
        assert t.hour == 1
        assert t.minute == 2
        assert t.second == 30


# ---------------------------------------------------------------------------
# _make_name_tuple
# ---------------------------------------------------------------------------

class TestMakeNameTuple:
    def test_normal_order(self):
        assert _make_name_tuple({"last": "Karhu", "first": "Otso"}, False) == ("Karhu", "Otso")

    def test_reverse_order(self):
        assert _make_name_tuple({"last": "Karhu", "first": "Otso"}, True) == ("Otso", "Karhu")


# ---------------------------------------------------------------------------
# findNamesFromResults
# ---------------------------------------------------------------------------

class TestFindNamesFromResults:
    def _make_results(self, data):
        return parseResults(data)

    def test_exact_match(self):
        results = self._make_results("1. Karhu Otso 24.49\n")
        participants = [{"last": "Karhu", "first": "Otso"}]
        found = findNamesFromResults(participants, results, False, False)
        assert len(found) == 1
        assert found[0]["last"] == "Karhu"
        assert found[0]["first"] == "Otso"

    def test_no_match(self):
        results = self._make_results("1. Karhu Otso 24.49\n")
        participants = [{"last": "Niemi", "first": "Tero"}]
        found = findNamesFromResults(participants, results, False, False)
        assert len(found) == 0

    def test_reverse_names(self):
        results = self._make_results("1. Otso Karhu 24.49\n")
        participants = [{"last": "Karhu", "first": "Otso"}]
        found = findNamesFromResults(participants, results, True, False)
        assert len(found) == 1
        assert found[0]["last"] == "Karhu"

    def test_alias_match(self):
        results = self._make_results("1. Karhuu Otso 24.49\n")
        participants = [{"last": "Karhu", "first": "Otso",
                         "aliases": [{"last": "Karhuu", "first": "Otso"}]}]
        found = findNamesFromResults(participants, results, False, False)
        assert len(found) == 1
        assert found[0]["last"] == "Karhu"  # Main name, not alias

    def test_no_match_without_alias_field(self):
        results = self._make_results("1. Karhuu Otso 24.49\n")
        participants = [{"last": "Karhu", "first": "Otso"}]
        found = findNamesFromResults(participants, results, False, False)
        assert len(found) == 0

    def test_main_name_priority_over_alias(self):
        results = self._make_results(
            "1. Karhu Otso 24.49\n2. Karhuu Otso 30.00\n"
        )
        participants = [{"last": "Karhu", "first": "Otso",
                         "aliases": [{"last": "Karhuu", "first": "Otso"}]}]
        found = findNamesFromResults(participants, results, False, False)
        assert len(found) == 1
        assert found[0]["time"].minute == 24  # Main name's time

    def test_alias_with_reverse_names(self):
        results = self._make_results("1. Otso Karhuu 24.49\n")
        participants = [{"last": "Karhu", "first": "Otso",
                         "aliases": [{"last": "Karhuu", "first": "Otso"}]}]
        found = findNamesFromResults(participants, results, True, False)
        assert len(found) == 1
        assert found[0]["last"] == "Karhu"

    def test_multiple_aliases(self):
        results = self._make_results("1. Bear Otso 24.49\n")
        participants = [{"last": "Karhu", "first": "Otso",
                         "aliases": [
                             {"last": "Karhuu", "first": "Otso"},
                             {"last": "Bear", "first": "Otso"},
                         ]}]
        found = findNamesFromResults(participants, results, False, False)
        assert len(found) == 1
        assert found[0]["last"] == "Karhu"

    def test_multiple_participants_mixed(self):
        results = self._make_results(
            "1. Karhuu Otso 24.49\n2. Niemi Tero 25.10\n"
        )
        participants = [
            {"last": "Karhu", "first": "Otso",
             "aliases": [{"last": "Karhuu", "first": "Otso"}]},
            {"last": "Niemi", "first": "Tero"},
        ]
        found = findNamesFromResults(participants, results, False, False)
        assert len(found) == 2

    def test_close_matches_reported(self, capsys):
        results = self._make_results("1. Karhune Otso 24.49\n")
        participants = [{"last": "Karhun", "first": "Otso"}]
        found = findNamesFromResults(participants, results, False, True)
        assert len(found) == 0
        captured = capsys.readouterr()
        assert "close matches" in captured.out.lower()

    def test_dnf_result_matched(self):
        results = self._make_results("Karhu Otso ei aikaa\n")
        participants = [{"last": "Karhu", "first": "Otso"}]
        found = findNamesFromResults(participants, results, False, False)
        assert len(found) == 1
        assert found[0]["time"] is None

    def test_backward_compatible_no_aliases(self):
        results = self._make_results("1. Karhu Otso 24.49\n2. Niemi Tero 25.10\n")
        participants = [
            {"last": "Karhu", "first": "Otso"},
            {"last": "Niemi", "first": "Tero"},
        ]
        found = findNamesFromResults(participants, results, False, False)
        assert len(found) == 2


# ---------------------------------------------------------------------------
# sortByTime
# ---------------------------------------------------------------------------

class TestSortByTime:
    def test_sorts_by_time(self):
        a = {"time": formatTime("25.10"), "first": "A", "last": "A"}
        b = {"time": formatTime("24.49"), "first": "B", "last": "B"}
        result = sortByTime([a, b])
        assert result[0]["first"] == "B"
        assert result[1]["first"] == "A"

    def test_none_time_sorted_last(self):
        a = {"time": formatTime("25.10"), "first": "A", "last": "A"}
        b = {"time": None, "first": "B", "last": "B"}
        result = sortByTime([a, b])
        assert result[0]["first"] == "A"
        assert result[1]["first"] == "B"


# ---------------------------------------------------------------------------
# calculatePoints
# ---------------------------------------------------------------------------

class TestCalculatePoints:
    def _participant(self, first, last, time_str):
        return {
            "first": first,
            "last": last,
            "time": formatTime(time_str) if time_str else None,
        }

    def test_winner_gets_1000_below_threshold(self):
        p = [self._participant("A", "Aa", "24.49"),
             self._participant("B", "Bb", "25.10")]
        calculatePoints(p, threshold=6, reference=3)
        sorted_p = sortByTime(p)
        assert sorted_p[0]["points"] == 1000

    def test_reference_position_gets_1000(self):
        participants = [
            self._participant("A", "Aa", "20.00"),
            self._participant("B", "Bb", "22.00"),
            self._participant("C", "Cc", "24.00"),
            self._participant("D", "Dd", "25.00"),
            self._participant("E", "Ee", "26.00"),
            self._participant("F", "Ff", "27.00"),
        ]
        calculatePoints(participants, threshold=6, reference=3)
        sorted_p = sortByTime(participants)
        assert sorted_p[2]["points"] == 1000  # 3rd place

    def test_dnf_gets_minimum_points(self):
        p = [self._participant("A", "Aa", "24.49"),
             self._participant("B", "Bb", None)]
        calculatePoints(p, threshold=6, reference=3)
        dnf = [x for x in p if x["time"] is None][0]
        assert dnf["points"] == getMinPoints()

    def test_winner_capped_at_1050(self):
        # Winner much faster than 3rd place → should be capped
        participants = [
            self._participant("A", "Aa", "10.00"),
            self._participant("B", "Bb", "19.00"),
            self._participant("C", "Cc", "20.00"),
            self._participant("D", "Dd", "25.00"),
            self._participant("E", "Ee", "26.00"),
            self._participant("F", "Ff", "27.00"),
        ]
        calculatePoints(participants, threshold=6, reference=3)
        sorted_p = sortByTime(participants)
        assert sorted_p[0]["points"] == 1050

    def test_slower_than_reference_loses_one_per_10s(self):
        participants = [
            self._participant("A", "Aa", "20.00"),
            self._participant("B", "Bb", "20.10"),  # 10s slower
            self._participant("C", "Cc", "20.20"),  # 20s slower
        ]
        calculatePoints(participants, threshold=1, reference=1)
        sorted_p = sortByTime(participants)
        # Winner = reference = 1000
        assert sorted_p[0]["points"] == 1000
        assert sorted_p[1]["points"] == 999  # -1 point per 10s
        assert sorted_p[2]["points"] == 998

    def test_minimum_points_floor(self):
        # Very slow participant still gets minimum
        participants = [
            self._participant("A", "Aa", "10.00"),
            self._participant("B", "Bb", "59.59"),  # Very slow
        ]
        calculatePoints(participants, threshold=6, reference=3)
        sorted_p = sortByTime(participants)
        assert sorted_p[1]["points"] >= getMinPoints()

    def test_positions_assigned(self):
        p = [self._participant("A", "Aa", "25.10"),
             self._participant("B", "Bb", "24.49")]
        calculatePoints(p, threshold=6, reference=3)
        sorted_p = sortByTime(p)
        assert sorted_p[0]["pos"] == "1."
        assert sorted_p[1]["pos"] == "2."

    def test_dnf_position_is_dash(self):
        p = [self._participant("A", "Aa", "24.49"),
             self._participant("B", "Bb", None)]
        calculatePoints(p, threshold=6, reference=3)
        dnf = [x for x in p if x["time"] is None][0]
        assert dnf["pos"] == "-"


# ---------------------------------------------------------------------------
# updatePointsForParticipants
# ---------------------------------------------------------------------------

class TestUpdatePointsForParticipants:
    def test_points_stored_on_participant(self):
        participants = [{"first": "Otso", "last": "Karhu"}]
        points = [{"first": "Otso", "last": "Karhu", "points": 1000}]
        updatePointsForParticipants(participants, points, eventId=1, wrongTrack=False)
        assert participants[0]["points"][1] == {"count": 1000, "wrongTrack": False}

    def test_wrong_track_flag(self):
        participants = [{"first": "Otso", "last": "Karhu"}]
        points = [{"first": "Otso", "last": "Karhu", "points": 500}]
        updatePointsForParticipants(participants, points, eventId=2, wrongTrack=True)
        assert participants[0]["points"][2]["wrongTrack"] is True

    def test_multiple_events(self):
        participants = [{"first": "Otso", "last": "Karhu"}]
        points1 = [{"first": "Otso", "last": "Karhu", "points": 1000}]
        points2 = [{"first": "Otso", "last": "Karhu", "points": 950}]
        updatePointsForParticipants(participants, points1, eventId=1, wrongTrack=False)
        updatePointsForParticipants(participants, points2, eventId=2, wrongTrack=False)
        assert participants[0]["points"][1]["count"] == 1000
        assert participants[0]["points"][2]["count"] == 950


# ---------------------------------------------------------------------------
# calculateTotalPoints
# ---------------------------------------------------------------------------

class TestCalculateTotalPoints:
    def test_sums_best_n_events(self):
        config = {
            "max_number_of_results": 2,
            "series": {
                "A": {
                    "participants": [{
                        "first": "Otso", "last": "Karhu",
                        "points": {
                            1: {"count": 1000, "wrongTrack": False},
                            2: {"count": 900, "wrongTrack": False},
                            3: {"count": 950, "wrongTrack": False},
                        }
                    }]
                }
            }
        }
        calculateTotalPoints(config)
        p = config["series"]["A"]["participants"][0]
        # Best 2: 1000 + 950 = 1950
        assert p["total_points"] == 1950

    def test_excludes_x_points(self):
        config = {
            "max_number_of_results": 2,
            "series": {
                "A": {
                    "participants": [{
                        "first": "Otso", "last": "Karhu",
                        "points": {
                            1: {"count": 1000, "wrongTrack": False},
                            2: {"count": "X", "wrongTrack": True},
                            3: {"count": 800, "wrongTrack": False},
                        }
                    }]
                }
            }
        }
        calculateTotalPoints(config)
        p = config["series"]["A"]["participants"][0]
        assert p["total_points"] == 1800

    def test_marks_used_events(self):
        config = {
            "max_number_of_results": 1,
            "series": {
                "A": {
                    "participants": [{
                        "first": "Otso", "last": "Karhu",
                        "points": {
                            1: {"count": 1000, "wrongTrack": False},
                            2: {"count": 900, "wrongTrack": False},
                        }
                    }]
                }
            }
        }
        calculateTotalPoints(config)
        p = config["series"]["A"]["participants"][0]
        assert p["points"][1].get("used") is True
        assert p["points"][2].get("used") is None

    def test_no_points_no_crash(self):
        config = {
            "max_number_of_results": 3,
            "series": {
                "A": {
                    "participants": [{"first": "Otso", "last": "Karhu"}]
                }
            }
        }
        calculateTotalPoints(config)
        # Should not crash, no total_points set


# ---------------------------------------------------------------------------
# normalizeEventData
# ---------------------------------------------------------------------------

class TestNormalizeEventData:
    def test_new_format_passthrough(self):
        data = {
            "tracks": {"A-rata": {"length": "5km", "data": "..."}},
            "series_mapping": {"pitkä": "A-rata"},
        }
        result = normalizeEventData(data)
        assert result is data

    def test_old_format_converted(self):
        data = {
            "series": {
                "pitkä": {"track": "A-rata", "length": "5km", "data": "result data"},
                "lyhyt": {"track": "B-rata", "length": "3km", "data": "result data 2"},
            }
        }
        result = normalizeEventData(data)
        assert "tracks" in result
        assert "series_mapping" in result
        assert result["series_mapping"]["pitkä"] == "A-rata"
        assert result["tracks"]["A-rata"]["length"] == "5km"
        assert result["tracks"]["A-rata"]["data"] == "result data"

    def test_old_format_with_other_tracks(self):
        data = {
            "series": {
                "pitkä": {"track": "A", "length": "5km", "data": "..."},
                "other": {
                    "C-rata": "other data",
                }
            }
        }
        result = normalizeEventData(data)
        assert "C-rata" in result["tracks"]
        assert result["tracks"]["C-rata"]["data"] == "other data"


# ---------------------------------------------------------------------------
# resolveAutoParticipants
# ---------------------------------------------------------------------------

class TestResolveAutoParticipants:
    def _setup_auto_config(self, tmpdir, auto_participants, events):
        """Create config and source files for auto-resolution testing."""
        sources = os.path.join(tmpdir, "sources")
        os.makedirs(sources, exist_ok=True)

        config = {
            "year": 2026,
            "name": "test",
            "max_number_of_results": 6,
            "number_of_events": len(events),
            "series": {
                "auto": {"participants": auto_participants},
                "pitkä": {"participant_threshold": 3, "reference_position": 1},
                "lyhyt": {"participant_threshold": 3, "reference_position": 1},
            }
        }

        for event in events:
            filepath = os.path.join(sources, event["filename"])
            event_data = {
                "event_number": event.get("event_number", 1),
                "location": "Test",
                "date": "1.1.",
                "organizer": "Test",
                "reverse_names": event.get("reverse_names", False),
                "series_mapping": event["series_mapping"],
                "tracks": event["tracks"],
            }
            with open(filepath, "w", encoding="utf-8") as f:
                yaml.dump(event_data, f)

        return config, sources

    def test_assigns_to_most_frequent_series(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config, sources = self._setup_auto_config(tmpdir,
                auto_participants=[{"last": "Karhu", "first": "Otso"}],
                events=[
                    {"filename": "01_test.yaml", "event_number": 1,
                     "series_mapping": {"pitkä": "A", "lyhyt": "B"},
                     "tracks": {
                         "A": {"data": "1. Karhu Otso 24.49\n"},
                         "B": {"data": "1. Niemi Tero 30.00\n"},
                     }},
                    {"filename": "02_test.yaml", "event_number": 2,
                     "series_mapping": {"pitkä": "A", "lyhyt": "B"},
                     "tracks": {
                         "A": {"data": "1. Karhu Otso 25.00\n"},
                         "B": {"data": "1. Niemi Tero 31.00\n"},
                     }},
                ])

            resolveAutoParticipants(config, sources)
            assert "auto" not in config["series"]
            pitkä_names = [(p["last"], p["first"]) for p in config["series"]["pitkä"]["participants"]]
            assert ("Karhu", "Otso") in pitkä_names

    def test_alias_counted_in_auto(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config, sources = self._setup_auto_config(tmpdir,
                auto_participants=[{
                    "last": "Karhu", "first": "Otso",
                    "aliases": [{"last": "Karhuu", "first": "Otso"}],
                }],
                events=[
                    {"filename": "01_test.yaml", "event_number": 1,
                     "series_mapping": {"pitkä": "A", "lyhyt": "B"},
                     "tracks": {
                         "A": {"data": "1. Karhuu Otso 24.49\n"},
                         "B": {"data": "1. Niemi Tero 30.00\n"},
                     }},
                ])

            resolveAutoParticipants(config, sources)
            pitkä_names = [(p["last"], p["first"]) for p in config["series"]["pitkä"]["participants"]]
            assert ("Karhu", "Otso") in pitkä_names

    def test_no_auto_series_noop(self):
        config = {
            "series": {
                "pitkä": {"participant_threshold": 3, "reference_position": 1, "participants": []},
            }
        }
        resolveAutoParticipants(config, "/nonexistent")
        assert "pitkä" in config["series"]

    def test_no_appearances_not_assigned(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config, sources = self._setup_auto_config(tmpdir,
                auto_participants=[{"last": "Nobody", "first": "Person"}],
                events=[
                    {"filename": "01_test.yaml", "event_number": 1,
                     "series_mapping": {"pitkä": "A", "lyhyt": "B"},
                     "tracks": {
                         "A": {"data": "1. Karhu Otso 24.49\n"},
                         "B": {"data": "1. Niemi Tero 30.00\n"},
                     }},
                ])

            resolveAutoParticipants(config, sources)
            all_participants = (
                config["series"]["pitkä"]["participants"]
                + config["series"]["lyhyt"]["participants"]
            )
            names = [(p["last"], p["first"]) for p in all_participants]
            assert ("Nobody", "Person") not in names


# ---------------------------------------------------------------------------
# Integration: end-to-end points calculation
# ---------------------------------------------------------------------------

class TestIntegration:
    def test_full_event_flow(self):
        """Parse results → find names → calculate points → sum totals."""
        data = (
            "1. Karhu Otso 20.00\n"
            "2. Niemi Tero 20.30\n"
            "3. Lehto Matti 21.00\n"
        )
        results = parseResults(data)
        participants_cfg = [
            {"last": "Karhu", "first": "Otso"},
            {"last": "Niemi", "first": "Tero"},
            {"last": "Lehto", "first": "Matti"},
        ]

        found = findNamesFromResults(participants_cfg, results, False, False)
        assert len(found) == 3

        calculatePoints(found, threshold=3, reference=2)
        sorted_found = sortByTime(found)

        # 2nd place = reference = 1000
        assert sorted_found[1]["points"] == 1000
        # 1st place > 1000
        assert sorted_found[0]["points"] > 1000
        # 3rd place < 1000
        assert sorted_found[2]["points"] < 1000

    def test_alias_in_full_flow(self):
        """Alias name in results gets matched and scored under main name."""
        data = "1. Karhuu Otso 20.00\n2. Niemi Tero 20.30\n"
        results = parseResults(data)
        participants_cfg = [
            {"last": "Karhu", "first": "Otso",
             "aliases": [{"last": "Karhuu", "first": "Otso"}]},
            {"last": "Niemi", "first": "Tero"},
        ]

        found = findNamesFromResults(participants_cfg, results, False, False)
        assert len(found) == 2
        assert found[0]["last"] == "Karhu"

        calculatePoints(found, threshold=6, reference=3)
        assert found[0]["points"] == 1000  # Winner below threshold
