"""Tests der Wand-Anschlusseisen-Geometrie (ohne Allplan lauffähig)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent
                       / 'PythonPartsScripts' / 'SlabReinforcement'))

from wall_connection import (WallRun, auto_leg_length, clip_segment_to_loop,
                             same_footprint, toggle_walls,
                             wall_connection_runs, wall_thickness)

SLAB = [(0.0, 0.0), (5000.0, 0.0), (5000.0, 4000.0), (0.0, 4000.0)]

# Wand 3000 x 240, achsparallel mitten auf der Platte
WALL = [(1000.0, 2000.0), (4000.0, 2000.0), (4000.0, 2240.0), (1000.0, 2240.0)]


class TestWallThickness(unittest.TestCase):
    def test_achsparalleles_rechteck(self):
        self.assertAlmostEqual(wall_thickness(WALL), 240.0)

    def test_gedrehtes_rechteck(self):
        import math
        c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
        rotated = [(x * c - y * s, x * s + y * c) for x, y in WALL]

        self.assertAlmostEqual(wall_thickness(rotated), 240.0, places=5)


class TestClipSegment(unittest.TestCase):
    def test_ganz_innen(self):
        self.assertEqual(clip_segment_to_loop((1000, 2000), (4000, 2000), SLAB),
                         [(0.0, 1.0)])

    def test_ragt_beidseitig_hinaus(self):
        spans = clip_segment_to_loop((-1000, 2000), (6000, 2000), SLAB)

        self.assertEqual(len(spans), 1)
        t0, t1 = spans[0]
        self.assertAlmostEqual(-1000 + 7000 * t0, 0.0)
        self.assertAlmostEqual(-1000 + 7000 * t1, 5000.0)

    def test_ganz_draussen(self):
        self.assertEqual(clip_segment_to_loop((0, 5000), (5000, 5000), SLAB), [])

    def test_l_kontur_zerteilt_in_zwei_stuecke(self):
        # C-förmige Kontur: Segment quer über die Einbuchtung
        c_shape = [(0, 0), (5000, 0), (5000, 1000), (2000, 1000),
                   (2000, 3000), (5000, 3000), (5000, 4000), (0, 4000)]
        spans = clip_segment_to_loop((0, 500), (5000, 500), c_shape)

        self.assertEqual(len(spans), 1)  # y=500 liegt unter der Einbuchtung

        spans = clip_segment_to_loop((1000, 2000), (5000, 2000), c_shape)
        self.assertEqual(len(spans), 1)
        t0, t1 = spans[0]
        self.assertAlmostEqual(1000 + 4000 * t1, 2000.0)


class TestWallConnectionRuns(unittest.TestCase):
    def test_nur_die_beiden_langseiten(self):
        runs = wall_connection_runs(WALL, SLAB, min_run_length=200.0)

        self.assertEqual(len(runs), 2)
        for run in runs:
            length = abs(run.to_pnt[0] - run.from_pnt[0])
            self.assertAlmostEqual(length, 3000.0)

    def test_schenkel_zeigen_von_der_wand_weg(self):
        runs = wall_connection_runs(WALL, SLAB, min_run_length=200.0)

        by_y = sorted(runs, key=lambda r: r.from_pnt[1])

        # Untere Wandseite (y=2000): Schenkel nach unten (-90°),
        # obere Wandseite (y=2240): nach oben (+90°)
        self.assertAlmostEqual(by_y[0].outward_deg % 360.0, 270.0)
        self.assertAlmostEqual(by_y[1].outward_deg % 360.0, 90.0)

    def test_wand_ragt_ueber_die_platte_hinaus(self):
        wall = [(-1000.0, 2000.0), (6000.0, 2000.0),
                (6000.0, 2240.0), (-1000.0, 2240.0)]
        runs = wall_connection_runs(wall, SLAB, min_run_length=200.0)

        self.assertEqual(len(runs), 2)
        for run in runs:
            xs = sorted((run.from_pnt[0], run.to_pnt[0]))
            self.assertAlmostEqual(xs[0], 0.0)
            self.assertAlmostEqual(xs[1], 5000.0)

    def test_wand_ganz_neben_der_platte(self):
        wall = [(6000.0, 0.0), (9000.0, 0.0), (9000.0, 240.0), (6000.0, 240.0)]

        self.assertEqual(wall_connection_runs(wall, SLAB, 200.0), [])

    def test_zu_kurze_reststuecke_entfallen(self):
        # Nur 150 mm der Wand liegen über der Platte
        wall = [(4850.0, 2000.0), (8000.0, 2000.0),
                (8000.0, 2240.0), (4850.0, 2240.0)]

        self.assertEqual(wall_connection_runs(wall, SLAB, min_run_length=200.0), [])

    def test_reihenfolge_der_wandpunkte_egal(self):
        runs_ccw = wall_connection_runs(WALL, SLAB, 200.0)
        runs_cw = wall_connection_runs(list(reversed(WALL)), SLAB, 200.0)

        normals_ccw = sorted(round(r.outward_deg % 360.0, 3) for r in runs_ccw)
        normals_cw = sorted(round(r.outward_deg % 360.0, 3) for r in runs_cw)

        self.assertEqual(normals_ccw, normals_cw)


class TestToggleWalls(unittest.TestCase):
    """Mehrfachauswahl: erneut gewählte Wände werden abgewählt."""

    WALL_A = [(1000.0, 2000.0), (4000.0, 2000.0), (4000.0, 2240.0), (1000.0, 2240.0)]
    WALL_B = [(500.0, 500.0), (740.0, 500.0), (740.0, 3500.0), (500.0, 3500.0)]

    def test_neue_wand_kommt_hinzu(self):
        self.assertEqual(toggle_walls([], [self.WALL_A]), [self.WALL_A])

    def test_erneutes_waehlen_entfernt(self):
        self.assertEqual(toggle_walls([self.WALL_A], [self.WALL_A]), [])

    def test_gemischt_hinzu_und_abwaehlen(self):
        result = toggle_walls([self.WALL_A], [self.WALL_A, self.WALL_B])

        self.assertEqual(result, [self.WALL_B])

    def test_punktreihenfolge_egal(self):
        rotated = self.WALL_A[2:] + self.WALL_A[:2]

        self.assertEqual(toggle_walls([self.WALL_A], [list(reversed(rotated))]), [])

    def test_leicht_verschobene_wand_ist_eine_andere(self):
        shifted = [(x + 50.0, y) for x, y in self.WALL_A]

        self.assertEqual(len(toggle_walls([self.WALL_A], [shifted])), 2)

    def test_same_footprint_toleranz(self):
        jittered = [(x + 0.05, y - 0.05) for x, y in self.WALL_A]

        self.assertTrue(same_footprint(self.WALL_A, jittered))
        self.assertFalse(same_footprint(self.WALL_A, self.WALL_B))


class TestAutoLegLength(unittest.TestCase):
    def test_formel_aus_dem_buero_pythonpart(self):
        # Stoss 600, Platte 250 mit 30/30 Deckung: 600 - 190 = 410
        self.assertAlmostEqual(auto_leg_length(600, 250, 30, 30, 200), 410.0)

    def test_mindestschenkel_greift(self):
        # Stoss 480 bei dicker Platte: 480 - 440 = 40 < 200
        self.assertAlmostEqual(auto_leg_length(480, 500, 30, 30, 200), 200.0)

    def test_abrundung_auf_zehn(self):
        self.assertAlmostEqual(auto_leg_length(605, 250, 30, 30, 200), 410.0)


if __name__ == '__main__':
    unittest.main()
