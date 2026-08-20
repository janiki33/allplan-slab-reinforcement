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

        # Links/rechts je eine Hauptverlegung; der Randstab am Ende des
        # Scanrasters (kleinerer Abstand) wird als eigene Exakt-Verlegung
        # geführt statt aufs Raster verschoben zu werden
        self.assertEqual(len(groups), 4)

        mains = sorted((g for g in groups if len(g.positions) > 1),
                       key=lambda g: g.piece)
        self.assertEqual(len(mains), 2)
        self.assertEqual(len(mains[0].positions), len(bars) - 1)
        self.assertAlmostEqual(mains[0].piece[1] - mains[1].piece[0], 600.0,
                               places=6)
        mid = (30 + 13970) / 2
        self.assertAlmostEqual(mains[0].piece[1], mid + 300, places=6)

        # Jede Bahn ist genau einmal je Stück belegt
        for piece_group in (mains[0], mains[1]):
            singles = [g for g in groups if len(g.positions) == 1
                       and g.piece == piece_group.piece]
            self.assertEqual(len(piece_group.positions) + len(singles),
                             len(bars))

    def test_form6_thirds(self):
        contour = [(0, 0), (21000, 0), (21000, 4500), (0, 4500)]
        bars, groups = plan(contour)

        pieces = {g.piece for g in groups}
        self.assertEqual(len(pieces), 3)      # gedrittelt

        for g in groups:
            self.assertLessEqual(g.piece[1] - g.piece[0], 8000 + 1e-6)

        # je Stück: Hauptlauf + exakter Randstab decken alle Bahnen ab
        for piece in pieces:
            total = sum(len(g.positions) for g in groups if g.piece == piece)
            self.assertEqual(total, len(bars))

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


class FluchtShareTest(unittest.TestCase):
    """Lohnt-sich-Regel: kleine Aussparungen in grossen Platten erzeugen
    keine Fluchten — belegt am realen Projektbeispiel 20.5 x 15 m."""

    CONTOUR = [(0, 0), (20510, 0), (20510, 15025), (0, 15025)]
    OP1 = [(810, 9190), (5045, 9190), (5045, 10380), (810, 10380)]
    OP2 = [(3250, 6030), (4850, 6030), (4850, 7780), (3250, 7780)]

    def test_small_openings_produce_no_fluchten(self):
        for axis in (0, 1):
            bars = compute_contour_bars(self.CONTOUR, [self.OP1, self.OP2],
                                        axis, 300.0, 30.0, 300.0,
                                        dist_margin=36)
            self.assertEqual(
                active_fluchten(self.CONTOUR, [self.OP1, self.OP2], axis,
                                bars, 3000.0), [])

    def test_full_x_bars_anchor_on_the_zone_edge(self):
        """Anker-Regel: erste Stossachse an der Aussenkante der
        Aussparungszone (x = 5045), das freie Feld rechts davon
        gleichmässig geteilt — insgesamt 3 Stösse je Vollbahn."""

        bars = compute_contour_bars(self.CONTOUR, [self.OP1, self.OP2], 0,
                                    300.0, 30.0, 300.0, dist_margin=36)
        groups = plan_layer(bars, self.CONTOUR, [self.OP1, self.OP2], 0, **PARAMS)

        full = pieces_at(groups, 36.0)
        self.assertEqual(len(full), 4)
        self.assertAlmostEqual(full[0][1], 5045 + 300, places=6)

        for piece in full:
            self.assertLessEqual(piece[1] - piece[0], 8000 + 1e-6)

    def test_free_field_pieces_are_shared_across_all_rows(self):
        """Rechts der Zone EINE durchgehende Verlegung: die hinteren
        Stücke der Aussparungszeilen sind identisch mit denen der vollen
        Bahnen und werden über die ganze Plattenhöhe zusammengelegt."""

        bars = compute_contour_bars(self.CONTOUR, [self.OP1, self.OP2], 0,
                                    300.0, 30.0, 300.0, dist_margin=36)
        groups = plan_layer(bars, self.CONTOUR, [self.OP1, self.OP2], 0, **PARAMS)

        full = pieces_at(groups, 36.0)
        op1_row = pieces_at(groups, 9636.0)

        # letzte zwei Stücke identisch (globale Achsen im freien Feld)
        self.assertEqual(full[-1], op1_row[-1])
        self.assertEqual(full[-2], op1_row[-2])

        # und über alle Bahnen zusammengelegt (Hauptlauf über die ganze
        # Höhe plus der exakte Randstab am Scanende)
        big = [g for g in groups if g.piece == full[-1]]
        self.assertEqual(sum(len(g.positions) for g in big), len(bars))
        self.assertGreaterEqual(max(len(g.positions) for g in big),
                                len(bars) - 1)

    def test_y_columns_keep_the_plain_mid(self):
        """In Y gibt es keinen Anker: die freien Stücke neben der Zone
        sind nicht überlang — volle Spalten stossen einfach mittig."""

        bars = compute_contour_bars(self.CONTOUR, [self.OP1, self.OP2], 1,
                                    300.0, 30.0, 300.0, dist_margin=36)
        groups = plan_layer(bars, self.CONTOUR, [self.OP1, self.OP2], 1, **PARAMS)

        full = pieces_at(groups, 19836.0)
        self.assertEqual(len(full), 2)
        self.assertAlmostEqual(full[0][1], (30 + 14995) / 2 + 300, places=6)

    def test_row_next_to_opening_laps_mid(self):
        bars = compute_contour_bars(self.CONTOUR, [self.OP1, self.OP2], 0,
                                    300.0, 30.0, 300.0, dist_margin=36)
        groups = plan_layer(bars, self.CONTOUR, [self.OP1, self.OP2], 0, **PARAMS)

        # Zeile durch Aussparung 2: linkes Stück mittig gestossen. Die
        # Region endet an der Schnittmenge der Nachbarbahnen (3214: der
        # Sperrstreifen der Aussparung clippt die Bahn direkt daneben) —
        # strikt in der Deckung, kein Stab ragt in die Hilfsparallele
        row = pieces_at(groups, 6336.0)
        self.assertAlmostEqual(row[0][1], (30 + 3214) / 2 + 300, places=6)

    def test_large_opening_still_uses_fluchten(self):
        contour = [(0, 0), (14000, 0), (14000, 7000), (0, 7000)]
        opening = [(6000, 2500), (8500, 2500), (8500, 4500), (6000, 4500)]
        bars = bars_for(contour, [opening])

        # 2 m Kante an 7 m Platte = 29 % >= 25 % -> Fluchten aktiv
        self.assertEqual(active_fluchten(contour, [opening], 0, bars, 3000.0),
                         [6000, 8500])


