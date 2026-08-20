"""Tests für die Scanline-Logik polygonaler Konturen (ohne Allplan lauffähig)."""

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'PythonPartsScripts' / 'SlabReinforcement'))

from contour_placement import (LONGEST, SHORTEST, _round_outward,
                               bar_parallel_breaks,
                               compute_contour_bars, decompose_into_zones,
                               edge_setback, group_bars_into_runs,
                               group_bars_into_steps, loop_area, loop_bbox,
                               parallel_edges, scan_positions,
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


class DecompositionTest(unittest.TestCase):
    """Schritt 1: Zerlegung in Rechtecke, ausgerichtet nach der Stabrichtung."""

    # Treppenkontur mit Schräge unten rechts (wie die Beispielplatte)
    SLAB = [(0, 0), (6748, 0), (10214, 5131), (10214, 9240), (6748, 9240),
            (6748, 6798), (3416, 6798), (3416, 3135), (2095, 3135),
            (2095, 5131), (0, 5131)]

    def _zones(self, run_axis, deviation=250.0):
        bars = compute_contour_bars(self.SLAB, [], run_axis, 150.0, 40.0, 300.0,
                                    max_setback=150.0, dist_margin=46.0)
        return bars, decompose_into_zones(self.SLAB and bars, self.SLAB, run_axis,
                                          deviation, 50.0, 300.0)

    def test_breaks_follow_the_bar_direction(self):
        # Stäbe in Y -> Sprünge an den senkrechten Kanten (x-Werte)
        self.assertEqual(bar_parallel_breaks(self.SLAB, 1),
                         [0, 2095, 3416, 6748, 10214])

        # Stäbe in X -> Sprünge an den waagrechten Kanten (y-Werte)
        self.assertEqual(bar_parallel_breaks(self.SLAB, 0),
                         [0, 3135, 5131, 6798, 9240])

    def test_rectangles_differ_per_layer(self):
        _, zones_y = self._zones(1)
        _, zones_x = self._zones(0)

        rects_y = [z for z in zones_y if z.kind == 'rect']
        rects_x = [z for z in zones_x if z.kind == 'rect']

        self.assertEqual(len(rects_y), 4)
        self.assertEqual(len(rects_x), 4)
        self.assertNotEqual([z.segments[0] for z in rects_y],
                            [z.segments[0] for z in rects_x])

    def test_rectangle_bars_all_have_the_same_length(self):
        _, zones = self._zones(1)

        for zone in [z for z in zones if z.kind == 'rect']:
            self.assertEqual(len(set(zone.segments)), 1)

    def test_slanted_part_becomes_step_zones(self):
        _, zones = self._zones(1)

        steps = [z for z in zones if z.kind == 'step']

        self.assertGreater(len(steps), 1)
        # Stufen werden zur Schräge hin kürzer
        lengths = [z.segments[0][0][1] - z.segments[0][0][0] for z in steps]
        self.assertGreater(lengths[0], lengths[-1])

    def test_step_is_measured_on_the_longest_bar(self):
        bars, zones = self._zones(1)

        # Die Stufenzone deckt hier den Bereich unterhalb des Rechtecks ab;
        # ihr unteres Ende muss dem *längsten* (am tiefsten reichenden) Stab
        # der Stufe folgen, nicht dem kürzesten.
        available = {bar.position: bar.segments[0][0] for bar in bars}

        for zone in [z for z in zones if z.kind == 'step']:
            built_from = zone.segments[0][0][0]
            own = [available[p] for p in zone.positions if p in available]

            if not own:
                continue

            # bis zum längsten Stab (das Raster rundet dort nach aussen)
            self.assertLessEqual(built_from, min(own) + 1e-6)
            # und nicht am kürzesten Stab abgeschnitten
            self.assertLess(built_from, max(own) + 1e-6)

    def test_overshoot_stays_within_the_allowance(self):
        deviation = 250.0
        bars, zones = self._zones(1, deviation)

        available = {bar.position: bar.segments for bar in bars}
        raster = 50.0

        for zone in [z for z in zones if z.kind == 'step']:
            built = zone.segments[0][0]

            for position in zone.positions:
                for own_from, own_to in available.get(position, ()):
                    # Stufe darf den Stab verlängern, aber nur begrenzt
                    # (zusätzlich bis zu einem Raster je Ende durch die Rundung)
                    overshoot = max(own_from - built[0], 0) + max(built[1] - own_to, 0)
                    self.assertLessEqual(overshoot, deviation + 2 * raster + 1e-6)

    def test_round_outward_never_shortens(self):
        self.assertEqual(_round_outward((1050, 1560), 100), (1000, 1600))
        self.assertEqual(_round_outward((-1560, -1050), 100), (-1600, -1000))
        self.assertEqual(_round_outward((1000, 1500), 100), (1000, 1500))
        self.assertEqual(_round_outward((10, 20), 0), (10, 20))


class ZoneVariantTest(unittest.TestCase):
    """Variante A/B der Rechteckgrenze und Vermeidung von Einzelstäben."""

    SLAB = DecompositionTest.SLAB

    def _zones(self, run_axis, snap):
        bars = compute_contour_bars(self.SLAB, [], run_axis, 150.0, 40.0, 300.0,
                                    max_setback=150.0, dist_margin=46.0)
        return bars, decompose_into_zones(bars, self.SLAB, run_axis, 250.0, 50.0,
                                          300.0, snap_to_contour=snap)

    def test_variant_a_pulls_the_rectangle_to_a_contour_edge(self):
        # Mittleres Band der X-Lage: Variante A endet an der Kante x=6748,
        # Variante B erst am Beginn der Schräge
        _, zones_a = self._zones(0, True)
        _, zones_b = self._zones(0, False)

        def middle_end(zones):
            for zone in zones:
                if zone.kind != 'rect':
                    continue
                for seg_from, seg_to in zone.segments[0]:
                    if 3300 < seg_from < 3600 and zone.positions[0] > 3000:
                        return seg_to
            return None

        self.assertAlmostEqual(middle_end(zones_a), 6748, delta=1)
        self.assertGreater(middle_end(zones_b), 8000)

    def test_variant_a_creates_more_steps(self):
        _, zones_a = self._zones(0, True)
        _, zones_b = self._zones(0, False)

        steps_a = len([z for z in zones_a if z.kind == 'step'])
        steps_b = len([z for z in zones_b if z.kind == 'step'])

        self.assertGreater(steps_a, steps_b)

    def test_straight_edge_is_not_snapped(self):
        # Band ohne Schräge darf nicht an einer fremden Kante zerschnitten werden
        _, zones = self._zones(0, True)

        top = [z for z in zones if z.kind == 'rect' and z.positions[0] > 6800]

        self.assertTrue(top)
        for zone in top:
            seg_from, seg_to = zone.segments[0][0]
            self.assertGreater(seg_to - seg_from, 3000)

    def test_no_single_bar_placements(self):
        for run_axis in (0, 1):
            for snap in (True, False):
                _, zones = self._zones(run_axis, snap)

                for zone in zones:
                    self.assertGreater(len(zone.positions), 1,
                                       f'Einzelstab in {zone.kind}-Zone bei '
                                       f'{zone.positions} (run_axis={run_axis})')

    def test_merged_single_bar_keeps_the_neighbour_length(self):
        # Der zugeschlagene Stab bekommt die Länge der Nachbarverlegung
        _, zones = self._zones(1, True)

        for zone in zones:
            self.assertEqual(len(zone.positions), len(zone.segments))
            self.assertEqual(len(set(zone.segments)), 1)


class EdgeExtensionTest(unittest.TestCase):
    """Anschlusseisen: Stäbe ragen an ausgewählten Konturkanten über den Rand."""

    def test_extension_replaces_the_cover_at_that_edge(self):
        plain = compute_contour_bars(RECT, [], 0, 500.0, 40.0, 300.0)
        self.assertEqual(plain[0].segments, ((40.0, 4960.0),))

        # Kante 3 ist die linke Kante (von (0,4000) nach (0,0))
        extended = compute_contour_bars(RECT, [], 0, 500.0, 40.0, 300.0,
                                        edge_extensions={3: 600.0})

        self.assertEqual(extended[0].segments, ((-600.0, 4960.0),))

    def test_other_edges_keep_their_cover(self):
        extended = compute_contour_bars(RECT, [], 0, 500.0, 40.0, 300.0,
                                        edge_extensions={3: 600.0})

        for bar in extended:
            self.assertAlmostEqual(bar.segments[0][1], 4960.0, places=6)

    def test_both_ends_can_be_extended(self):
        extended = compute_contour_bars(RECT, [], 0, 500.0, 40.0, 300.0,
                                        edge_extensions={1: 600.0, 3: 600.0})

        self.assertEqual(extended[0].segments, ((-600.0, 5600.0),))

    def test_no_extensions_behaves_as_before(self):
        self.assertEqual(compute_contour_bars(RECT, [], 0, 500.0, 40.0, 300.0),
                         compute_contour_bars(RECT, [], 0, 500.0, 40.0, 300.0,
                                              edge_extensions={}))


class StepReferenceTest(unittest.TestCase):
    """Stufenlänge am längsten oder am kürzesten Stab."""

    CONTOUR = [(0, 0), (3000, 0), (5000, 2000), (5000, 4000), (0, 4000)]

    def _zones(self, reference):
        bars = compute_contour_bars(self.CONTOUR, [], 0, 150, 30, 300,
                                    dist_margin=34)

        return bars, decompose_into_zones(bars, self.CONTOUR, 0,
                                          max_step_deviation=250,
                                          length_raster=50,
                                          min_bar_length=300,
                                          step_reference=reference)

    def test_shortest_keeps_every_bar_inside_the_concrete(self):
        bars, zones = self._zones(SHORTEST)
        available = {bar.position: bar.segments for bar in bars}

        for zone in zones:
            for i, built in enumerate(zone.segments[0]):
                for position in zone.positions:
                    own = available.get(position, ())

                    if i >= len(own):
                        continue

                    self.assertGreaterEqual(built[0], own[i][0] - 1e-6)
                    self.assertLessEqual(built[1], own[i][1] + 1e-6)

    def test_longest_does_extend_beyond_the_concrete(self):
        bars, zones = self._zones(LONGEST)
        available = {bar.position: bar.segments for bar in bars}

        overshoots = [built[1] - own[i][1]
                      for zone in zones if zone.kind == 'step'
                      for i, built in enumerate(zone.segments[0])
                      for position in zone.positions
                      for own in [available.get(position, ())]
                      if i < len(own)]

        self.assertTrue(any(value > 1.0 for value in overshoots))

    def test_shortest_raster_never_grows_past_the_reference_bar(self):
        # Bei SHORTEST rundet das Raster nach innen — die gerade erst
        # gesicherte Deckung darf es nicht wieder auffressen.
        bars, zones = self._zones(SHORTEST)
        widest = {bar.position: bar.segments for bar in bars}

        for zone in zones:
            for i, built in enumerate(zone.segments[0]):
                own = [widest[p][i] for p in zone.positions
                       if p in widest and i < len(widest[p])]

                if not own:
                    continue

                self.assertGreaterEqual(built[0], min(lo for lo, _ in own) - 1e-6)
                self.assertLessEqual(built[1], max(hi for _, hi in own) + 1e-6)


class ParallelEdgeCoverTest(unittest.TestCase):
    """Im Deckungsstreifen einer stabparallelen Kante darf kein Stab liegen."""

    def test_parallel_edges_of_the_l_shape(self):
        # Stäbe in X (run_axis 0) -> parallel sind die Kanten mit konstantem y
        edges = sorted(parallel_edges(L_SHAPE, 0))

        self.assertEqual(edges, [(0.0, 0.0, 5000.0),
                                 (2000.0, 3000.0, 5000.0),
                                 (4000.0, 0.0, 3000.0)])

    def test_no_bar_inside_the_cover_of_a_reentrant_edge(self):
        bars = compute_contour_bars(L_SHAPE, [], 0, 195, 30, 200,
                                    dist_margin=30)

        for bar in bars:
            if abs(bar.position - 2000) >= 30:
                continue

            for seg_from, seg_to in bar.segments:
                # Kein Segment darf über die Kante y=2000 (x 3000..5000) reichen
                self.assertLessEqual(seg_from, 3000)
                self.assertLessEqual(seg_to, 3000)

    def test_bar_is_clipped_not_dropped(self):
        # y = 30 + 10*195 = 1980 liegt 20 mm unter der Kante y=2000 und wird
        # abgeschnitten statt komplett zu entfallen; der Sperrstreifen ist
        # um die Deckung verlängert, damit auch zur Ecke Deckung bleibt.
        bars = {bar.position: bar.segments
                for bar in compute_contour_bars(L_SHAPE, [], 0, 195, 30, 200,
                                                dist_margin=30)}

        self.assertEqual(bars[1980], ((30.0, 2970.0),))
        self.assertEqual(bars[1785], ((30.0, 4970.0),))

    def test_full_width_bars_are_kept(self):
        # Ein Stab weit weg von der einspringenden Kante bleibt vollständig
        bars = compute_contour_bars(L_SHAPE, [], 0, 100, 30, 200,
                                    dist_margin=30)
        positions = [bar.position for bar in bars]

        self.assertIn(1030.0, positions)

    def test_opening_cover_strip_blocks_parallel_bars(self):
        """Hilfsparallele um die Aussparung: ein Stab, der innerhalb der
        Deckung an einer Aussparungskante entlangläuft, wird über deren
        (um die Deckung verlängerte) Ausdehnung abgeschnitten."""

        opening = [(2000, 1000), (3000, 1000), (3000, 2000), (2000, 2000)]
        # Raster trifft y = 1020 — nur 20 mm unter der Kante y = 1000
        bars = {bar.position: bar.segments
                for bar in compute_contour_bars(RECT, [opening], 0, 165, 30,
                                                200, dist_margin=30)}

        clipped = bars[1020.0]
        self.assertEqual(len(clipped), 2)
        self.assertAlmostEqual(clipped[0][1], 2000 - 30, places=6)
        self.assertAlmostEqual(clipped[1][0], 3000 + 30, places=6)

        # Ein Stab ausserhalb des Streifens läuft ungestört durch
        far = [seg for pos, segs in bars.items() if pos < 900 for seg in segs]
        self.assertTrue(all(abs(seg[1] - 4970) < 1 for seg in far))

    def test_rectangle_is_unaffected(self):
        with_filter = compute_contour_bars(RECT, [], 0, 250, 30, 200,
                                           dist_margin=30)

        self.assertTrue(with_filter)
        self.assertAlmostEqual(with_filter[0].position, 30.0)
        self.assertAlmostEqual(with_filter[-1].position, 3970.0)


if __name__ == '__main__':
    unittest.main()
