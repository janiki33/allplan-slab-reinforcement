"""Reine Geometrie der Aussparungsbewehrung — beliebige (auch schiefe)
Öffnungspolygone.

Wie contour_placement.py bewusst OHNE Allplan-Abhängigkeit, damit die
Logik ohne Allplan testbar bleibt.

Der Unterschied zum Rechteckmodus: Dort liegt die Öffnung achsparallel im
Plattenraster und die Zulagen fallen mit den Hauptrichtungen zusammen.
Hier läuft je Öffnungskante eine Schar Zulagestäbe **parallel zu dieser
Kante** — also in beliebiger Richtung — mit Überstand um die
Übergreifungslänge über die Ecken hinaus. Jeder Stab wird anschliessend
an der Plattenkontur und an allen anderen Öffnungen abgeschnitten.

Konventionen wie in contour_placement.py: Loop = Punktliste ohne
wiederholten Endpunkt, zyklisch interpretiert.
"""

from __future__ import annotations

import math
from typing import NamedTuple

Point = tuple[float, float]
Loop = list[Point]
Segment = tuple[Point, Point]


def signed_area(loop: Loop) -> float:
    """Vorzeichenbehaftete Fläche (positiv bei Gegenuhrzeigersinn)."""

    area = 0.0

    for i, (x1, y1) in enumerate(loop):
        x2, y2 = loop[(i + 1) % len(loop)]
        area += x1 * y2 - x2 * y1

    return area / 2.0


def point_in_loop(point: Point, loop: Loop) -> bool:
    """Punkt-in-Polygon (Ray-Casting, halboffene Kantenregel)."""

    x, y = point
    inside = False

    for i, (x1, y1) in enumerate(loop):
        x2, y2 = loop[(i + 1) % len(loop)]

        if (y1 > y) != (y2 > y):
            t = (y - y1) / (y2 - y1)

            if x < x1 + t * (x2 - x1):
                inside = not inside

    return inside


def outward_normals(loop: Loop) -> list[tuple[float, float]]:
    """Einheits-Aussennormale je Kante — bei einem Öffnungspolygon zeigt
    sie vom Loch weg in den Beton hinein.
    """

    sign = 1.0 if signed_area(loop) > 0 else -1.0

    normals = []

    for i, (x1, y1) in enumerate(loop):
        x2, y2 = loop[(i + 1) % len(loop)]

        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)

        if length < 1e-9:
            normals.append((0.0, 0.0))
            continue

        normals.append((sign * dy / length, -sign * dx / length))

    return normals


class EdgeBar(NamedTuple):
    """Ein Zulagestab: Strecke plus die Kante, zu der er gehört."""

    start: Point
    end: Point
    edge_index: int
    offset: float

    @property
    def angle(self) -> float:
        """Richtungswinkel in Grad (für die Shape-Rotation)."""

        return math.degrees(math.atan2(self.end[1] - self.start[1],
                                       self.end[0] - self.start[0]))

    @property
    def length(self) -> float:
        return math.hypot(self.end[0] - self.start[0], self.end[1] - self.start[1])


def opening_edge_bars(loop: Loop,
                      bar_count: int,
                      first_offset: float,
                      spacing: float,
                      lap: float,
                      min_edge_length: float = 1.0) -> list[EdgeBar]:
    """Zulagestäbe parallel zu jeder Öffnungskante.

    first_offset ist der Abstand der ersten Stabachse von der Kante,
    spacing der Achsabstand der weiteren Stäbe, lap der Überstand über
    beide Kantenenden hinaus (Übergreifungslänge).
    """

    if bar_count <= 0:
        return []

    normals = outward_normals(loop)
    bars: list[EdgeBar] = []

    for i, (x1, y1) in enumerate(loop):
        x2, y2 = loop[(i + 1) % len(loop)]

        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)

        if length < min_edge_length:
            continue

        tx, ty = dx / length, dy / length
        nx, ny = normals[i]

        for index in range(bar_count):
            offset = first_offset + index * spacing

            bars.append(EdgeBar(
                (x1 + nx * offset - tx * lap, y1 + ny * offset - ty * lap),
                (x2 + nx * offset + tx * lap, y2 + ny * offset + ty * lap),
                i, offset))

    return bars


def corner_diagonals(loop: Loop,
                     bar_count: int,
                     offset: float,
                     length: float,
                     spacing: float,
                     min_angle: float = 20.0) -> list[EdgeBar]:
    """Diagonalstäbe über die Öffnungsecken.

    Je Ecke wird die Winkelhalbierende nach aussen bestimmt; der Stab liegt
    **senkrecht** dazu, überspannt die Ecke also diagonal. Weitere Stäbe
    liegen parallel dahinter (spacing nach aussen).

    Nur an Ecken, an denen die Kanten deutlich abknicken (min_angle) — an
    einem fast geraden Durchlauf gibt es keine Ecke zu sichern.
    """

    if bar_count <= 0 or length <= 0:
        return []

    normals = outward_normals(loop)
    bars: list[EdgeBar] = []

    for i, corner in enumerate(loop):
        previous_normal = normals[i - 1]
        next_normal = normals[i]

        bx, by = previous_normal[0] + next_normal[0], previous_normal[1] + next_normal[1]
        bisector_length = math.hypot(bx, by)

        if bisector_length < 1e-9:
            continue

        # Knickwinkel zwischen den beiden Kantennormalen
        dot = max(-1.0, min(1.0, previous_normal[0] * next_normal[0]
                            + previous_normal[1] * next_normal[1]))

        if math.degrees(math.acos(dot)) < min_angle:
            continue

        bx, by = bx / bisector_length, by / bisector_length

        # Stabrichtung senkrecht zur Winkelhalbierenden
        tx, ty = -by, bx

        for index in range(bar_count):
            distance = offset + index * spacing

            centre = (corner[0] + bx * distance, corner[1] + by * distance)

            bars.append(EdgeBar(
                (centre[0] - tx * length / 2.0, centre[1] - ty * length / 2.0),
                (centre[0] + tx * length / 2.0, centre[1] + ty * length / 2.0),
                i, distance))

    return bars


