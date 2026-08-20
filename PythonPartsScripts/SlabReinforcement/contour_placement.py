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

import math
from typing import NamedTuple

LONGEST = 'longest'
SHORTEST = 'shortest'

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


def _crossings(loop: Loop, run_axis: int, coord: float) -> list[tuple[float, float, int]]:
    """Schnittpunkte der Scanlinie (dist-Koordinate = coord) mit den Kanten
    des Loops.

    Halboffene Regel (d1 <= coord < d2), damit Scheitelpunkte nicht doppelt
    zählen — Standard-Scanline-Verfahren.

    Returns:
        Liste (Koordinate auf der run-Achse, sin des Winkels zwischen
        Stabrichtung und geschnittener Kante, Index der Kante), aufsteigend
        sortiert. sin = 1 bei einer Kante rechtwinklig zum Stab, kleiner bei
        Schrägen. Der Kantenindex erlaubt es, je Kante unterschiedlich zu
        verfahren (z. B. Anschlusseisen über den Rand hinaus).
    """

    dist_axis = 1 - run_axis
    crossings: list[tuple[float, float, int]] = []

    for i, p1 in enumerate(loop):
        p2 = loop[(i + 1) % len(loop)]

        d1, d2 = p1[dist_axis], p2[dist_axis]

        if d1 == d2:
            continue

        if (d1 <= coord < d2) or (d2 <= coord < d1):
            t = (coord - d1) / (d2 - d1)

            edge_run = p2[run_axis] - p1[run_axis]
            edge_dist = d2 - d1
            edge_length = math.hypot(edge_run, edge_dist)

            sin_alpha = abs(edge_dist) / edge_length if edge_length else 1.0

            crossings.append((p1[run_axis] + t * edge_run, sin_alpha, i))

    crossings.sort()

    return crossings


def edge_setback(cover: float, sin_alpha: float, max_setback: float = 0.0) -> float:
    """Rückversatz des Stabendes entlang der Stabachse, damit die
    Betondeckung **senkrecht** zur Kante eingehalten wird.

    Bei einer Kante rechtwinklig zum Stab (sin = 1) ist der Rückversatz
    gleich der Deckung. Bei einer Schräge unter dem Winkel alpha wächst er
    auf cover / sin(alpha) an — bei spitzen Winkeln stark, deshalb die
    Begrenzung max_setback (0 = unbegrenzt).
    """

    if cover <= 0:
        return 0.0

    if sin_alpha <= 1e-6:
        return max_setback if max_setback > 0 else cover

    setback = cover / sin_alpha

    if max_setback > 0:
        setback = min(setback, max_setback)

    return setback


def _intervals_at(loop: Loop,
                  run_axis: int,
                  coord: float,
                  cover: float = 0.0,
                  max_setback: float = 0.0,
                  as_hole: bool = False,
                  extensions: dict[int, float] | None = None) -> list[Interval]:
    """Innen-Intervalle des Loops entlang der run-Achse bei coord.

    Mit cover > 0 werden die Intervalle um den kantenabhängigen Rückversatz
    verkleinert (Kontur) bzw. vergrößert (as_hole=True für Öffnungen, deren
    Rand ebenfalls Deckung braucht).

    extensions: je Kantenindex ein Überstand, um den der Stab über diese
    Kante hinausragt (Anschlusseisen). Ein Überstand ersetzt die Deckung an
    diesem Ende.
    """

    crossings = _crossings(loop, run_axis, coord)
    extra = extensions or {}

    intervals: list[Interval] = []

    for i in range(0, len(crossings) - 1, 2):
        (start, sin_start, edge_start), (end, sin_end, edge_end) = crossings[i], crossings[i + 1]

        setback_start = -extra[edge_start] if edge_start in extra \
            else edge_setback(cover, sin_start, max_setback)
        setback_end = -extra[edge_end] if edge_end in extra \
            else edge_setback(cover, sin_end, max_setback)

        if as_hole:
            intervals.append((start - setback_start, end + setback_end))
        else:
            intervals.append((start + setback_start, end - setback_end))

    return intervals


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
    # analog zur AdditionalCover-Regel der linearen Placements. Der Zusatzstab
    # muss mindestens den halben Stababstand entfernt sein, sonst läge er
    # praktisch auf seinem Nachbarn.
    if end - positions[-1] > spacing / 2.0:
        positions.append(end)

    return positions


