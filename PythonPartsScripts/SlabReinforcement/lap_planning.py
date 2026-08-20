"""Stossplanung nach Bürosystematik.

Abgenommen am 14-Formen-Studienblatt (Stoss-Studie, bestätigt): Ziel ist
die **minimale Anzahl Verlegungen** — Stösse selbst kosten nichts.

Regeln:
    1. Überlange Stäbe werden gleichmässig geteilt (halbiert, gedrittelt,
       ...), kein festes Stossraster.
    2. Passeisen-Regel: jedes Eisen ab der Passeisen-Grenze (Palettenwert,
       Default 3 m) enthält mindestens einen Stoss — damit nie ein Eisen
       exakt auf Mass geschnitten werden muss; die Teilstücke lassen sich
       stattdessen schieben.
    3. Fluchten (Aussparungskanten und einspringende Ecken quer zur
       Stabrichtung) sind bevorzugte Stossachsen und laufen durch die
       ganze Platte — aber nur, wenn sie sich lohnen: die Kante muss
       einen Mindestanteil der Plattenbreite betreffen (min_share,
       Default 25 %). Kleine Aussparungen in grossen Platten erzeugen
       sonst Zusatzstösse über das ganze Feld, ohne Verlegungen zu
       sparen (belegt am realen Projektbeispiel 20.5 x 15 m). Eine
       Eck-Flucht entfällt ausserdem, wenn die kurze Seite der Ecke
       ohnehin mittig gestossen wird (Länge >= Passeisen-Grenze).
    4. Abtreppung: je Bereich EINE gerade Stosslinie, geerbt vom
       Pflichtstoss der vollen Bahnen; sie rutscht parallel nach innen,
       bis jedes Abtreppungsstück die Mindestlänge erreicht. Die
       Stufenbildung selbst bleibt unverändert wie bisher: Stäbe bilden
       eine Stufe, solange keiner mehr als die zulässige Abweichung von
       seiner Länge verliert; vermessen wird am längsten Stab der Stufe,
       das Längenraster rundet nach aussen.
    5. Keine Verlegung mit nur einem Stab: Einzelgänger werden mit dem
       Nachbarn zusammengefasst.

Wie die übrigen Geometriemodule bewusst OHNE Allplan-Abhängigkeit.
"""

from __future__ import annotations

import math
from typing import NamedTuple

Point = tuple[float, float]
Loop = list[Point]
Interval = tuple[float, float]


class PlacementGroup(NamedTuple):
    """Eine Verlegung: identisches Stabstück über mehrere Scan-Positionen."""

    positions: list[float]
    piece: Interval


def loop_bbox(loop: Loop) -> tuple[float, float, float, float]:
    xs = [p[0] for p in loop]
    ys = [p[1] for p in loop]
    return min(xs), min(ys), max(xs), max(ys)


def active_fluchten(contour: Loop,
                    openings: list[Loop],
                    run_axis: int,
                    bars,
                    pass_threshold: float,
                    min_share: float = 0.25,
                    tol: float = 1.0) -> list[float]:
    """Stossachsen-Kandidaten quer zur Stabrichtung.

    Eine Flucht ist nur aktiv, wenn sich das Ausrichten lohnt (Regel 3):
    die Kante muss mindestens min_share der Scan-Ausdehnung der Platte
    betreffen — so viele Bahnen enden dort, dass eine gemeinsame
    Stossachse Verlegungen spart. Kleine Aussparungen in grossen Platten
    fallen durch und ihre Umgebung stösst segmentweise mittig.

    Eine einspringende Konturkante (Ecke) ist zusätzlich nur aktiv, wenn
    die an ihr endenden kurzen Bahnstücke unter der Passeisen-Grenze
    liegen — sonst bekommen diese ohnehin einen mittigen Stoss und die
    Flucht spart keine Verlegung.
    """

    if not bars:
        return []

    scan_extent = max(b.position for b in bars) - min(b.position for b in bars)

    if scan_extent <= 0:
        return []

    fluchten: list[float] = []

    for opening in openings:
        bb = loop_bbox(opening)
        span = bb[(1 - run_axis) + 2] - bb[1 - run_axis]

        if span / scan_extent >= min_share:
            fluchten += [bb[run_axis], bb[run_axis + 2]]

    bb = loop_bbox(contour)
    lo, hi = bb[run_axis], bb[run_axis + 2]

    for i, p1 in enumerate(contour):
        p2 = contour[(i + 1) % len(contour)]

        if abs(p1[run_axis] - p2[run_axis]) > tol:
            continue

        coord = p1[run_axis]

        if not (lo + tol < coord < hi - tol):
            continue

        span = sorted((p1[1 - run_axis], p2[1 - run_axis]))

        if (span[1] - span[0]) / scan_extent < min_share:
            continue                     # zu kleine Kante — lohnt nicht

        # Kurze Seite: Segmente, die im Kantenbereich an dieser Kante enden
        short_lengths = []

        for bar in bars:
            if not (span[0] - tol <= bar.position <= span[1] + tol):
                continue

            for seg in bar.segments:
                boundary_gap = min(abs(seg[0] - coord), abs(seg[1] - coord))

                # Deckung/Anschluss verschieben das Stabende leicht von der
                # Kante weg — grosszügige Toleranz
                if boundary_gap <= 100.0:
                    short_lengths.append(seg[1] - seg[0])

        if short_lengths and max(short_lengths) >= pass_threshold:
            continue                     # Flucht entfällt (Regel 3)

        fluchten.append(coord)

    return sorted(set(fluchten))


