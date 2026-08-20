"""Tests für die Aussparungsbewehrung (ohne Allplan lauffähig)."""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'PythonPartsScripts' / 'SlabReinforcement'))

from opening_reinforcement import (EdgeBar, clip_bar, corner_diagonals,
                                   group_equal_bars, opening_edge_bars,
                                   outward_normals, point_in_loop, signed_area)

SLAB = [(0, 0), (10000, 0), (10000, 8000), (0, 8000)]

# Aussparung 1000x600, mittig genug für vollen Überstand
OPENING = [(4000, 3000), (5000, 3000), (5000, 3600), (4000, 3600)]


class LoopBasicsTest(unittest.TestCase):

    def test_signed_area_sign_follows_orientation(self):
        self.assertGreater(signed_area(OPENING), 0)
        self.assertLess(signed_area(list(reversed(OPENING))), 0)

    def test_point_in_loop(self):
        self.assertTrue(point_in_loop((4500, 3300), OPENING))
        self.assertFalse(point_in_loop((3000, 3300), OPENING))

    def test_normals_point_away_from_the_opening(self):
        centre = (4500, 3300)

        for i, normal in enumerate(outward_normals(OPENING)):
            x1, y1 = OPENING[i]
            x2, y2 = OPENING[(i + 1) % len(OPENING)]

            middle = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
            probe = (middle[0] + normal[0] * 10, middle[1] + normal[1] * 10)

            self.assertFalse(point_in_loop(probe, OPENING))
            # und wirklich vom Mittelpunkt weg
            self.assertGreater(math.dist(probe, centre), math.dist(middle, centre))

    def test_orientation_does_not_change_the_normals(self):
        forward = outward_normals(OPENING)
        backward = outward_normals(list(reversed(OPENING)))

        # dieselben Richtungen, nur in anderer Kantenreihenfolge
        self.assertEqual(sorted(round(n[0], 6) for n in forward),
                         sorted(round(n[0], 6) for n in backward))


class EdgeBarTest(unittest.TestCase):

    def test_one_bar_per_edge_and_count(self):
        bars = opening_edge_bars(OPENING, 2, 12, 50, 800)

        self.assertEqual(len(bars), 8)

    def test_bar_is_parallel_to_its_edge_and_offset_outward(self):
        bars = opening_edge_bars(OPENING, 1, 12, 50, 0)

        # Kante 0 läuft von (4000,3000) nach (5000,3000), aussen = -y
        bottom = next(bar for bar in bars if bar.edge_index == 0)

        self.assertAlmostEqual(bottom.start[1], 3000 - 12, places=6)
        self.assertAlmostEqual(bottom.end[1], 3000 - 12, places=6)
        self.assertAlmostEqual(bottom.start[0], 4000, places=6)
        self.assertAlmostEqual(bottom.end[0], 5000, places=6)

    def test_lap_extends_beyond_both_corners(self):
        bars = opening_edge_bars(OPENING, 1, 12, 50, 800)
        bottom = next(bar for bar in bars if bar.edge_index == 0)

        self.assertAlmostEqual(bottom.start[0], 4000 - 800, places=6)
        self.assertAlmostEqual(bottom.end[0], 5000 + 800, places=6)
        self.assertAlmostEqual(bottom.length, 1000 + 2 * 800, places=6)

    def test_further_bars_are_offset_by_the_spacing(self):
        bars = [bar for bar in opening_edge_bars(OPENING, 3, 12, 50, 0)
                if bar.edge_index == 0]

        self.assertEqual([round(bar.offset) for bar in bars], [12, 62, 112])

    def test_angle_of_a_slanted_edge(self):
        slanted = [(0, 0), (1000, 1000), (0, 2000)]
        bars = opening_edge_bars(slanted, 1, 10, 50, 0)

        self.assertAlmostEqual(bars[0].angle, 45.0, places=6)

    def test_zero_count_gives_nothing(self):
        self.assertEqual(opening_edge_bars(OPENING, 0, 12, 50, 800), [])


class CornerDiagonalTest(unittest.TestCase):

    def test_one_diagonal_per_corner(self):
        bars = corner_diagonals(OPENING, 1, 30, 1500, 100)

        self.assertEqual(len(bars), 4)

    def test_diagonal_runs_at_45_degrees_over_a_right_angle_corner(self):
        bars = corner_diagonals(OPENING, 1, 30, 1500, 100)

        for bar in bars:
            self.assertAlmostEqual(abs(bar.angle) % 90, 45.0, places=6)
            self.assertAlmostEqual(bar.length, 1500, places=6)

    def test_diagonal_lies_outside_the_opening(self):
        for bar in corner_diagonals(OPENING, 1, 30, 1500, 100):
            centre = ((bar.start[0] + bar.end[0]) / 2.0,
                      (bar.start[1] + bar.end[1]) / 2.0)

            self.assertFalse(point_in_loop(centre, OPENING))

    def test_straight_run_is_not_a_corner(self):
        # Zusätzlicher Punkt mitten auf einer Kante -> kein Knick
        loop = [(4000, 3000), (4500, 3000), (5000, 3000), (5000, 3600), (4000, 3600)]

        self.assertEqual(len(corner_diagonals(loop, 1, 30, 1000, 100)), 4)

    def test_zero_length_gives_nothing(self):
        self.assertEqual(corner_diagonals(OPENING, 1, 30, 0, 100), [])


