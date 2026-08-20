"""Tests der neuen Stossplanung — die Fälle entsprechen den vom Anwender
bestätigten Formen des Studienblatts (Formen 1–10, Proben A–D)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'PythonPartsScripts' / 'SlabReinforcement'))

from contour_placement import compute_contour_bars
from lap_planning import (PlacementGroup, active_fluchten, base_cuts,
                          plan_layer)

PARAMS = dict(lmax=8000.0, lap=600.0, pass_threshold=3000.0,
              step_deviation=250.0, raster=50.0, min_piece=2000.0,
              min_bar=300.0)


def bars_for(contour, openings=(), spacing=300.0, cover=30.0):
    return compute_contour_bars(contour, list(openings), 0, spacing, cover,
                                300.0, dist_margin=cover + 6)


def plan(contour, openings=()):
    bars = bars_for(contour, openings)
    return bars, plan_layer(bars, contour, list(openings), 0, **PARAMS)


def pieces_at(groups, position):
    return sorted(g.piece for g in groups if position in g.positions)


class BaseCutsTest(unittest.TestCase):
    """Regeln 1 und 2 auf Segmentebene."""

    def test_short_bar_keeps_no_cut(self):
        self.assertEqual(base_cuts((0, 2500), [], 8000, 600, 3000, 300), [])

    def test_pass_bar_gets_a_mid_cut(self):
        self.assertEqual(base_cuts((0, 5000), [], 8000, 600, 3000, 300), [2500])

    def test_13m_is_halved(self):
        self.assertEqual(base_cuts((0, 13000), [], 8000, 600, 3000, 300), [6500])

    def test_19m_is_split_in_thirds(self):
        cuts = base_cuts((0, 19000), [], 8000, 600, 3000, 300)
        self.assertEqual(len(cuts), 2)
        self.assertAlmostEqual(cuts[0], 19000 / 3, places=6)
        self.assertAlmostEqual(cuts[1], 2 * 19000 / 3, places=6)

    def test_fluchten_are_used_first(self):
        cuts = base_cuts((0, 14000), [6000, 8500], 8000, 600, 3000, 300)
        self.assertEqual(cuts, [6000, 8500])

    def test_piece_still_too_long_gets_an_extra_cut(self):
        # Flucht bei 2000 lässt rechts 16 m übrig -> zwei Zusatzstösse
        cuts = base_cuts((0, 18000), [2000], 8000, 600, 3000, 300)
        self.assertEqual(len(cuts), 3)
        self.assertIn(2000, cuts)


class FluchtenTest(unittest.TestCase):
    """Regel 3: Fluchten und wann sie entfallen."""

    def test_opening_edges_are_always_active(self):
        contour = [(0, 0), (14000, 0), (14000, 7000), (0, 7000)]
        opening = [(6000, 2500), (8500, 2500), (8500, 4500), (6000, 4500)]
        bars = bars_for(contour, [opening])

        self.assertEqual(active_fluchten(contour, [opening], 0, bars, 3000.0),
                         [6000, 8500])

    def test_corner_flucht_stays_for_a_short_leg(self):
        # Probe B: Schenkel 7430..9970 = 2.54 m < 3 m -> Flucht bleibt
        contour = [(0, 0), (10000, 0), (10000, 8000), (7400, 8000),
                   (7400, 4000), (0, 4000)]
        bars = bars_for(contour)

        self.assertEqual(active_fluchten(contour, [], 0, bars, 3000.0), [7400])

    def test_corner_flucht_falls_for_a_long_leg(self):
        # Probe A: Schenkel 7130..11970 = 4.84 m >= 3 m -> Flucht entfällt
        contour = [(0, 0), (12000, 0), (12000, 8000), (7100, 8000),
                   (7100, 4000), (0, 4000)]
        bars = bars_for(contour)

        self.assertEqual(active_fluchten(contour, [], 0, bars, 3000.0), [])


class RectanglePlanTest(unittest.TestCase):
    """Formen 1 und 6."""

    def test_form1_every_bar_lapped_mid(self):
        contour = [(0, 0), (14000, 0), (14000, 6000), (0, 6000)]
        bars, groups = plan(contour)

        # Eine linke und eine rechte Verlegung über alle Bahnen
        self.assertEqual(len(groups), 2)

        left, right = sorted(groups, key=lambda g: g.piece)
        self.assertEqual(len(left.positions), len(bars))
        self.assertAlmostEqual(left.piece[1] - right.piece[0], 600.0, places=6)
        mid = (30 + 13970) / 2
        self.assertAlmostEqual(left.piece[1], mid + 300, places=6)

    def test_form6_thirds(self):
        contour = [(0, 0), (21000, 0), (21000, 4500), (0, 4500)]
        bars, groups = plan(contour)

        self.assertEqual(len(groups), 3)
        for g in groups:
            self.assertLessEqual(g.piece[1] - g.piece[0], 8000 + 1e-6)

    def test_no_lap_below_pass_threshold(self):
        contour = [(0, 0), (2500, 0), (2500, 4000), (0, 4000)]
        bars, groups = plan(contour)

        self.assertEqual(len(groups), 1)
        self.assertEqual(len(groups[0].positions), len(bars))


class LShapePlanTest(unittest.TestCase):
    """Formen 2 / Proben A und B."""

    def test_short_leg_keeps_the_flucht(self):
        # Probe B: unten Stoss auf der Flucht, oben Passeisen ohne Stoss
        contour = [(0, 0), (10000, 0), (10000, 8000), (7400, 8000),
                   (7400, 4000), (0, 4000)]
        bars, groups = plan(contour)

        low = pieces_at(groups, 36.0)
        self.assertEqual(len(low), 2)
        self.assertAlmostEqual(low[0][1], 7400 + 300, places=6)

        up = pieces_at(groups, 4236.0)
        self.assertEqual(len(up), 1)          # Passeisen, kein Stoss

    def test_long_leg_laps_mid_and_flucht_falls(self):
        # Probe A: beide Regionen mittig
        contour = [(0, 0), (12000, 0), (12000, 8000), (7100, 8000),
                   (7100, 4000), (0, 4000)]
        bars, groups = plan(contour)

        low = pieces_at(groups, 36.0)
        self.assertEqual(len(low), 2)
        self.assertAlmostEqual(low[0][1], (30 + 11970) / 2 + 300, places=6)

        up = pieces_at(groups, 4236.0)
        self.assertEqual(len(up), 2)          # >= 3 m -> mittig gestossen
        self.assertAlmostEqual(up[0][1], (7130 + 11970) / 2 + 300, places=6)


class OpeningPlanTest(unittest.TestCase):
    """Formen 4/8 / Probe C."""

    CONTOUR = [(0, 0), (14000, 0), (14000, 7000), (0, 7000)]
    OPENING = [(6000, 2500), (8500, 2500), (8500, 4500), (6000, 4500)]

    def test_full_bars_lap_on_both_fluchten(self):
        bars, groups = plan(self.CONTOUR, [self.OPENING])

        full = pieces_at(groups, 36.0)
        self.assertEqual(len(full), 3)
        self.assertAlmostEqual(full[0][1], 6300, places=6)
        self.assertAlmostEqual(full[2][0], 8200, places=6)

    def test_interrupted_rows_get_mid_pass_laps(self):
        bars, groups = plan(self.CONTOUR, [self.OPENING])

        row = pieces_at(groups, 3036.0)
        # links 0..5970 (>= 3 m -> mittig), rechts 8530..13970 (>= 3 m -> mittig)
        self.assertEqual(len(row), 4)
        self.assertAlmostEqual(row[0][1], (30 + 5970) / 2 + 300, places=6)
        self.assertAlmostEqual(row[2][1], (8530 + 13970) / 2 + 300, places=6)

    def test_every_piece_within_lmax(self):
        bars, groups = plan(self.CONTOUR, [self.OPENING])

        for g in groups:
            self.assertLessEqual(g.piece[1] - g.piece[0], 8000 + 1e-6)


class SteppedPlanTest(unittest.TestCase):
    """Formen 3/5 / Probe D."""

    CONTOUR = [(0, 0), (14000, 0), (14000, 2500), (8500, 8000), (0, 8000)]

    def test_step_line_is_inherited_and_shifted(self):
        bars, groups = plan(self.CONTOUR)

        # volle Bahnen: Mitte wäre 7000; kürzestes Stufenende ~8621 ->
        # Linie = 8621 - 2000 (Mindestlänge) ~ 6621
        stepped = [b for b in bars if b.segments[0][1] < 13000]
        min_end = min(b.segments[0][1] for b in stepped)

        left = pieces_at(groups, 36.0)
        self.assertEqual(len(left), 2)
        line = left[0][1] - 300

        self.assertAlmostEqual(line, min_end - 2000, places=4)
        self.assertLess(line, 7000)

    def test_stepped_pieces_start_on_one_line(self):
        bars, groups = plan(self.CONTOUR)

        # Stufengruppen: Stücke, die auf der Stosslinie beginnen (nicht am
        # Plattenrand) und nicht bis zur vollen Länge reichen
        stepped_groups = [g for g in groups
                          if g.piece[0] > 5000 and g.piece[1] < 13970 - 1]

        self.assertGreater(len(stepped_groups), 1)
        starts = {round(g.piece[0], 3) for g in stepped_groups}
        self.assertEqual(len(starts), 1)      # eine gemeinsame Stosslinie

    def test_step_geometry_unchanged(self):
        # Vermessung am längsten Ende, Raster nach aussen — wie bisher
        bars, groups = plan(self.CONTOUR)

        for g in groups:
            if len(g.positions) < 2 or g.piece[1] >= 13970 - 1 \
                    or g.piece[0] < 5000:
                continue

            member_ends = [b.segments[0][1] for b in bars
                           if b.position in g.positions]

            self.assertGreaterEqual(g.piece[1] + 1e-6, max(member_ends))
            self.assertLessEqual(g.piece[1] - max(member_ends), 50 + 1e-6)
            self.assertAlmostEqual(g.piece[1] % 50, 0, places=6)

    def test_every_stepped_piece_at_least_min_piece(self):
        bars, groups = plan(self.CONTOUR)

        for g in groups:
            self.assertGreaterEqual(g.piece[1] - g.piece[0], 2000 - 50 - 1e-6)

    def test_min_lap_at_the_line(self):
        bars, groups = plan(self.CONTOUR)

        for bar in bars:
            pieces = pieces_at(groups, bar.position)
            for a, b in zip(pieces, pieces[1:]):
                self.assertGreaterEqual(a[1] - b[0], 600 - 1e-6)


class NoSingletonTest(unittest.TestCase):

    def test_no_single_bar_groups_in_stepped_regions(self):
        contour = [(0, 0), (14000, 0), (14000, 2500), (8500, 8000), (0, 8000)]
        bars, groups = plan(contour)

        for g in groups:
            self.assertGreater(len(g.positions), 1)


if __name__ == '__main__':
    unittest.main()
