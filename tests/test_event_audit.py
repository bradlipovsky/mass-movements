import csv
import unittest
from datetime import datetime, timezone

from scripts import check_event_audit as audit


class EventAuditEquationTest(unittest.TestCase):
    def test_positive_and_negative_utc_offsets(self):
        self.assertEqual(
            audit.converted_utc("2016-09-21T05:00:00", 480),
            datetime(2016, 9, 20, 21, tzinfo=timezone.utc),
        )
        self.assertEqual(
            audit.converted_utc("2015-10-17T20:00:00", -540),
            datetime(2015, 10, 18, 5, tzinfo=timezone.utc),
        )

    def test_dst_offsets_can_differ_across_interval(self):
        lower = audit.converted_utc("2022-03-27T00:00:00", 60)
        upper = audit.converted_utc("2022-03-28T00:00:00", 120)
        self.assertEqual((upper - lower).total_seconds(), 23 * 3600)

    def test_leap_day_and_half_open_precision(self):
        lower = audit.converted_utc("2024-02-29T12:34:00", 0)
        upper = audit.converted_utc("2024-02-29T12:35:00", 0)
        self.assertEqual((upper - lower).total_seconds(), 60)
        self.assertLess(lower, upper)

    def test_interval_overlap_identifies_conflict(self):
        self.assertTrue(audit.intervals_overlap(
            "2020-01-01T00:00:00Z", "2020-01-01T01:00:00Z",
            "2020-01-01T00:30:00Z", "2020-01-01T02:00:00Z",
        ))
        self.assertFalse(audit.intervals_overlap(
            "2020-01-01T00:00:00Z", "2020-01-01T01:00:00Z",
            "2020-01-01T01:00:00Z", "2020-01-01T02:00:00Z",
        ))

    def test_uncertainty_classes(self):
        self.assertEqual(audit.uncertainty_class(100), "le_100_m")
        self.assertEqual(audit.uncertainty_class(101), "le_1_km")
        self.assertEqual(audit.uncertainty_class(5000), "le_5_km")
        self.assertEqual(audit.uncertainty_class(5001), "gt_5_km_or_unknown")


class EventAuditArtifactTest(unittest.TestCase):
    def test_registered_tables_and_manifest(self):
        errors, summary, coordinates, times, sources = audit.validate_rows()
        audit.validate_manifest(errors)
        self.assertEqual(errors, [])
        self.assertEqual(len(summary), 53)
        self.assertEqual(len({row["candidate_id"] for row in summary}), 53)
        self.assertEqual((len(coordinates), len(times), len(sources)), (0, 0, 0))

    def test_review_tables_have_no_climate_fields(self):
        forbidden = {"temperature", "rank", "reanalysis", "permafrost", "glacier_change"}
        for path in audit.FILES.values():
            with path.open(newline="", encoding="utf-8") as handle:
                fields = set(csv.DictReader(handle).fieldnames or [])
            self.assertTrue(fields.isdisjoint(forbidden), (path, fields & forbidden))


if __name__ == "__main__":
    unittest.main()
