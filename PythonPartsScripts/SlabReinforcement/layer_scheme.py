"""Auswertung der Lagerichtung aus der Palette.

Eigenes Modul, damit die Zuordnung Palettenwert -> Lagenreihenfolge ohne
Allplan-Umgebung getestet werden kann; sie war mehrfach die Ursache
falsch herum liegender Lagen.
"""

from __future__ import annotations

import re

# Variante 1: 1./4. Lage senkrecht -> die äusseren Lagen laufen in Y
LAYER_SCHEME_OUTER_Y = 1
# Variante 2: 1./4. Lage waagrecht -> die äusseren Lagen laufen in X
LAYER_SCHEME_OUTER_X = 2


def layer_scheme_value(raw) -> int:
    """Palettenwert der Lagerichtung robust auf 1 oder 2 abbilden.

    Die Palette liefert einen StringComboBox-Wert ("Variante 1" bzw.
    "Variante 2"); ältere gespeicherte Parametersätze können noch eine
    Zahl enthalten. Beides wird auf die enthaltene Ziffer reduziert, ein
    unbekannter Wert fällt auf Variante 2 zurück, statt eine Exception zu
    werfen.
    """

    # erste Ziffernfolge: trägt sowohl "Variante 1" als auch einen alten
    # Zahlwert wie 1.0, ohne dass die Nachkommastelle mitgelesen wird
    match = re.search(r'\d+', str(raw))

    if match is None:
        return LAYER_SCHEME_OUTER_X

    value = int(match.group())

    if value not in (LAYER_SCHEME_OUTER_Y, LAYER_SCHEME_OUTER_X):
        return LAYER_SCHEME_OUTER_X

    return value


def outer_direction(raw) -> str:
    """Richtung, in der die 1. und die 4. Lage verlaufen ("X" oder "Y")."""

    return 'X' if layer_scheme_value(raw) == LAYER_SCHEME_OUTER_X else 'Y'
