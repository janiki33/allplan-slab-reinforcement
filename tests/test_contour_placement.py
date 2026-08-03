"""Tests für die Scanline-Logik polygonaler Konturen (ohne Allplan lauffähig)."""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'PythonPartsScripts' / 'SlabReinforcement'))

from contour_placement import (compute_contour_bars, edge_setback,
                               group_bars_into_runs, group_bars_into_steps,
                               loop_area, loop_bbox, scan_positions,
                               split_closed_loops)

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

        # Rest 100 <= halber Stababstand -> kein Zusatzstab
        self.assertEqual(positions, [0, 200, 400])

    def test_end_bar_added_when_the_rest_is_large_enough(self):
        # Rest 200 > halber Stababstand (150) -> Randstab am Ende
        self.assertEqual(scan_positions(0, 1100, 300), [0, 300, 600, 900, 1100])

    def test_no_end_bar_when_the_rest_is_small(self):
        # Rest 100 <= halber Stababstand -> der Stab läge fast auf dem Nachbarn
        self.assertEqual(scan_positions(0, 1000, 300), [0, 300, 600, 900])

    def test_no_duplicate_end_bar_when_grid_fits(self):
        self.assertEqual(scan_positions(0, 1000, 250), [0, 250, 500, 750, 1000])


class ComputeContourBarsTest(unittest.TestCase):

    def test_rectangle_all_bars_full_length(self):
        # Stäbe in X, Scan entlang Y; Deckung 25, Abstand 150.
        # Die Segmente sind Nettomasse: an den rechtwinkligen Rändern ist
        # die Deckung 1:1 abgezogen.
        bars = compute_contour_bars(RECT, [], 0, 150, 25, 300)

        self.assertEqual(bars[0].position, 25)
        self.assertEqual(bars[0].segments, ((25, 4975),))
        self.assertTrue(all(bar.segments == ((25, 4975),) for bar in bars))

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
        # 0..4000 mit Abstand 200 geht exakt auf -> ein einziger Lauf
        bars = compute_contour_bars(RECT, [], 0, 200, 0, 300)
        runs = group_bars_into_runs(bars)

        self.assertEqual(len(runs), 1)
        self.assertEqual(len(runs[0].positions), len(bars))
        self.assertEqual(runs[0].spacing, 200)

    def test_small_rest_does_not_create_an_extra_run(self):
        # 25..3975 mit Abstand 150: Rest 50 <= halber Abstand -> ein Lauf
        bars = compute_contour_bars(RECT, [], 0, 150, 25, 300)
        runs = group_bars_into_runs(bars)

        self.assertEqual(len(runs), 1)

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


class EdgeCoverTest(unittest.TestCase):
    """Betondeckung senkrecht zur Kante (auch an Schrägen)."""

    def test_perpendicular_edge_uses_the_plain_cover(self):
        self.assertAlmostEqual(edge_setback(30, 1.0), 30, places=6)

    def test_slanted_edge_needs_a_larger_setback(self):
        # 45°: 30 / sin(45°) = 42.43
        self.assertAlmostEqual(edge_setback(30, math.sin(math.radians(45))),
                               30 / math.sin(math.radians(45)), places=6)

    def test_setback_is_capped_for_sharp_angles(self):
        self.assertEqual(edge_setback(30, math.sin(math.radians(5)), max_setback=120), 120)

    def test_no_cover_means_no_setback(self):
        self.assertEqual(edge_setback(0, 0.5), 0.0)

    def test_bar_keeps_perpendicular_cover_at_a_45_degree_edge(self):
        # Schräge von (3000,0) nach (5000,2000): bei y ist x_kante = 3000 + y
        contour = [(0, 0), (3000, 0), (5000, 2000), (5000, 4000), (0, 4000)]
        cover = 30

        bars = compute_contour_bars(contour, [], 0, 500, cover, 100)
        bar = bars[0]

        edge_x = 3000 + bar.position
        setback = edge_x - bar.segments[0][1]

        # senkrechter Abstand = axialer Rückversatz x sin(45°)
        self.assertAlmostEqual(setback * math.sin(math.radians(45)), cover, places=6)

    def test_opening_edges_keep_their_cover_too(self):
        opening = [(1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000)]
        bars = compute_contour_bars(RECT, [opening], 0, 500, 25, 100)

        bar = next(bar for bar in bars if 1000 < bar.position < 2000)

        # Loch wächst um die Deckung -> Stabenden halten Abstand zur Öffnung
        self.assertAlmostEqual(bar.segments[0][1], 1000 - 25, places=6)
        self.assertAlmostEqual(bar.segments[1][0], 2000 + 25, places=6)


