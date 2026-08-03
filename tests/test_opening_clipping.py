"""Tests für die Allplan-unabhängige Band-/Segmentlogik.

Ausführbar ohne Allplan:  python3 -m pytest tests/  (oder unittest)
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'PythonPartsScripts' / 'SlabReinforcement'))

from opening_clipping import compute_edge_bar_runs, compute_placement_bands


class ComputePlacementBandsTest(unittest.TestCase):

    def test_no_opening_returns_single_full_band(self):
        bands = compute_placement_bands(4000, 5000, None, None)

        self.assertEqual(len(bands), 1)
        self.assertEqual(bands[0].dist_from, 0)
        self.assertEqual(bands[0].dist_to, 4000)
        self.assertEqual(bands[0].run_segments, [(0, 5000)])

    def test_opening_outside_slab_is_ignored(self):
        bands = compute_placement_bands(4000, 5000, (4500, 5000), (1000, 2000))

        self.assertEqual(len(bands), 1)
        self.assertEqual(bands[0].run_segments, [(0, 5000)])

    def test_opening_inside_creates_three_bands(self):
        # Platte 5000x4000, Stäbe entlang run=5000; Öffnung x=1500..2300, y=1200..2200
        bands = compute_placement_bands(4000, 5000, (1200, 2200), (1500, 2300))

        self.assertEqual(len(bands), 3)

        self.assertEqual((bands[0].dist_from, bands[0].dist_to), (0, 1200))
        self.assertEqual(bands[0].run_segments, [(0, 5000)])

        self.assertEqual((bands[1].dist_from, bands[1].dist_to), (1200, 2200))
        self.assertEqual(bands[1].run_segments, [(0, 1500), (2300, 5000)])

        self.assertEqual((bands[2].dist_from, bands[2].dist_to), (2200, 4000))
        self.assertEqual(bands[2].run_segments, [(0, 5000)])

    def test_opening_at_slab_edge_drops_empty_parts(self):
        # Öffnung beginnt am Plattenrand (dist) und am Stabanfang (run)
        bands = compute_placement_bands(4000, 5000, (0, 800), (0, 1000))

        self.assertEqual(len(bands), 2)
        self.assertEqual((bands[0].dist_from, bands[0].dist_to), (0, 800))
        self.assertEqual(bands[0].run_segments, [(1000, 5000)])
        self.assertEqual((bands[1].dist_from, bands[1].dist_to), (800, 4000))

    def test_opening_spanning_full_run_removes_bars_in_band(self):
        bands = compute_placement_bands(4000, 5000, (1000, 2000), (-10, 5010))

        # Mittleres Band enthält keine Segmente mehr und entfällt komplett
        self.assertEqual(len(bands), 2)
        self.assertEqual((bands[0].dist_from, bands[0].dist_to), (0, 1000))
        self.assertEqual((bands[1].dist_from, bands[1].dist_to), (2000, 4000))

    def test_short_segments_are_dropped(self):
        # Reststück rechts der Öffnung nur 100 lang -> fällt unter Mindestlänge 300
        bands = compute_placement_bands(4000, 5000, (1000, 2000), (1500, 4900),
                                        min_segment_length=300)

        middle = bands[1]
        self.assertEqual(middle.run_segments, [(0, 1500)])

    def test_degenerate_slab_returns_nothing(self):
        self.assertEqual(compute_placement_bands(0, 5000, None, None), [])
        self.assertEqual(compute_placement_bands(4000, -5, None, None), [])


class ComputeEdgeBarRunsTest(unittest.TestCase):

    def test_two_runs_with_lap_overhang(self):
        runs = compute_edge_bar_runs(4000, 5000, (1200, 2200), (1500, 2300),
                                     lap_length=800, zone_width=100)

        self.assertEqual(len(runs), 2)

        before, after = runs
        self.assertEqual((before.run_from, before.run_to), (700, 3100))
        self.assertEqual((before.dist_from, before.dist_to), (1100, 1200))
        self.assertEqual((after.dist_from, after.dist_to), (2200, 2300))

    def test_runs_clamped_at_slab_boundary(self):
        # Öffnung nahe am Plattenursprung: Überstand und Zone werden geklemmt
        runs = compute_edge_bar_runs(4000, 5000, (50, 500), (100, 600),
                                     lap_length=800, zone_width=100)

        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0].run_from, 0)
        self.assertEqual((runs[0].dist_from, runs[0].dist_to), (0, 50))

    def test_no_zone_when_opening_touches_edge(self):
        # Öffnung beginnt direkt am Plattenrand -> vor der Öffnung keine Zone
        runs = compute_edge_bar_runs(4000, 5000, (0, 500), (100, 600),
                                     lap_length=200, zone_width=100)

        self.assertEqual(len(runs), 1)
        self.assertEqual((runs[0].dist_from, runs[0].dist_to), (500, 600))


if __name__ == '__main__':
    unittest.main()