def _crossings(segment: Segment, loop: Loop) -> list[tuple[float, float]]:
    """Schnittparameter t der Strecke mit den Kanten des Loops.

    Returns:
        Liste (t, sin des Winkels zwischen Strecke und geschnittener
        Kante), aufsteigend nach t.
    """

    (px, py), (qx, qy) = segment
    rx, ry = qx - px, qy - py

    if abs(rx) < 1e-12 and abs(ry) < 1e-12:
        return []

    result: list[tuple[float, float]] = []

    for i, (x1, y1) in enumerate(loop):
        x2, y2 = loop[(i + 1) % len(loop)]

        sx, sy = x2 - x1, y2 - y1

        denominator = rx * sy - ry * sx

        if abs(denominator) < 1e-12:
            continue

        t = ((x1 - px) * sy - (y1 - py) * sx) / denominator
        u = ((x1 - px) * ry - (y1 - py) * rx) / denominator

        if not (0.0 <= t <= 1.0 and 0.0 <= u <= 1.0):
            continue

        segment_length = math.hypot(rx, ry)
        edge_length = math.hypot(sx, sy)

        sin_alpha = abs(rx * sy - ry * sx) / (segment_length * edge_length)

        result.append((t, sin_alpha))

    result.sort()

    return result


def clip_bar(bar: EdgeBar,
             contour: Loop,
             holes: list[Loop],
             cover: float = 0.0,
             max_setback: float = 0.0,
             min_length: float = 0.0) -> list[EdgeBar]:
    """Schneidet einen Zulagestab an der Plattenkontur und an allen
    Öffnungen ab.

    An jedem Schnitt wird zusätzlich die Betondeckung **senkrecht zur
    geschnittenen Kante** abgezogen (an Schrägen also cover/sin alpha,
    begrenzt durch max_setback) — dieselbe Regel wie bei den Hauptlagen.
    Die ursprünglichen Stabenden bleiben unangetastet: dort endet der Stab
    nicht an einer Betonkante, sondern weil seine Länge zu Ende ist.
    """

    segment = (bar.start, bar.end)

    breaks: list[tuple[float, float]] = []

    for loop in [contour] + list(holes):
        breaks += _crossings(segment, loop)

    breaks.sort()

    limits = [0.0] + [t for t, _ in breaks] + [1.0]
    setbacks = {t: sin_alpha for t, sin_alpha in breaks}

    (px, py), (qx, qy) = segment
    rx, ry = qx - px, qy - py
    total = math.hypot(rx, ry)

    if total < 1e-9:
        return []

    pieces: list[EdgeBar] = []

    for lo, hi in zip(limits, limits[1:]):
        if hi - lo < 1e-9:
            continue

        middle = (px + rx * (lo + hi) / 2.0, py + ry * (lo + hi) / 2.0)

        if not point_in_loop(middle, contour):
            continue

        if any(point_in_loop(middle, hole) for hole in holes):
            continue

        start_setback = _setback(cover, setbacks.get(lo), max_setback) if lo > 0 else 0.0
        end_setback = _setback(cover, setbacks.get(hi), max_setback) if hi < 1.0 else 0.0

        lo_length = lo * total + start_setback
        hi_length = hi * total - end_setback

        if hi_length - lo_length < max(min_length, 1e-9):
            continue

        pieces.append(EdgeBar(
            (px + rx * lo_length / total, py + ry * lo_length / total),
            (px + rx * hi_length / total, py + ry * hi_length / total),
            bar.edge_index, bar.offset))

    return pieces


def _setback(cover: float, sin_alpha: float | None, max_setback: float) -> float:
    """Rückversatz entlang der Stabachse für die Deckung senkrecht zur
    geschnittenen Kante — identisch zu contour_placement.edge_setback.
    """

    if cover <= 0 or sin_alpha is None:
        return 0.0

    if sin_alpha <= 1e-6:
        return max_setback if max_setback > 0 else cover

    setback = cover / sin_alpha

    if max_setback > 0:
        setback = min(setback, max_setback)

    return setback


def group_equal_bars(bars: list[EdgeBar],
                     tol: float = 1.0) -> list[list[EdgeBar]]:
    """Fasst aufeinanderfolgende Stäbe derselben Kante zusammen, die gleich
    lang sind und gleichen Achsabstand haben — sie lassen sich als **eine**
    Verlegung absetzen statt als Einzelstäbe.
    """

    groups: list[list[EdgeBar]] = []

    for bar in bars:
        if groups:
            group = groups[-1]
            reference = group[-1]

            same_edge = bar.edge_index == reference.edge_index
            same_length = abs(bar.length - reference.length) <= tol
            gap = bar.offset - reference.offset
            same_gap = len(group) < 2 or \
                abs(gap - (group[1].offset - group[0].offset)) <= tol

            if same_edge and same_length and gap > tol and same_gap:
                group.append(bar)
                continue

        groups.append([bar])

    return groups