def _equal_cuts(seg: Interval, count: int) -> list[float]:
    """count Stossachsen, die das Segment in count+1 gleiche Teile teilen."""

    length = seg[1] - seg[0]
    return [seg[0] + length * (k + 1) / (count + 1) for k in range(count)]


def base_cuts(seg: Interval,
              fluchten: list[float],
              lmax: float,
              lap: float,
              pass_threshold: float,
              min_bar: float) -> list[float]:
    """Stossachsen eines (gedachten) Rechtecksegments.

    Erst alle Fluchten, die das Segment mit genug Randabstand kreuzen;
    dann jedes noch überlange Teilstück gleichmässig nachteilen; dann die
    Passeisen-Regel, falls immer noch kein Stoss vorhanden ist.
    """

    margin = max(lap, min_bar)
    length = seg[1] - seg[0]

    cuts = [f for f in fluchten if seg[0] + margin < f < seg[1] - margin]

    bounds = [seg[0]] + sorted(cuts) + [seg[1]]

    for lo, hi in zip(bounds, bounds[1:]):
        piece_len = (hi - lo) + lap          # Stück inkl. Übergreifungsanteil
        if piece_len > lmax:
            extra = math.ceil(piece_len / lmax) - 1
            cuts += _equal_cuts((lo, hi), extra)

    if not cuts and length >= pass_threshold:
        cuts = [(seg[0] + seg[1]) / 2.0]

    return sorted(cuts)


def _pieces_from_cuts(seg: Interval, cuts: list[float], lap: float) -> list[Interval]:
    pieces: list[Interval] = []
    lo = seg[0]

    for c in cuts:
        pieces.append((lo, c + lap / 2.0))
        lo = c - lap / 2.0

    pieces.append((lo, seg[1]))

    return pieces


def _split_by_spacing(positions: list[float], tol: float = 1.0) -> list[list[float]]:
    """Teilt Scan-Positionen in Läufe mit konstantem Abstand (eine lineare
    Verlegung braucht einen konstanten Stababstand)."""

    runs: list[list[float]] = []

    for pos in positions:
        if runs:
            run = runs[-1]
            gap = run[1] - run[0] if len(run) >= 2 else None

            if gap is None or abs((pos - run[-1]) - gap) <= tol:
                run.append(pos)
                continue

        runs.append([pos])

    return runs


def _round_up(value: float, raster: float) -> float:
    if raster <= 0:
        return value
    return math.ceil(value / raster - 1e-9) * raster


class _SlotRegion(NamedTuple):
    positions: list[float]
    segs: list[Interval]


def scan_breaks(contour: Loop,
                openings: list[Loop],
                run_axis: int,
                tol: float = 1.0) -> list[float]:
    """Scan-Koordinaten aller Kanten, die parallel zu den Stäben laufen —
    dort ändert sich die Bahnstruktur sprunghaft (L-Ecke, Aussparungsrand)
    und die Verlegung muss getrennt werden. Ohne diese Trennung würde der
    Sprung an einer L-Ecke fälschlich als Abtreppung gelesen."""

    scan_axis = 1 - run_axis
    breaks: list[float] = []

    for loop in [contour] + list(openings):
        for i, p1 in enumerate(loop):
            p2 = loop[(i + 1) % len(loop)]

            if abs(p1[scan_axis] - p2[scan_axis]) <= tol and \
                    abs(p1[run_axis] - p2[run_axis]) > tol:
                breaks.append(p1[scan_axis])

    return sorted(set(breaks))


