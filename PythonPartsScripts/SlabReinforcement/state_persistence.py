"""Sichern und Laden der eingegebenen Geometrie eines abgesetzten PythonParts.

Allplan stellt beim Bearbeiten eines abgesetzten PythonParts nur die
Palettenwerte wieder her. Die per Interactor eingegebene Geometrie
(Absetzpunkt, Kontur, Aussparungen) lebt allein im ScriptObject und waere
nach dem Verlassen verloren — das Element liesse sich dann nicht mehr
bearbeiten. Diese beiden Funktionen legen sie als Zeichenkette in einem
versteckten Palettenparameter ab.

Bewusst frei von Allplan-Importen, damit die Kodierung ohne laufendes
Allplan testbar bleibt (wie die uebrigen Geometriemodule).
"""

from __future__ import annotations

import json

# Erhoeht sich, wenn sich das Format aendert. Ein Stand mit abweichender
# Fassung wird verworfen statt falsch interpretiert.
STATE_VERSION = 1

# Koordinaten werden auf 0.1 mm gerundet abgelegt: feiner als jede
# Bewehrungstoleranz und deutlich kuerzer als der volle float-Text.
_PRECISION = 1


def _round_polygon(points) -> list:
    return [[round(float(x), _PRECISION), round(float(y), _PRECISION)]
            for x, y in points]


def _read_polygon(points) -> list:
    return [(float(x), float(y)) for x, y in points]


def encode_state(placement_pnt: tuple,
                 contour,
                 detected_openings,
                 drawn_openings,
                 z_offset: float,
                 thickness_override,
                 walls=None) -> str:
    """Geometriestand in eine Zeichenkette fuer die Palette.

    `placement_pnt` als (x, y, z); `contour` als Punktliste oder None;
    die Aussparungen als Listen von Punktlisten.
    """

    state = {
        'v': STATE_VERSION,
        'pnt': [round(float(v), _PRECISION) for v in placement_pnt],
        'contour': _round_polygon(contour) if contour else None,
        'detected': [_round_polygon(op) for op in (detected_openings or [])],
        'drawn': [_round_polygon(op) for op in (drawn_openings or [])],
        'z_offset': round(float(z_offset), _PRECISION),
        'thickness': None if thickness_override is None else float(thickness_override),
        'walls': [_round_polygon(wall) for wall in (walls or [])],
    }

    return json.dumps(state, separators=(',', ':'))


def decode_state(raw: str) -> dict | None:
    """Gegenstueck zu encode_state.

    Liefert ein dict mit den Schluesseln placement_pnt, contour,
    detected_openings, drawn_openings, z_offset und thickness_override —
    oder None, wenn nichts gespeichert ist bzw. der Stand unbrauchbar ist.
    Der Aufrufer entscheidet, was er meldet.
    """

    if not raw:
        return None

    try:
        state = json.loads(raw)
    except (TypeError, ValueError):
        return None

    if not isinstance(state, dict) or state.get('v') != STATE_VERSION:
        return None

    try:
        pnt = state['pnt']
        thickness = state.get('thickness')

        return {
            'placement_pnt': (float(pnt[0]), float(pnt[1]), float(pnt[2])),
            'contour': _read_polygon(state['contour']) if state.get('contour') else None,
            'detected_openings': [_read_polygon(op) for op in state.get('detected', [])],
            'drawn_openings': [_read_polygon(op) for op in state.get('drawn', [])],
            'z_offset': float(state.get('z_offset', 0.0)),
            'thickness_override': None if thickness is None else float(thickness),
            # Fehlt in Ständen von vor dem Wandanschluss — dann leer
            'walls': [_read_polygon(wall) for wall in state.get('walls', [])],
        }
    except (KeyError, TypeError, ValueError, IndexError):
        return None
