"""Reine Scanline-Geometrie für polygonale Plattenkonturen.

Wie opening_clipping.py bewusst OHNE Allplan-Abhängigkeit, damit die
Logik ohne Allplan testbar bleibt.

Konventionen:
    - Ein "Loop" ist eine geschlossene Kontur als Punktliste [(x, y), ...]
      OHNE wiederholten Endpunkt (wird zyklisch interpretiert).
    - run_axis: 0 = Stäbe verlaufen in X (Scan entlang Y),
                1 = Stäbe verlaufen in Y (Scan entlang X).
    - Ein "Bar" ist (scan_koordinate, Segmente auf der Stabachse).
"""

from __future__ import annotations

from typing import NamedTuple

Point = tuple[float, float]
Loop = list[Point]
Interval = tuple[float, float]


def split_closed_loops(points: list[Point], tol: float = 1.0) -> list[Loop]:
    """Zerlegt eine Punktfolge, in der jede Teilkontur mit ihrem Startpunkt
    abgeschlossen ist (Allplan-Polygone: erster Punkt = letzter Punkt),
    in einzelne Loops ohne wiederholten Endpunkt.

    Eine nicht geschlossene Restfolge wird als (implizit geschlossener)
    Loop übernommen.
    """

    loops: list[Loop] = []
    start = 0

    while start < len(points):
        loop_end = None

        for idx in range(start + 1, len(points)):
            if abs(points[idx][0] - points[start][0]) <= tol and \
                    abs(points[idx][1] - points[start][1]) <= tol:
                loop_end = idx
                break

        if loop_end is None:
            loops.append(points[start:])
            break

        loops.append(points[start:loop_end])
        start = loop_end + 1

    return [loop for loop in loops if len(loop) >= 3]


def loop_area(loop: Loop) -> float:
    """Vorzeichenbehaftete Fläche (Gauß'sche Trapezformel)."""

    area = 0.0

    for i, (x1, y1) in enumerate(loop):
        x2, y2 = loop[(i + 1) % len(loop)]
        area += x1 * y2 - x2 * y1

    return area / 2.0


def loop_bbox(loop: Loop) -> tuple[float, float, float, float]:
    """(x_min, y_min, x_max, y_max) der Kontur."""

    xs = [p[0] for p in loop]
    ys = [p[1] for p in loop]

    return min(xs), min(ys), max(xs), max(ys)


def _crossings(loop: Loop, run_axis: int, coord: float) -> list[float]:
    """Schnittpunkte der Scanlinie (dist-Koordinate = coord) mit den
    Kanten des Loops, als Koordinaten auf der run-Achse.

    Halboffene Regel (d1 <= coord < d2), damit Scheitelpunkte nicht doppelt
    zählen — Standard-Scanline-Verfahren.
    """

    dist_axis = 1 - run_axis
    crossings: list[float] = []

    for i, p1 in enumerate(loop):
        p2 = loop[(i + 1) % len(loop)]

        d1, d2 = p1[dist_axis], p2[dist_axis]

        if d1 == d2:
            continue

        if (d1 <= coord < d2) or (d2 <= coord < d1):
            t = (coord - d1) / (d2 - d1)
            crossings.append(p1[run_axis] + t * (p2[run_axis] - p1[run_axis]))

    crossings.sort()

    return crossings


def _intervals_at(loop: Loop, run_axis: int, coord: float) -> list[Interval]:
    """Innen-Intervalle des Loops entlang der run-Achse bei coord."""

    crossings = _crossings(loop, run_axis, coord)

    return [(crossings[i], crossings[i + 1]) for i in range(0, len(crossings) - 1, 2)]


def _subtract_intervals(intervals: list[Interval],
                        holes: list[Interval]) -> list[Interval]:
    """Subtrahiert die (nicht notwendig disjunkten) Loch-Intervalle."""

    result = intervals

    for hole_from, hole_to in sorted(holes):
        next_result: list[Interval] = []

        for seg_from, seg_to in result:
            if hole_to <= seg_from or hole_from >= seg_to:
                next_result.append((seg_from, seg_to))
                continue

            if hole_from > seg_from:
                next_result.append((seg_from, hole_from))
            if hole_to < seg_to:
                next_result.append((hole_to, seg_to))

        result = next_result

    return result