def _slot_regions(bars, breaks: list[float]) -> list[_SlotRegion]:
    """Zerlegt die Bahnen in Bereiche gleicher Struktur: Trennung bei
    geänderter Segmentanzahl und an jeder stabparallelen Kante."""

    regions: list[_SlotRegion] = []
    current: list = []

    for bar in bars:
        if current:
            crosses = any(current[-1].position < b <= bar.position
                          for b in breaks)

            if crosses or len(bar.segments) != len(current[-1].segments):
                regions += _explode(current)
                current = []

        current.append(bar)

    regions += _explode(current)

    return regions


def _explode(group) -> list[_SlotRegion]:
    if not group:
        return []

    count = len(group[0].segments)

    return [_SlotRegion([b.position for b in group],
                        [b.segments[i] for b in group])
            for i in range(count)]


def plan_layer(bars,
               contour: Loop,
               openings: list[Loop],
               run_axis: int,
               *,
               lmax: float,
               lap: float,
               pass_threshold: float,
               step_deviation: float,
               raster: float,
               min_piece: float,
               min_bar: float,
               flucht_min_share: float = 0.25,
               tol: float = 1.0) -> list[PlacementGroup]:
    """Vollständige Stoss- und Verlegeplanung einer Lage."""

    if not bars or lap <= 0:
        return []

    fluchten = active_fluchten(contour, openings, run_axis, bars,
                               pass_threshold, flucht_min_share)
    breaks = scan_breaks(contour, openings, run_axis)

    groups: list[PlacementGroup] = []

    for region in _slot_regions(bars, breaks):
        starts = [s[0] for s in region.segs]
        ends = [s[1] for s in region.segs]

        start_stepped = max(starts) - min(starts) > tol
        end_stepped = max(ends) - min(ends) > tol

        envelope = (min(starts), max(ends))
        cuts = base_cuts(envelope, fluchten, lmax, lap, pass_threshold, min_bar)

        line_start = line_end = None

        if end_stepped:
            line_end, cuts = _step_line(cuts, envelope, min(ends), min_piece,
                                        lap, pass_threshold, side='end')
        if start_stepped:
            line_start, cuts = _step_line(cuts, envelope, max(starts), min_piece,
                                          lap, pass_threshold, side='start')

        # ------- Mittelteil (Rechteck zwischen den Stufenlinien) -------
        core = ((line_start - lap / 2.0) if line_start is not None else envelope[0],
                (line_end + lap / 2.0) if line_end is not None else envelope[1])

        core_cuts = [c for c in cuts if core[0] + lap < c < core[1] - lap]

        for piece in _pieces_from_cuts(core, core_cuts, lap):
            if piece[1] - piece[0] < min_bar:
                continue
            for positions in _split_by_spacing(region.positions):
                groups.append(PlacementGroup(positions, piece))

        # ------- Stufenstücke -------
        if end_stepped:
            groups += _step_groups(region, line_end, lap, step_deviation,
                                   raster, side='end')
        if start_stepped:
            groups += _step_groups(region, line_start, lap, step_deviation,
                                   raster, side='start')

    return _merge_singletons(groups)


def _step_line(cuts: list[float],
               envelope: Interval,
               boundary: float,
               min_piece: float,
               lap: float,
               pass_threshold: float,
               side: str) -> tuple[float, list[float]]:
    """Stosslinie einer Abtreppung (Regel 4).

    Geerbt wird die dem Stufenbereich nächste Pflicht-Stossachse; gibt es
    keine, liegt die Linie mittig zwischen dem kürzesten Stufenende
    (boundary) und dem gegenüberliegenden Segmentende. Danach rutscht sie
    parallel nach innen, bis das kürzeste Stufenstück die Mindestlänge
    min_piece erreicht.
    """

    if side == 'end':
        inherited = max((c for c in cuts if c < boundary - lap), default=None)
        nominal = inherited if inherited is not None \
            else (envelope[0] + boundary) / 2.0
        line = min(nominal, boundary - min_piece)
        remaining = [c for c in cuts if c < line - lap]
    else:
        inherited = min((c for c in cuts if c > boundary + lap), default=None)
        nominal = inherited if inherited is not None \
            else (boundary + envelope[1]) / 2.0
        line = max(nominal, boundary + min_piece)
        remaining = [c for c in cuts if c > line + lap]

    return line, remaining