class GroupBarsIntoStepsTest(unittest.TestCase):
    """Abtreppung an schrägen Rändern.

    Testkontur: Rechteck 5000x4000 mit 45°-Schräge von (3000,0) nach (5000,2000).
    """

    DIAG = [(0, 0), (3000, 0), (5000, 2000), (5000, 4000), (0, 4000)]

    def _bars(self, spacing=150):
        return compute_contour_bars(self.DIAG, [], 0, spacing, 0, 300)

    def test_rectangle_still_collapses_to_one_run(self):
        bars = compute_contour_bars(RECT, [], 0, 200, 0, 300)
        steps = group_bars_into_steps(bars, max_step_loss=250, length_raster=50)

        self.assertEqual(len(steps), 1)
        self.assertEqual(len(steps[0].positions), len(bars))

    def test_no_bar_is_shortened_more_than_allowed(self):
        bars = self._bars()
        max_loss = 250

        steps = group_bars_into_steps(bars, max_step_loss=max_loss, length_raster=0)

        available = {bar.position: bar.segments[0] for bar in bars}

        for step in steps:
            for position in step.positions:
                own = available[position]
                built = step.segments[0]
                loss = abs(built[0] - own[0]) + abs(own[1] - built[1])

                self.assertLessEqual(loss, max_loss)

    def test_bars_never_protrude_beyond_the_contour(self):
        bars = self._bars()
        steps = group_bars_into_steps(bars, max_step_loss=500, length_raster=50)

        available = {bar.position: bar.segments[0] for bar in bars}

        for step in steps:
            for position in step.positions:
                own_from, own_to = available[position]
                built_from, built_to = step.segments[0]

                self.assertGreaterEqual(built_from, own_from - 1e-6)
                self.assertLessEqual(built_to, own_to + 1e-6)

    def test_larger_allowance_creates_fewer_and_wider_steps(self):
        bars = self._bars()

        few = group_bars_into_steps(bars, max_step_loss=500, length_raster=50)
        many = group_bars_into_steps(bars, max_step_loss=150, length_raster=50)

        self.assertLess(len(few), len(many))
        self.assertGreater(len(few[0].positions), len(many[0].positions))

    def test_zero_allowance_means_every_differing_bar_on_its_own(self):
        bars = self._bars()
        steps = group_bars_into_steps(bars, max_step_loss=0, length_raster=0)

        stepped = [step for step in steps if step.positions[0] < 2000]
        self.assertTrue(all(len(step.positions) == 1 for step in stepped))

    def test_length_raster_rounds_inward(self):
        bars = self._bars()
        steps = group_bars_into_steps(bars, max_step_loss=250, length_raster=100)

        for step in steps:
            for seg_from, seg_to in step.segments:
                self.assertAlmostEqual(seg_from % 100, 0, places=6)
                self.assertAlmostEqual(seg_to % 100, 0, places=6)

    def test_step_breaks_where_opening_starts(self):
        opening = [(1000, 1000), (2000, 1000), (2000, 2000), (1000, 2000)]
        bars = compute_contour_bars(RECT, [opening], 0, 200, 0, 300)

        steps = group_bars_into_steps(bars, max_step_loss=250, length_raster=0)

        # Bereiche mit 1 und mit 2 Segmenten dürfen nie in derselben Stufe liegen
        self.assertGreaterEqual(len(steps), 3)
        self.assertTrue(any(len(step.segments) == 2 for step in steps))


if __name__ == '__main__':
    unittest.main()
