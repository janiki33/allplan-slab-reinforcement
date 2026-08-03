"""Reine Geometrie-Hilfsfunktionen für das Kappen von Bewehrungsstäben an Öffnungen.

Dieses Modul hat bewusst KEINE Abhängigkeit zur Allplan-API, damit die
Band-/Segmentlogik ohne Allplan (z. B. mit pytest) getestet werden kann.

Koordinatenkonvention pro Bewehrungslage:
    - "run"-Achse:  Richtung, in der die Stäbe verlaufen (Stablänge)
    - "dist"-Achse: Richtung, in der die Stäbe verteilt werden (Stababstand)

Für eine Lage in X-Richtung ist run = globale X-Achse, dist = globale Y-Achse;
für eine Lage in Y-Richtung genau umgekehrt.
"""

from __future__ import annotations

from typing import NamedTuple


class PlacementBand(NamedTuple):
    """Ein Verlegeband: Bereich auf der dist-Achse mit Stab-Segmenten auf der run-Achse.

    dist_from/dist_to: Anfang/Ende des Bandes auf der Verteilachse
    run_segments:      Liste (run_from, run_to) der Stababschnitte; bei einem
                       Band ohne Öffnung genau ein Segment über die volle Länge
    """

    dist_from: float
    dist_to: float
    run_segments: list[tuple[float, float]]


def _overlap(a_min: float, a_max: float, b_min: float, b_max: float) -> bool:
    return a_min < b_max and b_min < a_max


def compute_placement_bands(dist_len: float,
                            run_len: float,
                            opening_dist: tuple[float, float] | None,
                            opening_run: tuple[float, float] | None,
                            min_band_width: float = 1.0,
                            min_segment_length: float = 1.0,
                            bonus_start: float = 0.0,
                            bonus_end: float = 0.0) -> list[PlacementBand]:
    """Zerlegt die Verlegefläche einer Lage in Bänder, in denen jeweils Stäbe
    gleicher Länge verlegt werden können.

    Ohne Öffnung (oder wenn die Öffnung die Fläche nicht schneidet) entsteht
    genau ein Band über die volle Fläche. Schneidet die Öffnung die Fläche,
    entstehen bis zu drei Bänder: vor der Öffnung, neben der Öffnung
    (mit gekappten Stäben links/rechts der Öffnung) und hinter der Öffnung.

    Args:
        dist_len:           Ausdehnung der Fläche entlang der Verteilachse
        run_len:            Ausdehnung der Fläche entlang der Stabrichtung
        opening_dist:       (min, max) der Öffnung auf der Verteilachse oder None
        opening_run:        (min, max) der Öffnung auf der Stabrichtung oder None
        min_band_width:     Bänder schmaler als dieser Wert werden verworfen
        min_segment_length: Stab-Segmente kürzer als dieser Wert werden verworfen
        bonus_start:        Zusatzlänge (z. B. Anschlusseisen-Überstand), die
                            einem am Rand run=0 endenden Segment beim
                            Mindestlängen-Test angerechnet wird
        bonus_end:          dito für den Rand run=run_len

    Returns:
        Liste der Verlegebänder in aufsteigender dist-Reihenfolge
    """

    full_band = PlacementBand(0.0, dist_len, [(0.0, run_len)])

    if dist_len <= 0 or run_len <= 0:
        return []

    if opening_dist is None or opening_run is None:
        return [full_band]

    d0 = max(opening_dist[0], 0.0)
    d1 = min(opening_dist[1], dist_len)
    r0 = max(opening_run[0], 0.0)
    r1 = min(opening_run[1], run_len)

    # Öffnung liegt komplett außerhalb der Fläche -> nichts zu kappen
    if d0 >= d1 or r0 >= r1 or \
            not _overlap(d0, d1, 0.0, dist_len) or not _overlap(r0, r1, 0.0, run_len):
        return [full_band]

    bands: list[PlacementBand] = []

    if d0 >= min_band_width:
        bands.append(PlacementBand(0.0, d0, [(0.0, run_len)]))

    clipped_segments = [(seg_from, seg_to)
                        for seg_from, seg_to in ((0.0, r0), (r1, run_len))
                        if (seg_to - seg_from)
                        + (bonus_start if seg_from == 0.0 else 0.0)
                        + (bonus_end if seg_to == run_len else 0.0)
                        >= min_segment_length]
    if clipped_segments:
        bands.append(PlacementBand(d0, d1, clipped_segments))

    if dist_len - d1 >= min_band_width:
        bands.append(PlacementBand(d1, dist_len, [(0.0, run_len)]))

    return bands