def _step_groups(region: _SlotRegion,
                 line: float,
                 lap: float,
                 step_deviation: float,
                 raster: float,
                 side: str) -> list[PlacementGroup]:
    """Stufenstücke — Stufenbildung unverändert wie bisher.

    Aufeinanderfolgende Bahnen bilden eine Stufe, solange ihre Enden um
    höchstens step_deviation auseinanderliegen; das gemeinsame Stück wird
    am **längsten** Ende vermessen und das Längenraster rundet nach
    aussen. Neu ist nur der Anfang des Stücks: er liegt auf der
    Stosslinie (minus halbe Übergreifung), nicht mehr an einer
    Zonengrenze.
    """

    entries = list(zip(region.positions, region.segs))

    groups: list[list] = []

    for pos, seg in entries:
        boundary = seg[1] if side == 'end' else seg[0]

        if groups:
            bounds = [b for _, b in groups[-1]]
            if max(bounds + [boundary]) - min(bounds + [boundary]) <= step_deviation:
                groups[-1].append((pos, boundary))
                continue

        groups.append([(pos, boundary)])

    # Keine Einzelgänger (Regel 5): ein einzelner Stab wird mit dem
    # Nachbarn zusammengelegt — aufeinanderfolgende Einzelne bilden Paare,
    # ein einzelner Rest hängt sich an die vorige Stufe an
    merged: list[list] = []
    for group in groups:
        if merged and len(group) == 1 and len(merged[-1]) == 1:
            merged[-1] += group
        else:
            merged.append(group)

    if len(merged) >= 2 and len(merged[-1]) == 1:
        merged[-2] += merged.pop()

    result: list[PlacementGroup] = []

    for group in merged:
        positions = [pos for pos, _ in group]
        bounds = [b for _, b in group]

        uniform = max(bounds) - min(bounds) <= 1.0

        if side == 'end':
            # Vermessung am längsten Ende; das Raster rundet nur bei einer
            # echten Stufe nach aussen — ein gleichmässiger Block endet
            # exakt an seiner Betonkante
            outer = max(bounds) if uniform else _round_up(max(bounds), raster)
            piece = (line - lap / 2.0, outer)
        else:
            outer = min(bounds) if uniform else \
                (math.floor(min(bounds) / raster + 1e-9) * raster
                 if raster > 0 else min(bounds))
            piece = (outer, line + lap / 2.0)

        for run in _split_by_spacing(positions):
            result.append(PlacementGroup(run, piece))

    return result


def _merge_singletons(groups: list[PlacementGroup]) -> list[PlacementGroup]:
    """Regel 5 auf Verlegungsebene: eine Ein-Stab-Verlegung wird der
    benachbarten Verlegung mit überlappendem Stück zugeschlagen, sofern
    deren Stück das des Einzelstabs abdeckt."""

    result = list(groups)
    changed = True

    while changed:
        changed = False

        for i, group in enumerate(result):
            if len(group.positions) != 1:
                continue

            pos = group.positions[0]

            for j, other in enumerate(result):
                if i == j or not other.positions:
                    continue

                gap = min(abs(pos - other.positions[0]),
                          abs(pos - other.positions[-1]))
                spacing = (other.positions[1] - other.positions[0]) \
                    if len(other.positions) > 1 else gap

                covers = other.piece[0] <= group.piece[0] + 1e-6 and \
                    other.piece[1] >= group.piece[1] - 1e-6

                # Auch der Randstab am Ende eines Laufs (kleinerer Abstand
                # als das Raster) wird übernommen — wie bisher rückt er
                # dabei auf das Verlegeraster
                if covers and gap <= spacing + 1.0:
                    merged_positions = sorted(other.positions + [pos])
                    result[j] = PlacementGroup(merged_positions, other.piece)
                    del result[i]
                    changed = True
                    break

            if changed:
                break

    return result
