"""SlabReinforcement — PythonPart-Paket für Allplan 2026.

Offiziell dokumentierte Paketstruktur für PythonParts mit mehreren Modulen
(Doku: Key components → File locations, Abschnitt "Tip"): Der Ordner
enthält ein `__init__.py`, das die vom Framework erwarteten Funktionen
bereitstellt. Die `.pyp` verweist dann auf `SlabReinforcement.py` — eine
Datei, die es gar nicht gibt; Python behandelt den gleichnamigen Ordner
dank dieses `__init__.py` als Modul.

Damit funktionieren die relativen Importe der Nachbarmodule zuverlässig.
"""

from .slab_reinforcement import check_allplan_version, create_script_object

__all__ = ['check_allplan_version', 'create_script_object']