def parallel_edges(loop: Loop, run_axis: int,
                   tol: float = 1e-6) -> list[tuple[float, float, float]]:
    """Kanten, die **parallel** zur Stabrichtung verlaufen.

    Returns:
        Liste (dist-Koordinate der Kante, Ausdehnung von, Ausdehnung bis)
        auf der run-Achse.
    """

    dist_axis = 1 - run_axis
    edges: list[tuple[float, float, float]] = []

    for i, p1 in enumerate(loop):
        p2 = loop[(i + 1) % len(loop)]

        if abs(p1[dist_axis] - p2[dist_axis]) > tol:
            continue

        run_from, run_to = sorted((p1[run_axis], p2[run_axis]))

        if run_to - run_from > tol:
            edges.append((p1[dist_axis], run_from, run_to))

    return edges


def _parallel_cover_holes(position: float,
                          edges: list[tuple[float, float, float]],
                          margin: float,
                          tol: float = 1e-6) -> list[Interval]:
    """Sperrbereiche auf der run-Achse für eine Scan-Position.

    Liegt die Position innerhalb der Betondeckung einer stabparallelen
    Kante (Hilfsparallele), darf der Stab auf deren Ausdehnung nicht
    verlaufen — er wird dort abgeschnitten statt komplett zu entfallen,
    damit der Rest der Platte weiter bewehrt bleibt. Der Sperrbereich
    ist an beiden Enden um die Deckung verlängert, damit auch zur
    anschliessenden Querkante (Ecke) die Deckung eingehalten ist.
    """

    return [(edge_from - margin, edge_to + margin)
            for coord, edge_from, edge_to in edges
            if abs(position - coord) < margin - tol]


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
                         edge_zone_spacing: float = 0.0,
                         max_setback: float = 0.0,
                         dist_margin: float | None = None,
                         edge_extensions: dict[int, float] | None = None) -> list[ContourBar]:
    """Scanline-Verlegung: für jede Scan-Position die Stab-Segmente
    innerhalb der Kontur abzüglich der Öffnungen.

    Die zurückgegebenen Segmente sind **Nettomasse**: Die Betondeckung ist
    bereits abgezogen, und zwar senkrecht zur jeweils geschnittenen Kante
    (an Schrägen also mit dem größeren Rückversatz cover/sin(alpha), nach
    oben begrenzt durch max_setback). Ränder von Öffnungen erhalten
    dieselbe Deckung.

    dist_margin ist der Randabstand der **Stabachsen** auf der dist-Achse
    (Default: side_cover). Da die Deckung bis zur Staboberfläche gilt,
    sollte hier side_cover + Stabdurchmesser/2 übergeben werden.
    Segmente kürzer als min_bar_length entfallen.
    """

    dist_axis = 1 - run_axis
    bbox = loop_bbox(contour)

    margin = side_cover if dist_margin is None else dist_margin

    dist_min = bbox[dist_axis] + margin
    dist_max = bbox[dist_axis + 2] - margin

    bars: list[ContourBar] = []

    # Hilfsparallelen: jede stabparallele Kante sperrt ihren
    # Deckungsstreifen — dort dürfen KEINE Eisen liegen. Für die
    # bbox-Ränder erledigt das bereits margin; einspringende Konturkanten
    # (L-Form, Vorsprünge) und **alle Aussparungskanten** sperren
    # zusätzlich: um die Aussparung liegt eine nach aussen um die Deckung
    # verbreiterte Zone, in der die Stäbe abgeschnitten werden.
    blocking_edges = parallel_edges(contour, run_axis)

    for opening in openings:
        blocking_edges += parallel_edges(opening, run_axis)

    for position in scan_positions(dist_min, dist_max, spacing,
                                   edge_zone_length, edge_zone_spacing):
        intervals = _intervals_at(contour, run_axis, position,
                                  side_cover, max_setback,
                                  extensions=edge_extensions)

        holes: list[Interval] = _parallel_cover_holes(position, blocking_edges,
                                                      margin)
        for opening in openings:
            holes += _intervals_at(opening, run_axis, position,
                                   side_cover, max_setback, as_hole=True)

        segments = tuple(
            (seg_from, seg_to)
            for seg_from, seg_to in _subtract_intervals(intervals, holes)
            if seg_to - seg_from >= min_bar_length)

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