def compute_edge_strip_segments(dist_len: float,
                                opening_dist: tuple[float, float] | None,
                                opening_run: tuple[float, float] | None,
                                strip_run: tuple[float, float],
                                min_segment_length: float = 1.0) -> list[tuple[float, float]]:
    """Teilt die Verlegestrecke entlang einer Plattenkante (dist-Achse) in
    Abschnitte, die die Öffnung aussparen.

    Gedacht für Randbügel und separate Anschlusseisen: Deren Stäbe belegen
    senkrecht zur Kante den Randstreifen strip_run (Intervall auf der
    Stabrichtungs-Achse der Kante). Nur wenn die Öffnung diesen Streifen
    schneidet, wird die Verlegestrecke im Öffnungsbereich unterbrochen.

    Returns:
        Liste (dist_from, dist_to) der zu verlegenden Abschnitte
    """

    full = [(0.0, dist_len)]

    if dist_len <= 0:
        return []

    if opening_dist is None or opening_run is None:
        return full

    if not _overlap(opening_run[0], opening_run[1], strip_run[0], strip_run[1]):
        return full

    d0 = max(opening_dist[0], 0.0)
    d1 = min(opening_dist[1], dist_len)

    if d0 >= d1:
        return full

    return [(seg_from, seg_to)
            for seg_from, seg_to in ((0.0, d0), (d1, dist_len))
            if seg_to - seg_from >= min_segment_length]


class EdgeBarRun(NamedTuple):
    """Eine Schar Randverstärkungsstäbe an einer Öffnungskante.

    run_from/run_to:   Anfang/Ende der Stäbe entlang ihrer Stabrichtung
    dist_from/dist_to: Verlegezone senkrecht dazu (direkt neben der Öffnungskante)
    """

    run_from: float
    run_to: float
    dist_from: float
    dist_to: float


def compute_edge_bar_runs(dist_len: float,
                          run_len: float,
                          opening_dist: tuple[float, float],
                          opening_run: tuple[float, float],
                          lap_length: float,
                          zone_width: float) -> list[EdgeBarRun]:
    """Berechnet die beiden Randverstärkungs-Scharen parallel zur run-Achse
    (eine vor, eine hinter der Öffnung, bezogen auf die dist-Achse).

    Die Stäbe überragen die Öffnung beidseitig um die Übergreifungslänge
    lap_length, werden aber an den Plattenrändern gekappt. Die Verlegezone
    (Breite zone_width) liegt unmittelbar neben der Öffnungskante und wird
    ebenfalls an den Plattenrand geklemmt.

    Returns:
        0-2 EdgeBarRun-Einträge (eine Kante entfällt, wenn dort kein Platz ist)
    """

    r0 = max(opening_run[0] - lap_length, 0.0)
    r1 = min(opening_run[1] + lap_length, run_len)

    if r1 - r0 <= 0:
        return []

    runs: list[EdgeBarRun] = []

    # Zone vor der Öffnung (kleinere dist-Werte)
    zone_to = min(opening_dist[0], dist_len)
    zone_from = max(zone_to - zone_width, 0.0)
    if 0.0 <= zone_from < zone_to:
        runs.append(EdgeBarRun(r0, r1, zone_from, zone_to))

    # Zone hinter der Öffnung (größere dist-Werte)
    zone_from = max(opening_dist[1], 0.0)
    zone_to = min(zone_from + zone_width, dist_len)
    if zone_from < zone_to <= dist_len:
        runs.append(EdgeBarRun(r0, r1, zone_from, zone_to))

    return runs