def scan_positions(start: float,
                   end: float,
                   spacing: float,
                   edge_zone_length: float = 0.0,
                   edge_zone_spacing: float = 0.0) -> list[float]:
    """Scan-Koordinaten von start bis end.

    Ohne Randverdichtung: äquidistant mit spacing ab start.
    Mit Randverdichtung: an beiden Enden eine Zone der Länge
    edge_zone_length mit edge_zone_spacing, dazwischen spacing —
    das Gegenstück zu calculate_length_of_regions für den Scanline-Pfad.
    """

    if end < start or spacing <= 0:
        return []

    use_zones = (edge_zone_length > 0 and edge_zone_spacing > 0
                 and 2 * edge_zone_length < end - start)

    if not use_zones:
        count = int((end - start) / spacing + 1e-9)
        positions = [start + i * spacing for i in range(count + 1)]
    else:
        positions = [start]

        regions = ((start + edge_zone_length, edge_zone_spacing),
                   (end - edge_zone_length, spacing),
                   (end, edge_zone_spacing))

        for region_end, region_spacing in regions:
            while positions[-1] + region_spacing <= region_end + 1e-9:
                positions.append(positions[-1] + region_spacing)

    # Randstab am fernen Ende ergänzen, wenn das Raster dort nicht aufgeht —
    # analog zur AdditionalCover-Regel der linearen Placements
    if end - positions[-1] > 1.0:
        positions.append(end)

    return positions


class ContourBar(NamedTuple):
    """Eine Stablinie: Scan-Koordinate + Segmente auf der Stabachse."""

    position: float
    segments: tuple[Interval, ...]


def compute_contour_bars(contour: Loop,
                         openings: list[Loop],
                         run_axis: int,
                         spacing: float,
                         side_cover: float,
                         min_bar_length: float,
                         edge_zone_length: float = 0.0,
                         edge_zone_spacing: float = 0.0) -> list[ContourBar]:
    """Scanline-Verlegung: für jede Scan-Position die Stab-Segmente
    innerhalb der Kontur abzüglich der Öffnungen.

    side_cover wird als Randabstand der Scan-Positionen auf der dist-Achse
    berücksichtigt; auf der Stabachse werden Segmente verworfen, deren
    Stablänge (Segment − 2 x side_cover) unter min_bar_length liegt —
    die Deckung selbst zieht später der Shape-Builder ab.
    """

    dist_axis = 1 - run_axis
    bbox = loop_bbox(contour)

    dist_min = bbox[dist_axis] + side_cover
    dist_max = bbox[dist_axis + 2] - side_cover

    bars: list[ContourBar] = []

    for position in scan_positions(dist_min, dist_max, spacing,
                                   edge_zone_length, edge_zone_spacing):
        intervals = _intervals_at(contour, run_axis, position)

        holes: list[Interval] = []
        for opening in openings:
            holes += _intervals_at(opening, run_axis, position)

        segments = tuple(
            (seg_from, seg_to)
            for seg_from, seg_to in _subtract_intervals(intervals, holes)
            if seg_to - seg_from - 2 * side_cover >= min_bar_length)

        if segments:
            bars.append(ContourBar(position, segments))

    return bars


class BarRun(NamedTuple):
    """Gruppe aufeinanderfolgender Stablinien mit identischen Segmenten
    und konstantem Abstand — verlegbar als eine lineare Platzierung.
    """

    positions: list[float]
    segments: tuple[Interval, ...]

    @property
    def spacing(self) -> float:
        if len(self.positions) < 2:
            return 0.0
        return self.positions[1] - self.positions[0]


def group_bars_into_runs(bars: list[ContourBar], tol: float = 1.0) -> list[BarRun]:
    """Fasst aufeinanderfolgende Stablinien zu Verlegeläufen zusammen.

    Kriterien: gleiche Segmente (Endpunkte innerhalb tol) und gleicher
    Abstand zur Vorgängerlinie (innerhalb tol). Bei Rechteckplatten
    kollabiert so die gesamte Lage auf wenige Placements, an schrägen
    Rändern entstehen Einzelstab-Läufe.
    """

    def segments_equal(a: tuple[Interval, ...], b: tuple[Interval, ...]) -> bool:
        if len(a) != len(b):
            return False
        return all(abs(s1[0] - s2[0]) <= tol and abs(s1[1] - s2[1]) <= tol
                   for s1, s2 in zip(a, b))

    runs: list[BarRun] = []

    for bar in bars:
        if runs:
            run = runs[-1]
            gap = bar.position - run.positions[-1]
            same_gap = len(run.positions) < 2 or abs(gap - run.spacing) <= tol

            if segments_equal(run.segments, bar.segments) and same_gap:
                run.positions.append(bar.position)
                continue

        runs.append(BarRun([bar.position], bar.segments))

    return runs