def _round_inward(seg: Interval, raster: float) -> Interval:
    """Rundet ein Segment auf das Raster — beide Enden nach innen, damit der
    Stab nie über die Betonkante hinauswächst.
    """

    if raster <= 0:
        return seg

    seg_from = math.ceil(seg[0] / raster - 1e-9) * raster
    seg_to = math.floor(seg[1] / raster + 1e-9) * raster

    return (seg_from, seg_to) if seg_to > seg_from else seg


def group_bars_into_steps(bars: list[ContourBar],
                          max_step_loss: float,
                          length_raster: float = 0.0,
                          min_bar_length: float = 0.0,
                          tol: float = 1.0) -> list[BarRun]:
    """Fasst Stablinien zu Abtreppungsstufen zusammen.

    Regel (eine einzige, nachvollziehbare Bedingung):
        Aufeinanderfolgende Stäbe bilden eine Stufe, solange **kein** Stab
        der Stufe dadurch mehr als `max_step_loss` kürzer wird, als er
        geometrisch sein könnte. Alle Stäbe einer Stufe bekommen dieselben
        Segmente: Anfang = größter Anfang, Ende = kleinstes Ende der Stufe.
        Damit ragt kein Stab über die Betonkante (abzüglich Deckung) hinaus,
        und die unbewehrte Zone an der Schräge ist durch max_step_loss
        begrenzt.

    Zusätzlich bricht eine Stufe ab, wenn sich die Segmentanzahl ändert
    (z. B. am Beginn einer Öffnung) oder der Stababstand wechselt.

    Bei einer rechtwinkligen Platte sind alle Stäbe gleich lang, der Verlust
    ist immer 0 — es entsteht genau ein Lauf über die gesamte Lage.

    Args:
        bars:           Stablinien aus compute_contour_bars
        max_step_loss:  zulässige Verkürzung je Stab [mm]; 0 = keine
                        Abtreppung (jeder abweichende Stab einzeln)
        length_raster:  Stablängen zusätzlich auf dieses Raster nach innen
                        runden (0 = aus)
        min_bar_length: Segmente, die nach Vereinheitlichung und Rundung
                        kürzer sind, entfallen
        tol:            Toleranz für "gleich"

    Returns:
        Liste der Stufen als BarRun (Positionen + gemeinsame Segmente)
    """

    def unify(group: list[ContourBar]) -> tuple[Interval, ...]:
        return tuple((max(bar.segments[i][0] for bar in group),
                      min(bar.segments[i][1] for bar in group))
                     for i in range(len(group[0].segments)))

    def worst_loss(group: list[ContourBar], unified: tuple[Interval, ...]) -> float:
        return max(abs(bar.segments[i][0] - unified[i][0]) +
                   abs(bar.segments[i][1] - unified[i][1])
                   for bar in group for i in range(len(unified)))

    steps: list[BarRun] = []
    group: list[ContourBar] = []

    def flush():
        if not group:
            return

        unified = unify(group)

        if length_raster > 0:
            unified = tuple(_round_outward(seg, length_raster) for seg in unified)

        # Vereinheitlichung und Rundung verkürzen die Stäbe noch einmal —
        # deshalb hier erneut gegen die Mindestlänge prüfen
        unified = tuple(seg for seg in unified if seg[1] - seg[0] >= min_bar_length)

        if not unified:
            return

        steps.append(BarRun([bar.position for bar in group], unified))

    for bar in bars:
        if group:
            same_shape = len(bar.segments) == len(group[0].segments)
            gap = bar.position - group[-1].position
            same_gap = len(group) < 2 or abs(gap - (group[1].position - group[0].position)) <= tol

            if same_shape and same_gap and worst_loss(group + [bar], unify(group + [bar])) <= max_step_loss:
                group.append(bar)
                continue

            flush()

        group = [bar]

    flush()

    # Stufen mit identischen Segmenten und gleichem Abstand wieder
    # zusammenfassen (Rechteckbereiche ergeben so einen einzigen Lauf)
    merged: list[BarRun] = []

    for step in steps:
        if merged:
            previous = merged[-1]
            gap = step.positions[0] - previous.positions[-1]
            gaps_ok = (len(previous.positions) < 2 or abs(gap - previous.spacing) <= tol) and \
                      (len(step.positions) < 2 or abs(gap - step.spacing) <= tol)

            if gaps_ok and len(previous.segments) == len(step.segments) and \
                    all(abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol
                        for a, b in zip(previous.segments, step.segments)):
                previous.positions.extend(step.positions)
                continue

        merged.append(step)

    return merged


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


