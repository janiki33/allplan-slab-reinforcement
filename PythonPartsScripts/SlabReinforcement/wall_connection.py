"""Reine Geometrie der Wand-Anschlusseisen.

Der Anwender wählt 3D-Wände, die auf der Platte stehen; entlang der langen
Wandseiten entstehen L-förmige Anschlusseisen: vertikaler Schenkel an der
Wandseite (Stoss mit der Wandbewehrung, ragt um die Stosslänge über OK
Platte), horizontaler Schenkel unten in der Platte, von der Wand weg.

Vorbild ist das Büro-PythonPart "AnschlusseisenBew" (WandanschlussBew,
Fall 2: getrennte innere/äussere L-Eisen): dort läuft je Wandseite eine
Verlegung, der Schenkel zeigt von der Wand weg, die automatische
Schenkellänge ist die Stosslänge abzüglich des in der Plattendicke
verfügbaren Verankerungswegs.

Wie die übrigen Geometriemodule bewusst OHNE Allplan-Abhängigkeit und in
sich geschlossen, damit die Logik ohne Allplan testbar bleibt.
Konventionen wie in contour_placement.py: Loop = Punktliste ohne
wiederholten Endpunkt, zyklisch interpretiert.
"""

from __future__ import annotations

import math
from typing import NamedTuple

Point = tuple[float, float]
Loop = list[Point]


class WallRun(NamedTuple):
    """Eine Verlegelinie entlang einer Wandseite.

    from_pnt/to_pnt liegen AUF der Wandseite (die Deckung übernimmt die
    Biegeform bzw. der Placement-Builder); outward_deg ist der Winkel der
    Aussennormalen in Grad — die Richtung, in die der Plattenschenkel
    zeigt (von der Wand weg).
    """

    from_pnt: Point
    to_pnt: Point
    outward_deg: float


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
    """Einheits-Aussennormale je Kante i (von Punkt i nach Punkt i+1)."""

    ccw = signed_area(loop) > 0
    normals = []

    for i, (x1, y1) in enumerate(loop):
        x2, y2 = loop[(i + 1) % len(loop)]

        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1.0

        # Bei Gegenuhrzeigersinn zeigt (dy, -dx) nach aussen
        nx, ny = (dy / length, -dx / length) if ccw else (-dy / length, dx / length)
        normals.append((nx, ny))

    return normals


def wall_thickness(loop: Loop) -> float:
    """Wanddicke: kleinste Ausdehnung des Grundrisses senkrecht zu einer
    seiner Kantenrichtungen (exakt für Rechtecke in beliebiger Drehung,
    brauchbar für L-/T-förmige Wandzüge).
    """

    best = float('inf')

    for i, (x1, y1) in enumerate(loop):
        x2, y2 = loop[(i + 1) % len(loop)]

        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)

        if length < 1.0:
            continue

        # Ausdehnung aller Punkte senkrecht zu dieser Kantenrichtung
        nx, ny = -dy / length, dx / length
        dots = [px * nx + py * ny for px, py in loop]
        best = min(best, max(dots) - min(dots))

    return best if best != float('inf') else 0.0


def clip_segment_to_loop(a: Point, b: Point, loop: Loop) -> list[tuple[float, float]]:
    """Parameterintervalle (t0, t1) von Strecke a->b, die im Loop liegen.

    Schnittparameter mit allen Loop-Kanten sammeln, sortieren, jedes
    Teilstück über seinen Mittelpunkt klassifizieren.
    """

    ax, ay = a
    dx, dy = b[0] - a[0], b[1] - a[1]

    params = [0.0, 1.0]

    for i, (x1, y1) in enumerate(loop):
        x2, y2 = loop[(i + 1) % len(loop)]

        ex, ey = x2 - x1, y2 - y1
        denom = dx * ey - dy * ex

        if abs(denom) < 1e-12:
            continue

        t = ((x1 - ax) * ey - (y1 - ay) * ex) / denom
        u = ((x1 - ax) * dy - (y1 - ay) * dx) / denom

        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
            params.append(t)

    params = sorted(set(params))
    inside: list[tuple[float, float]] = []

    for t0, t1 in zip(params, params[1:]):
        if t1 - t0 < 1e-9:
            continue

        mid = (ax + dx * (t0 + t1) / 2.0, ay + dy * (t0 + t1) / 2.0)

        if point_in_loop(mid, loop):
            if inside and abs(inside[-1][1] - t0) < 1e-9:
                inside[-1] = (inside[-1][0], t1)
            else:
                inside.append((t0, t1))

    return inside