class UniformRunTest(unittest.TestCase):
    """Jede Verlegung muss strikt äquidistant und doppelfrei sein — Allplan
    setzt Anzahl x konstanter Abstand ab; alles andere verschiebt real
    Stäbe (die 'fehlenden Eisen' unter der Aussparung)."""

    CONTOUR = [(0, 0), (20510, 0), (20510, 15025), (0, 15025)]
    OP2 = [(3250, 6030), (4850, 6030), (4850, 7780), (3250, 7780)]

    def test_all_groups_equidistant_across_strip_scenarios(self):
        # Aussparungs-Unterkante so schieben, dass Bahnen in den
        # Sperrstreifen fallen (die 0.7.3-Regression)
        for oy in range(9150, 9310, 15):
            op1 = [(810, oy), (5045, oy), (5045, oy + 1190), (810, oy + 1190)]

            for axis in (0, 1):
                bars = compute_contour_bars(self.CONTOUR, [op1, self.OP2],
                                            axis, 150.0, 40.0, 300.0,
                                            dist_margin=46.0)
                groups = plan_layer(bars, self.CONTOUR, [op1, self.OP2],
                                    axis, **PARAMS)

                for g in groups:
                    for a, b in zip(g.positions, g.positions[1:]):
                        self.assertGreater(b - a, 1.0)   # keine Doppelten

                    if len(g.positions) >= 3:
                        d0 = g.positions[1] - g.positions[0]
                        for a, b in zip(g.positions, g.positions[1:]):
                            self.assertAlmostEqual(b - a, d0, delta=1.0)

    def test_every_bar_segment_stays_covered(self):
        for oy in (9150, 9195, 9240):
            op1 = [(810, oy), (5045, oy), (5045, oy + 1190), (810, oy + 1190)]
            bars = compute_contour_bars(self.CONTOUR, [op1, self.OP2], 0,
                                        150.0, 40.0, 300.0, dist_margin=46.0)
            groups = plan_layer(bars, self.CONTOUR, [op1, self.OP2], 0, **PARAMS)

            placed = {}
            for g in groups:
                for pos in g.positions:
                    placed.setdefault(pos, []).append(g.piece)

            for bar in bars:
                pieces = sorted(placed.get(bar.position, []))

                for seg in bar.segments:
                    if seg[1] - seg[0] < 300:
                        continue

                    cur = seg[0]
                    for piece in pieces:
                        if piece[0] <= cur + 200.0:
                            cur = max(cur, piece[1])

                    self.assertGreaterEqual(cur, seg[1] - 200.0,
                                            f'Lücke bei y={bar.position}')


class NoSingletonTest(unittest.TestCase):

    def test_no_single_bar_groups_in_stepped_regions(self):
        contour = [(0, 0), (14000, 0), (14000, 2500), (8500, 8000), (0, 8000)]
        bars, groups = plan(contour)

        # Stufenstücke nie als Einzelstab; der exakte Randstab am Ende des
        # Scanrasters ist die zulässige Ausnahme (letzte Scan-Position)
        last = max(b.position for b in bars)

        for g in groups:
            if len(g.positions) == 1:
                self.assertAlmostEqual(g.positions[0], last, delta=1.0)


if __name__ == '__main__':
    unittest.main()