class ClipBarTest(unittest.TestCase):

    def test_bar_inside_the_slab_is_untouched(self):
        bar = opening_edge_bars(OPENING, 1, 12, 50, 800)[0]
        pieces = clip_bar(bar, SLAB, [OPENING], cover=30)

        self.assertEqual(len(pieces), 1)
        self.assertAlmostEqual(pieces[0].length, bar.length, places=6)

    def test_bar_is_cut_at_the_slab_edge_with_cover(self):
        # Aussparung direkt am linken Plattenrand
        opening = [(100, 3000), (1000, 3000), (1000, 3600), (100, 3600)]
        bar = next(b for b in opening_edge_bars(opening, 1, 12, 50, 800)
                   if b.edge_index == 0)

        pieces = clip_bar(bar, SLAB, [opening], cover=30)

        self.assertEqual(len(pieces), 1)
        # links bei x=0 gekappt, plus 30 Deckung
        self.assertAlmostEqual(pieces[0].start[0], 30, places=6)
        self.assertAlmostEqual(pieces[0].end[0], 1000 + 800, places=6)

    def test_bar_crossing_a_second_opening_is_split(self):
        other = [(5200, 2000), (5600, 2000), (5600, 5000), (5200, 5000)]
        # langer Stab entlang der Unterkante mit grossem Überstand
        bar = next(b for b in opening_edge_bars(OPENING, 1, 12, 50, 2000)
                   if b.edge_index == 0)

        pieces = clip_bar(bar, SLAB, [OPENING, other], cover=0)

        self.assertEqual(len(pieces), 2)
        self.assertAlmostEqual(pieces[0].end[0], 5200, places=6)
        self.assertAlmostEqual(pieces[1].start[0], 5600, places=6)

    def test_short_remainders_are_dropped(self):
        other = [(5200, 2000), (6900, 2000), (6900, 5000), (5200, 5000)]
        bar = next(b for b in opening_edge_bars(OPENING, 1, 12, 50, 2000)
                   if b.edge_index == 0)

        pieces = clip_bar(bar, SLAB, [OPENING, other], cover=0, min_length=300)

        # der Rest hinter der zweiten Öffnung ist nur 100 lang
        self.assertEqual(len(pieces), 1)

    def test_bar_completely_outside_gives_nothing(self):
        bar = EdgeBar((-3000, -3000), (-2000, -3000), 0, 0)

        self.assertEqual(clip_bar(bar, SLAB, [], cover=0), [])

    def test_slanted_cut_uses_the_perpendicular_cover(self):
        # Platte mit Schräge von (8000,0) nach (10000,2000)
        slab = [(0, 0), (8000, 0), (10000, 2000), (10000, 8000), (0, 8000)]
        bar = EdgeBar((5000, 1000), (11000, 1000), 0, 0)
        cover = 30

        pieces = clip_bar(bar, slab, [], cover=cover)

        self.assertEqual(len(pieces), 1)

        # Kante bei y=1000: x = 8000 + 1000 = 9000; Rückversatz = cover/sin45
        self.assertAlmostEqual(pieces[0].end[0],
                               9000 - cover / math.sin(math.radians(45)), places=4)


class GroupEqualBarsTest(unittest.TestCase):

    def test_equal_bars_of_one_edge_form_one_group(self):
        bars = [bar for bar in opening_edge_bars(OPENING, 3, 12, 50, 800)
                if bar.edge_index == 0]

        groups = group_equal_bars(bars)

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0]), 3)

    def test_different_edges_are_never_grouped(self):
        bars = opening_edge_bars(OPENING, 2, 12, 50, 800)
        groups = group_equal_bars(bars)

        self.assertEqual(len(groups), 4)

    def test_different_lengths_break_the_group(self):
        bars = [EdgeBar((0, 0), (1000, 0), 0, 0),
                EdgeBar((0, 50), (1000, 50), 0, 50),
                EdgeBar((0, 100), (600, 100), 0, 100)]

        groups = group_equal_bars(bars)

        self.assertEqual([len(group) for group in groups], [2, 1])

    def test_changed_spacing_breaks_the_group(self):
        bars = [EdgeBar((0, 0), (1000, 0), 0, 0),
                EdgeBar((0, 50), (1000, 50), 0, 50),
                EdgeBar((0, 200), (1000, 200), 0, 200)]

        groups = group_equal_bars(bars)

        self.assertEqual([len(group) for group in groups], [2, 1])

    def test_empty_input(self):
        self.assertEqual(group_equal_bars([]), [])


if __name__ == '__main__':
    unittest.main()