# ===================================================================
# Rechteck-Zerlegung (Verlegekonzept in drei Schritten)
#
# Schritt 1: Die Kontur wird in achsparallele Rechtecke zerlegt. Getrennt
#            wird dort, wo die Kontur eine zur Stabrichtung parallele Kante
#            hat — dort springt die Stablänge.
# Schritt 2: Je Rechteck EINE gemeinsame Stosslage (nicht je Stab).
# Schritt 3: Je Rechteck eine Verlegung; Abtreppung und Stösse zerteilen sie.
#
# Schräge Ränder erzeugen zusätzlich eine Abtreppungszone: der über alle
# Stäbe gemeinsame Teil bleibt Rechteck, der veränderliche Teil wird
# abgetreppt.
# ===================================================================


class PlacementZone(NamedTuple):
    """Ein Verlegebereich.

    kind:      'rect' = Rechteck (alle Stäbe gleich lang)
               'step' = Abtreppungszone an einer Schräge
    positions: Scan-Positionen der Stäbe
    segments:  je Position die Stabsegmente (bei 'rect' für alle gleich)
    """

    kind: str
    positions: list[float]
    segments: list[tuple[Interval, ...]]

    @property
    def spacing(self) -> float:
        if len(self.positions) < 2:
            return 0.0
        return self.positions[1] - self.positions[0]


def bar_parallel_breaks(contour: Loop, run_axis: int, tol: float = 1.0) -> list[float]:
    """dist-Koordinaten, an denen die Kontur eine zur Stabrichtung parallele
    Kante besitzt — dort springt die Stablänge, dort trennen die Rechtecke.
    """

    dist_axis = 1 - run_axis

    breaks = {p1[dist_axis]
              for i, p1 in enumerate(contour)
              if abs(p1[dist_axis] - contour[(i + 1) % len(contour)][dist_axis]) <= tol}

    return sorted(breaks)


def _split_at_breaks(bars: list[ContourBar], breaks: list[float]) -> list[list[ContourBar]]:
    """Teilt die Stablinien an den Sprungstellen in Gruppen."""

    groups: list[list[ContourBar]] = []
    current: list[ContourBar] = []
    limits = [b for b in breaks]

    for bar in bars:
        if current:
            previous = current[-1].position
            if any(previous < limit <= bar.position for limit in limits):
                groups.append(current)
                current = []

        current.append(bar)

    if current:
        groups.append(current)

    return groups


def decompose_into_zones(bars: list[ContourBar],
                         contour: Loop,
                         run_axis: int,
                         max_step_deviation: float,
                         length_raster: float = 0.0,
                         min_bar_length: float = 0.0,
                         snap_to_contour: bool = True,
                         step_reference: str = LONGEST) -> list[PlacementZone]:
    """Zerlegt die Stablinien in Rechteck- und Abtreppungszonen.

    Je zusammenhängendem Bereich (zwischen zwei Sprungstellen) wird der
    Teil, den alle Stäbe gemeinsam haben, zu einem Rechteck; was darüber
    oder darunter hinausragt, wird abgetreppt.

    snap_to_contour (Variante A): Die Rechteckgrenze wird zusätzlich auf
    die nächstgelegene Konturkante quer zur Stabrichtung gezogen, sodass
    die Rechtecke über die Bänder hinweg fluchten. Ohne diese Option
    (Variante B) endet das Rechteck genau dort, wo die Schräge beginnt.
    """

    # Konturkoordinaten quer zur Stabrichtung = mögliche Rechteckgrenzen
    snap_at = bar_parallel_breaks(contour, 1 - run_axis) if snap_to_contour else []

    zones: list[PlacementZone] = []

    for group in _split_at_breaks(bars, bar_parallel_breaks(contour, run_axis)):
        if not group:
            continue

        count = len(group[0].segments)

        if any(len(bar.segments) != count for bar in group):
            # Öffnung o. ä. innerhalb der Gruppe: konservativ je Stab trennen
            zones += _steps_from_bars(group, max_step_deviation, length_raster,
                                      min_bar_length)
            continue

        # Gemeinsamer Teil aller Stäbe = Rechteck
        common = tuple((max(bar.segments[i][0] for bar in group),
                        min(bar.segments[i][1] for bar in group))
                       for i in range(count))

        # Variante A: Grenze auf eine Konturkante ziehen — aber nur an der
        # Seite, an der überhaupt eine Schräge (Rest) vorhanden ist
        if snap_at:
            common = tuple(_snap_common(common[i], snap_at, group, i, min_bar_length)
                           for i in range(count))

        rect = tuple(seg for seg in common if seg[1] - seg[0] >= min_bar_length)

        if rect:
            zones.append(PlacementZone('rect', [bar.position for bar in group],
                                       [rect] * len(group)))

        # Was über den gemeinsamen Teil hinausragt -> Abtreppung
        remainder: list[ContourBar] = []

        for bar in group:
            extra: list[Interval] = []

            for i, (seg_from, seg_to) in enumerate(bar.segments):
                below = (seg_from, common[i][0])
                above = (common[i][1], seg_to)

                extra += [seg for seg in (below, above)
                          if seg[1] - seg[0] >= min_bar_length]

            if extra:
                remainder.append(ContourBar(bar.position, tuple(extra)))

        if remainder:
            zones += _steps_from_bars(remainder, max_step_deviation,
                                      length_raster, min_bar_length,
                                      reference=step_reference)

    return zones


