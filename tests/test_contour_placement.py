"""Tests für die Scanline-Logik polygonaler Konturen (ohne Allplan lauffähig)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'PythonPartsScripts' / 'SlabReinforcement'))

from contour_placement import (compute_contour_bars, group_bars_into_runs, loop_area,
                               loop_bbox, scan_positions, split_closed_loops)

RECT = [(0, 0), (5000, 0), (5000, 4000), (0, 4000)]

# L-Form: 5000x4000 mit ausgeklinkter Ecke oben rechts (ab x=3000, y=2000)
L_SHAPE = [(0, 0), (5000, 0), (5000, 2000), (3000, 2000), (3000, 4000), (0, 4000)]


class SplitClosedLoopsTest(unittest.TestCase):

    def test_single_closed_loop(self):
        points = RECT + [RECT[0]]
        loops = split_closed_loops(points)

        self.assertEqual(loops, [RECT])

    def test_contour_with_opening_loop(self):
        opening = [(1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000)]
        points = RECT + [RECT[0]] + opening + [opening[0]]

        loops = split_closed_loops(points)

        self.assertEqual(len(loops), 2)
        self.assertEqual(loops[0], RECT)
        self.assertEqual(loops[1], opening)

    def test_unclosed_rest_is_kept_as_loop(self):
        loops = split_closed_loops(RECT)

        self.assertEqual(loops, [RECT])

    def test_area_and_bbox(self):
        self.assertEqual(abs(loop_area(RECT)), 5000 * 4000)
        self.assertEqual(loop_bbox(L_SHAPE), (0, 0, 5000, 4000))


class ScanPositionsTest(unittest.TestCase):

    def test_uniform_spacing(self):
        positions = scan_positions(0, 1000, 250)

        self.assertEqual(positions, [0, 250, 500, 750, 1000])

    def test_edge_zones(self):
        positions = scan_positions(0, 2000, 200, edge_zone_length=300, edge_zone_spacing=100)

        # Zone [0..300] mit 100, Mitte mit 200, Zone [1700..2000] mit 100
        self.assertEqual(positions[:4], [0, 100, 200, 300])
        self.assertIn(500, positions)
        self.assertTrue(all(b - a == 100 for a, b in zip(positions, positions[1:])
                            if a >= 1700))

    def test_zones_disabled_when_too_short(self):
        positions = scan_positions(0, 500, 200, edge_zone_length=300, edge_zone_spacing=100)

        self.assertEqual(positions, [0, 200, 400])


class ComputeContourBarsTest(unittest.TestCase):

    def test_rectangle_all_bars_full_length(self):
        # Stäbe in X, Scan entlang Y; Deckung 25, Abstand 150
        bars = compute_contour_bars(RECT, [], 0, 150, 25, 300)

        self.assertEqual(bars[0].position, 25)
        self.assertEqual(bars[0].segments, ((0, 5000),))
        self.assertTrue(all(bar.segments == ((0, 5000),) for bar in bars))

    def test_l_shape_bars_get_shorter_in_notch(self):
        bars = compute_contour_bars(L_SHAPE, [], 0, 500, 0, 300)

        below = [bar for bar in bars if bar.position < 2000]
        above = [bar for bar in bars if bar.position > 2000]

        self.assertTrue(all(bar.segments == ((0, 5000),) for bar in below))
        self.assertTrue(all(bar.segments == ((0, 3000),) for bar in above))

    def test_opening_splits_bars(self):
        opening = [(1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000)]
        bars = compute_contour_bars(RECT, [opening], 0, 500, 0, 300)

        bar_in_opening = next(bar for bar in bars if 1000 < bar.position < 2000)
        self.assertEqual(bar_in_opening.segments, ((0, 1000), (2000, 5000)))

    def test_short_segments_dropped(self):
        # Öffnung lässt links nur 200 Reststab -> unter Mindestlänge 300
        opening = [(200, 1000), (2000, 1000), (2000, 2000), (200, 2000)]
        bars = compute_contour_bars(RECT, [opening], 0, 500, 0, 300)

        bar_in_opening = next(bar for bar in bars if 1000 < bar.position < 2000)
        self.assertEqual(bar_in_opening.segments, ((2000, 5000),))


class GroupBarsIntoRunsTest(unittest.TestCase):

    def test_rectangle_collapses_to_single_run(self):
        bars = compute_contour_bars(RECT, [], 0, 150, 25, 300)
        runs = group_bars_into_runs(bars)

        self.assertEqual(len(runs), 1)
        self.assertEqual(len(runs[0].positions), len(bars))
        self.assertEqual(runs[0].spacing, 150)

    def test_l_shape_creates_two_runs(self):
        bars = compute_contour_bars(L_SHAPE, [], 0, 500, 0, 300)
        runs = group_bars_into_runs(bars)

        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0].segments, ((0, 5000),))
        self.assertEqual(runs[1].segments, ((0, 3000),))

    def test_changed_spacing_breaks_run(self):
        bars = compute_contour_bars(RECT, [], 0, 200, 0,
                                    300, edge_zone_length=400, edge_zone_spacing=100)
        runs = group_bars_into_runs(bars)

        # Verdichtungszonen und Mittelbereich bilden getrennte Läufe
        self.assertGreaterEqual(len(runs), 3)
        self.assertEqual(runs[0].spacing, 100)


if __name__ == '__main__':
    unittest.main()
