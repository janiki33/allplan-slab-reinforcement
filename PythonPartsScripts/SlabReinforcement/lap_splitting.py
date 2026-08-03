"""Übergreifungsstösse: Zerlegung zu langer Stäbe in gestossene Teilstäbe.

Wie die übrigen Geometriemodule bewusst OHNE Allplan-Abhängigkeit, damit
die Stosslogik ohne Allplan getestet werden kann.

Konzept (die vollständige Begründung steht im README):

1. **Wann gestossen wird** — sobald die erforderliche Stablänge die
   zulässige Einzelstablänge (Lieferlänge, Palettenwert) überschreitet.
2. **Wie viele Teilstäbe** — die kleinste Anzahl n, mit der alle Teilstäbe
   die zulässige Länge einhalten; die Teilung erfolgt in gleich lange
   Stäbe, damit sich Bestellung und Verlegung vereinfachen.
3. **Wo gestossen wird** — die Stosslage wird innerhalb des zulässigen
   Spielraums so verschoben, dass die Stösse (a) zwischen benachbarten
   Stäben versetzt liegen und (b) möglichst weit von Sperrzonen
   (Öffnungsbereiche) entfernt sind.
4. **Versatz benachbarter Stäbe** — benachbarte Stäbe erhalten abwechselnd
   einen Stossversatz, damit nicht alle Stösse im selben Querschnitt
   liegen.

Alle Normwerte (Übergreifungslänge, geforderter Versatz, maximale
Stablänge) sind Parameter und werden NICHT fest codiert.
"""

from __future__ import annotations

import math

Interval = tuple[float, float]


def required_piece_count(total_length: float,
                         max_bar_length: float,
                         lap_length: float) -> int:
    """Kleinste Anzahl Teilstäbe, mit der alle die zulässige Länge einhalten.

    Bei n Teilstäben mit (n-1) Übergreifungen gilt
    Summe der Teillängen = Gesamtlänge + (n-1) x Übergreifungslänge,
    also n x max >= total + (n-1) x lap.
    """

    if total_length <= max_bar_length:
        return 1

    if max_bar_length <= lap_length:
        raise ValueError('Stablänge muss größer als die Übergreifungslänge sein')

    return max(2, math.ceil((total_length - lap_length) /
                            (max_bar_length - lap_length) - 1e-9))


def split_bar_with_laps(segment: Interval,
                        max_bar_length: float,
                        lap_length: float,
                        joint_shift: float = 0.0,
                        min_piece_length: float = 0.0) -> list[Interval]:
    """Zerlegt einen Stab in gestossene Teilstäbe.

    Die Teilstäbe überlappen sich jeweils um lap_length. Ohne joint_shift
    sind alle Teilstäbe gleich lang; ein joint_shift verschiebt sämtliche
    Stossfugen um diesen Betrag (der erste Teilstab wird länger, der letzte
    entsprechend kürzer) und wird dabei auf den zulässigen Bereich begrenzt.

    Returns:
        Liste der Teilstäbe als (von, bis); ohne Stoss genau ein Eintrag
    """

    seg_from, seg_to = segment
    total = seg_to - seg_from

    if total <= 0:
        return []

    count = required_piece_count(total, max_bar_length, lap_length)

    if count == 1:
        return [segment]

    base = (total + (count - 1) * lap_length) / count

    shift = clamp_joint_shift(joint_shift, base, max_bar_length,
                              max(min_piece_length, lap_length))

    pieces: list[Interval] = []
    start = seg_from

    for index in range(count):
        length = base

        if index == 0:
            length += shift
        elif index == count - 1:
            length -= shift

        pieces.append((start, start + length))
        start += length - lap_length

    return pieces


def clamp_joint_shift(joint_shift: float,
                      base_length: float,
                      max_bar_length: float,
                      min_piece_length: float) -> float:
    """Begrenzt die Stossverschiebung so, dass kein Teilstab zu lang oder
    zu kurz wird.
    """

    limit = min(max_bar_length - base_length, base_length - min_piece_length)

    if limit <= 0:
        return 0.0

    return max(-limit, min(limit, joint_shift))


def joint_positions(pieces: list[Interval], lap_length: float) -> list[float]:
    """Mitten der Stossfugen (zur Prüfung von Versatz und Sperrzonen)."""

    return [piece[1] - lap_length / 2.0 for piece in pieces[:-1]]


def _min_distance_to_zones(positions: list[float],
                           zones: list[Interval]) -> float:
    """Kleinster Abstand der Stossmitten zu den Sperrzonen.

    Liegt eine Stossmitte in einer Zone, ist das Ergebnis negativ (je
    tiefer drin, desto kleiner), sonst der Abstand zum nächsten Zonenrand.
    """

    if not positions:
        return float('inf')

    if not zones:
        return float('inf')

    worst = float('inf')

    for position in positions:
        best_for_position = float('inf')

        for zone_from, zone_to in zones:
            if zone_from <= position <= zone_to:
                best_for_position = min(best_for_position,
                                        -min(position - zone_from, zone_to - position))
            else:
                best_for_position = min(best_for_position,
                                        min(abs(position - zone_from),
                                            abs(position - zone_to)))

        worst = min(worst, best_for_position)

    return worst


def split_with_preferred_joints(segment: Interval,
                                max_bar_length: float,
                                lap_length: float,
                                preferred_shift: float = 0.0,
                                forbidden_zones: list[Interval] | None = None,
                                min_piece_length: float = 0.0,
                                search_steps: int = 24) -> list[Interval]:
    """Wie split_bar_with_laps, verschiebt die Stösse aber zusätzlich aus
    Sperrzonen heraus.

    Ausgangspunkt ist preferred_shift (der gewünschte Versatz gegenüber dem
    Nachbarstab). Liegt damit eine Stossfuge in einer Sperrzone, wird im
    zulässigen Bereich diejenige Verschiebung gesucht, die den kleinsten
    Abstand zu allen Sperrzonen maximiert und dabei möglichst nah am
    gewünschten Versatz bleibt.
    """

    zones = forbidden_zones or []

    pieces = split_bar_with_laps(segment, max_bar_length, lap_length,
                                 preferred_shift, min_piece_length)

    if len(pieces) == 1 or not zones:
        return pieces

    if _min_distance_to_zones(joint_positions(pieces, lap_length), zones) > 0:
        return pieces

    total = segment[1] - segment[0]
    count = len(pieces)
    base = (total + (count - 1) * lap_length) / count
    limit = clamp_joint_shift(float('inf'), base, max_bar_length,
                              max(min_piece_length, lap_length))

    best_pieces = pieces
    best_score = (_min_distance_to_zones(joint_positions(pieces, lap_length), zones), 0.0)

    for index in range(search_steps + 1):
        shift = -limit + (2 * limit) * index / max(search_steps, 1)

        candidate = split_bar_with_laps(segment, max_bar_length, lap_length,
                                        shift, min_piece_length)
        score = (_min_distance_to_zones(joint_positions(candidate, lap_length), zones),
                 -abs(shift - preferred_shift))

        if score > best_score:
            best_score = score
            best_pieces = candidate

    return best_pieces


def stagger_shift(bar_index: int, stagger_offset: float) -> float:
    """Gewünschter Stossversatz eines Stabes gegenüber seinen Nachbarn.

    Benachbarte Stäbe wechseln zwischen -offset/2 und +offset/2, sodass der
    Längsversatz zwischen zwei benachbarten Stössen genau stagger_offset
    beträgt.
    """

    return (-stagger_offset / 2.0) if bar_index % 2 == 0 else (stagger_offset / 2.0)