def _steps_from_bars(bars: list[ContourBar],
                     max_step_deviation: float,
                     length_raster: float,
                     min_bar_length: float,
                     tol: float = 1.0,
                     reference: str = LONGEST) -> list[PlacementZone]:
    """Abtreppung: Stäbe werden zu Stufen gruppiert; alle Stäbe einer Stufe
    haben dieselbe Länge.

    reference bestimmt, woran diese Länge gemessen wird:
        LONGEST  — am **längsten** Stab der Stufe. Die kürzeren Stäbe
                   ragen dann um bis zu max_step_deviation über ihre
                   eigene geometrische Länge hinaus, also in die
                   seitliche Betondeckung hinein und darüber hinaus.
        SHORTEST — am **kürzesten** Stab der Stufe. Kein Stab verlässt
                   den Beton; die längeren werden um bis zu
                   max_step_deviation verkürzt.

    Das Längenraster rundet in Richtung des Referenzstabes: bei LONGEST
    nach aussen (die Stufe folgt der Schräge, wie vom Anwender vorgegeben),
    bei SHORTEST nach innen — dort darf die Rundung die gerade erst
    gesicherte Deckung nicht wieder auffressen.
    """

    def enclosing(group: list[ContourBar]) -> tuple[Interval, ...]:
        count = len(group[0].segments)

        if reference == SHORTEST:
            return tuple((max(bar.segments[i][0] for bar in group),
                          min(bar.segments[i][1] for bar in group))
                         for i in range(count))

        return tuple((min(bar.segments[i][0] for bar in group),
                      max(bar.segments[i][1] for bar in group))
                     for i in range(count))

    def worst_overshoot(group: list[ContourBar], unified: tuple[Interval, ...]) -> float:
        return max(abs(bar.segments[i][0] - unified[i][0]) +
                   abs(unified[i][1] - bar.segments[i][1])
                   for bar in group for i in range(len(unified)))

    zones: list[PlacementZone] = []
    group: list[ContourBar] = []

    def flush():
        if not group:
            return

        unified = enclosing(group)

        if length_raster > 0:
            round_to_raster = _round_inward if reference == SHORTEST else _round_outward

            unified = tuple(round_to_raster(seg, length_raster) for seg in unified)

        unified = tuple(seg for seg in unified if seg[1] - seg[0] >= min_bar_length)

        if unified:
            zones.append(PlacementZone('step', [bar.position for bar in group],
                                       [unified] * len(group)))

    for bar in bars:
        if group:
            same_shape = len(bar.segments) == len(group[0].segments)
            gap = bar.position - group[-1].position
            same_gap = len(group) < 2 or abs(gap - (group[1].position - group[0].position)) <= tol

            if same_shape and same_gap and \
                    worst_overshoot(group + [bar], enclosing(group + [bar])) <= max_step_deviation:
                group.append(bar)
                continue

            flush()

        group = [bar]

    flush()

    return _merge_single_bar_zones(zones)