def wall_connection_runs(wall_loop: Loop,
                         slab_contour: Loop,
                         min_run_length: float,
                         face_factor: float = 1.6) -> list[WallRun]:
    """Verlegelinien der Anschlusseisen für einen Wandgrundriss.

    Je Wandkante, die länger ist als face_factor x Wanddicke (damit die
    kurzen Stirnseiten der Wand keine Eisen bekommen), wird die Kante an
    der Plattenkontur abgeschnitten — Wände dürfen über die Platte
    hinauslaufen. Teilstücke unter min_run_length entfallen.
    """

    if len(wall_loop) < 3 or len(slab_contour) < 3:
        return []

    thickness = wall_thickness(wall_loop)
    min_face = face_factor * thickness

    normals = outward_normals(wall_loop)
    runs: list[WallRun] = []

    for i, start in enumerate(wall_loop):
        end = wall_loop[(i + 1) % len(wall_loop)]

        dx, dy = end[0] - start[0], end[1] - start[1]
        length = math.hypot(dx, dy)

        if length <= min_face or length < min_run_length:
            continue

        outward_deg = math.degrees(math.atan2(normals[i][1], normals[i][0]))

        for t0, t1 in clip_segment_to_loop(start, end, slab_contour):
            if (t1 - t0) * length < min_run_length:
                continue

            runs.append(WallRun((start[0] + dx * t0, start[1] + dy * t0),
                                (start[0] + dx * t1, start[1] + dy * t1),
                                outward_deg))

    return runs


def auto_leg_length(lap_length: float,
                    thickness: float,
                    cover_bottom: float,
                    cover_top: float,
                    min_leg: float) -> float:
    """Automatische Länge des Plattenschenkels (Vorbild Büro-PythonPart):
    Stosslänge abzüglich des in der Plattendicke verfügbaren
    Verankerungswegs, mindestens min_leg, auf 10 mm abgerundet.
    """

    available = thickness - cover_bottom - cover_top
    leg = max(lap_length - available, min_leg)

    return math.floor(leg / 10.0) * 10.0


def _footprint_signature(loop: Loop) -> tuple[float, float, float]:
    """Kennwerte eines Grundrisses für den Gleichheitsvergleich:
    Fläche und Schwerpunkt (unabhängig von Punktreihenfolge und Startpunkt).
    """

    area = signed_area(loop)

    if abs(area) < 1e-9:
        xs = [p[0] for p in loop]
        ys = [p[1] for p in loop]
        return (0.0, sum(xs) / len(xs), sum(ys) / len(ys))

    cx = cy = 0.0

    for i, (x1, y1) in enumerate(loop):
        x2, y2 = loop[(i + 1) % len(loop)]
        cross = x1 * y2 - x2 * y1
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross

    return (abs(area), cx / (6.0 * area), cy / (6.0 * area))


def same_footprint(a: Loop, b: Loop, tol: float = 1.0) -> bool:
    """Beschreiben zwei Grundrisse dieselbe Wand? Verglichen werden Fläche
    und Schwerpunkt mit Toleranz — robust gegen Punktreihenfolge und
    Rundung, ausreichend trennscharf für reale Wandstellungen.
    """

    area_a, cx_a, cy_a = _footprint_signature(a)
    area_b, cx_b, cy_b = _footprint_signature(b)

    if math.hypot(cx_a - cx_b, cy_a - cy_b) > tol:
        return False

    return abs(area_a - area_b) <= tol * max(1.0, math.sqrt(max(area_a, area_b)))


def toggle_walls(existing: list[Loop], picked: list[Loop]) -> list[Loop]:
    """Mehrfachauswahl-Verhalten: bereits erfasste Wände werden durch
    erneutes Wählen entfernt (abgewählt), neue kommen hinzu. Innerhalb
    einer Auswahlrunde doppelt getroffene Wände zählen einfach.
    """

    result = list(existing)

    for loop in picked:
        for index, kept in enumerate(result):
            if same_footprint(kept, loop):
                del result[index]
                break
        else:
            result.append(loop)

    return result
