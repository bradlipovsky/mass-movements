import hashlib, json, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import audited_reanalysis as ar  # noqa: E402

class AuditedPopulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.eligibility, cls.selected = ar.analysis_frame()
        cls.cells = ar.build_cells(cls.selected)

    def test_exact_blind_selection(self):
        self.assertEqual((len(self.eligibility), len(self.selected)), (53, 22))
        self.assertEqual(self.selected.onset_role.value_counts().to_dict(),
                         {"source_failure": 16, "trigger_proxy": 6})
        self.assertEqual(self.selected.dependence_component.nunique(), 18)
        self.assertEqual(int(self.selected.old_pilot_overlap.sum()), 9)
        self.assertEqual(self.selected.coordinate_uncertainty_class.value_counts().to_dict(),
                         {"le_1_km": 19, "le_5_km": 3})
        ids = "\n".join(sorted(self.selected.candidate_id)) + "\n"
        self.assertEqual(hashlib.sha256(ids.encode()).hexdigest(), ar.SELECTED_DIGEST)
        self.assertEqual(set(self.eligibility.exclusion_reason[self.eligibility.selected]), {"selected"})
        self.assertTrue((self.eligibility.exclusion_reason[~self.eligibility.selected].str.len() > 20).all())

    def test_coordinate_assertion_corruption_stops(self):
        candidates = pd.read_csv(ROOT/"data/candidates.csv", dtype=str).fillna("")
        audit = pd.read_csv(ROOT/"data/event_audit/summary.csv", dtype=str).fillna("")
        base = candidates.query("consensus_decision == 'include' and trigger_time_eligible == 'yes'").merge(audit)
        base = base[(base.coordinate_status == "accepted") & (base.time_status == "accepted")]
        coordinates = pd.read_csv(ROOT/"data/event_audit/coordinate_assertions.csv", dtype=str).fillna("")
        ar.join_coordinates(base, coordinates)
        target = coordinates.assertion_id == base.iloc[0].coordinate_assertion_id
        for column, value in (("geometry_role", "deposit"), ("latitude_deg", "0")):
            corrupt = coordinates.copy(); corrupt.loc[target, column] = value
            with self.assertRaisesRegex(ValueError, "coordinate assertion mismatch"):
                ar.join_coordinates(base, corrupt)

    def test_conservative_anchors(self):
        lower = pd.to_datetime(self.selected.onset_lower_utc, utc=True, format="mixed")
        anchor = pd.to_datetime(self.selected.onset_anchor_utc, utc=True)
        gap = (lower-anchor).dt.total_seconds()
        self.assertTrue(((gap >= 0) & (gap < 3600)).all())
        self.assertTrue(np.allclose(gap, self.selected.quantization_gap_seconds))
        time0 = np.datetime64("1940-01-01T00:00:00")
        idx = ar.indices(time0, "2023-09-16T12:00:00Z", 2023, 168)
        stop = int((np.datetime64("2023-09-16T12")-time0)/np.timedelta64(1, "h"))
        self.assertEqual((len(idx), idx[-1]), (168, stop-1))
        self.assertIsNone(ar.indices(time0, "2020-02-29T00:00:00Z", 2019, 48))

    def test_four_cells_and_temperature_blind_primary_rule(self):
        self.assertEqual(len(self.cells), 88)
        self.assertTrue((self.cells.groupby("candidate_id").size() == 4).all())
        self.assertEqual(int(self.cells.primary_cell.sum()), 22)
        for _, group in self.cells.groupby("candidate_id"):
            expected = group.sort_values(["land_fraction", "distance_km", "grid_latitude_deg",
                                          "grid_longitude_deg_east"],
                                         ascending=[False, True, True, True]).iloc[0]
            self.assertTrue(bool(expected.primary_cell))

    def test_preaccess_artifacts_and_hash_gate(self):
        manifest_path = ar.OUT / "preaccess_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        self.assertEqual(manifest["status"], "pre_event_temperature_access_v1")
        self.assertEqual(manifest["population"], {"frame": 53, "selected": 22,
            "source_failure": 16, "trigger_proxy": 6, "components": 18,
            "old_pilot_overlap": 9, "cells": 88, "unique_grid_points": 73})
        for name, record in manifest["files"].items():
            path = ROOT/name
            self.assertEqual((path.stat().st_size, ar.sha256(path)), (record["bytes"], record["sha256"]))
        digest = ar.sha256(manifest_path)
        self.assertEqual(ar.verify_gate(manifest_path, digest)["selected_id_sha256"], ar.SELECTED_DIGEST)
        self.assertEqual(manifest["python"], ar.platform.python_version())
        with mock.patch.object(ar.platform, "python_version", return_value="0"):
            with self.assertRaisesRegex(ValueError, "runtime drift: python"): ar.verify_gate(manifest_path, digest)
        with self.assertRaisesRegex(ValueError, "approved digest"):
            ar.verify_gate(manifest_path, "0"*64)
        self.assertFalse(ar.RESULTS.exists())

class AuditedEquationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _, cls.selected = ar.analysis_frame(); cls.cells = ar.build_cells(cls.selected)

    def test_schema_row_and_column_stops(self):
        table = pd.read_csv(ar.OUT/"eligibility.csv")
        ar.cast_and_check("eligibility.csv", table)
        with self.assertRaisesRegex(ValueError, "schema mismatch"):
            ar.cast_and_check("eligibility.csv", table.iloc[:-1].copy())
        with self.assertRaisesRegex(ValueError, "schema mismatch"):
            ar.cast_and_check("eligibility.csv", table.rename(columns={"selected": "choice"}))

    def test_diagnostic_conservation_and_contrast_isolation(self):
        rows = []
        event_year = self.selected.set_index("candidate_id").event_year
        for cell in self.cells.itertuples():
            for anchor in ("onset", "calendar"):
                for year in ar.YEARS:
                    for window, hours in ar.WINDOWS.items():
                        bump = 2.0 if anchor == "onset" and year == event_year[cell.candidate_id] else 0.0
                        rows.append({"candidate_id": cell.candidate_id,
                            "grid_latitude_deg": cell.grid_latitude_deg,
                            "grid_longitude_deg_east": cell.grid_longitude_deg_east,
                            "primary_cell": cell.primary_cell, "anchor": anchor, "year": year,
                            "window": window, "hours": hours,
                            "mean_t2m_k": 250 + .001*cell.grid_latitude_deg + bump})
        diagnostics, primary, overlap = ar.derive(pd.DataFrame(rows), self.cells, self.selected)
        self.assertEqual((len(rows), len(diagnostics), len(primary), len(overlap)),
                         (24816, 528, 66, 27))
        self.assertTrue((primary.delta_time_warm_state_rank > 0).all())
        self.assertTrue(np.allclose(overlap.delta_combined_warm_state_rank,
            overlap.delta_coordinate_warm_state_rank + overlap.delta_time_warm_state_rank))
        self.assertTrue(np.allclose(overlap.delta_combined_linear_trend_residual_rank,
            overlap.delta_coordinate_linear_trend_residual_rank +
            overlap.delta_time_linear_trend_residual_rank))

    def test_gate_precedes_remote_open(self):
        opened = []
        with mock.patch.object(ar, "verify_gate", side_effect=ValueError("stop")), \
             mock.patch.object(ar.pilot, "open_store", side_effect=lambda: opened.append(True)):
            with self.assertRaisesRegex(ValueError, "stop"):
                ar.analyze(Path("missing"), "bad", Path(tempfile.mkdtemp())/"results")
        self.assertEqual(opened, [])
        result = Path(tempfile.mkdtemp())/"results"; result.mkdir()
        with mock.patch.object(ar, "verify_gate", return_value={}), \
             mock.patch.object(ar.pilot, "open_store", side_effect=lambda: opened.append(True)):
            with self.assertRaisesRegex(ValueError, "already exists"):
                ar.analyze(Path("bound"), "good", result)
        self.assertEqual(opened, [])

    def test_registered_point_extraction_and_stops(self):
        candidate = self.selected.iloc[[0]]; cells = self.cells[self.cells.candidate_id == candidate.iloc[0].candidate_id]
        hours = np.arange(np.datetime64("1978-01-01"), np.datetime64("2027-01-01"), np.timedelta64(1, "h"))
        def store(fill=250.):
            item = mock.Mock(); item.latitude.values = np.arange(90., -90.25, -.25)
            item.longitude.values = np.arange(0., 360., .25); item.valid_time.values = hours.copy()
            item.t2m.isel.side_effect = lambda **kw: mock.Mock(values=np.full(
                (len(kw["valid_time"]), kw["latitude"].size), fill))
            return item
        temporal = store(); matched, air = ar.extract(candidate, cells, temporal)
        self.assertEqual((len(matched), len(air)), (1128, 12))
        accessed = set()
        for call in temporal.t2m.isel.call_args_list:
            self.assertEqual(call.kwargs["latitude"].dims, ("point",))
            accessed.update(zip(call.kwargs["latitude"].values, call.kwargs["longitude"].values))
        self.assertEqual(accessed, set(zip(cells.latitude_index, cells.longitude_index)))
        for fill in (np.nan, 179.):
            with self.assertRaisesRegex(ValueError, "invalid requested temperature"):
                ar.extract(candidate, cells, store(fill))
        bad = store(); bad.valid_time.values[10] = bad.valid_time.values[9]
        with self.assertRaisesRegex(ValueError, "unexpected ERA5 grid"): ar.extract(candidate, cells, bad)
        bad = store(); bad.valid_time.values = np.delete(bad.valid_time.values, 10)
        with self.assertRaisesRegex(ValueError, "unexpected ERA5 grid"): ar.extract(candidate, cells, bad)
        bad = store(); bad.valid_time.values = bad.valid_time.values[bad.valid_time.values < np.datetime64("2025-01-01")]
        with self.assertRaisesRegex(ValueError, "exceeds store coverage"): ar.extract(candidate, cells, bad)
        bad_cells = cells.copy(); bad_cells.loc[bad_cells.index[0], "grid_latitude_deg"] = 0
        with self.assertRaisesRegex(ValueError, "grids disagree"): ar.extract(candidate, bad_cells, store())

    def test_registered_line_budget_and_no_new_dependency(self):
        source = ROOT/"scripts/audited_reanalysis.py"; test = Path(__file__)
        self.assertLessEqual(sum(path.read_text().count("\n") for path in (source, test)), 500)
        self.assertEqual((ROOT/"requirements-audited-reanalysis.txt").read_text(),
                         "-r requirements-reanalysis.txt\n")
        text = source.read_text()
        self.assertNotIn("hazard", text.lower())
        self.assertNotIn("failure_probability", text)

if __name__ == "__main__": unittest.main()