def _snap_common(seg: Interval,
                 snap_at: list[float],
                 group: list[ContourBar],
                 index: int,
                 min_bar_length: float) -> Interval:
    """Zieht die Rechteckgrenze auf eine Konturkante quer zur Stabrichtung.

    Nur die Seite wird gezogen, an der ein Stab über den gemeinsamen Teil
    hinausragt — an einer geraden Kante bleibt das Rechteck unangetastet.
    """

    lo, hi = seg

    has_upper_rest = any(bar.segments[index][1] > hi + 1.0 for bar in group)
    has_lower_rest = any(bar.segments[index][0] < lo - 1.0 for bar in group)

    if has_upper_rest:
        below = [b for b in snap_at if lo + min_bar_length <= b < hi]
        if below:
            hi = max(below)

    if has_lower_rest:
        above = [b for b in snap_at if lo < b <= hi - min_bar_length]
        if above:
            lo = min(above)

    return (lo, hi)


def _merge_single_bar_zones(zones: list[PlacementZone]) -> list[PlacementZone]:
    """Vermeidet Verlegungen mit nur einem Stab: Der einzelne Stab wird der
    Nachbarverlegung zugeschlagen, die dafür verlängert wird.
    """

    merged: list[PlacementZone] = []

    for zone in zones:
        if len(zone.positions) == 1 and merged and \
                len(merged[-1].segments[0]) == len(zone.segments[0]):
            previous = merged[-1]
            previous.positions.append(zone.positions[0])
            previous.segments.append(previous.segments[0])
            continue

        merged.append(zone)

    # Führt die Liste mit einem Einzelstab an, wird er der folgenden
    # Verlegung zugeschlagen
    if len(merged) > 1 and len(merged[0].positions) == 1 and \
            len(merged[1].segments[0]) == len(merged[0].segments[0]):
        following = merged[1]
        following.positions.insert(0, merged[0].positions[0])
        following.segments.insert(0, following.segments[0])
        merged.pop(0)

    return merged


def _round_outward(seg: Interval, raster: float) -> Interval:
    """Rundet ein Segment auf das Raster — beide Enden nach aussen, passend
    zur Vermessung am längsten Stab der Stufe.
    """

    if raster <= 0:
        return seg

    return (math.floor(seg[0] / raster + 1e-9) * raster,
            math.ceil(seg[1] / raster - 1e-9) * raster)


def apply_boundary_laps(zones: list[PlacementZone],
                        lap_length: float,
                        tol: float = 60.0) -> list[PlacementZone]:
    """Schritt 2: Übergreifung an jeder Verlegungsgrenze längs der Stäbe.

    Wo zwei Verlegungen in Stabrichtung aneinanderstossen (typisch Rechteck
    und angrenzende Abtreppungszone), müssen sie sich um die
    Übergreifungslänge überlappen — sonst wäre der Stab dort nur gestossen
    ohne Übergreifung. Verlängert wird die **Abtreppungszone** in das
    Rechteck hinein; das Rechteck bleibt unverändert, damit die
    Rechteckgrenze die Stosslage definiert.
    """

    if lap_length <= 0:
        return zones

    rects = [z for z in zones if z.kind == 'rect']
    result: list[PlacementZone] = []

    for zone in zones:
        if zone.kind != 'step':
            result.append(zone)
            continue

        segments = list(zone.segments[0])

        for rect in rects:
            # nur Rechtecke, die dieselben Stäbe tragen
            if rect.positions[-1] < zone.positions[0] - tol or \
                    rect.positions[0] > zone.positions[-1] + tol:
                continue

            for r_lo, r_hi in rect.segments[0]:
                for index, (s_lo, s_hi) in enumerate(segments):
                    if abs(s_hi - r_lo) <= tol:          # Stufe endet am Rechteck
                        segments[index] = (s_lo, r_lo + lap_length)
                    elif abs(s_lo - r_hi) <= tol:        # Stufe beginnt am Rechteck
                        segments[index] = (r_hi - lap_length, s_hi)

        unified = tuple(segments)
        result.append(PlacementZone(zone.kind, zone.positions,
                                    [unified] * len(zone.positions)))

    return result
