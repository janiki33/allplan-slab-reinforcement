# SlabReinforcement — PythonPart für Allplan 2026

Automatische Flächenbewehrung für Flachdecken: vier Bewehrungslagen
(oben/unten, jeweils X- und Y-Richtung), optional mit rechteckiger Öffnung
(Stäbe werden gekappt, die Öffnung erhält Randverstärkungsstäbe).
Eigenständige Neuentwicklung auf Basis der offiziellen Allplan Python API —
keine Kopie kommerzieller Plugins.

## Status

| Version | Funktionsumfang | Status |
|---|---|---|
| v0.1 | Rechteckplatte, 4 Lagen (Ø, Abstand, Deckung, Stahlgüte je Lage), Palette, Live-Vorschau, PythonPart-Erzeugung | umgesetzt |
| v0.2 | Rechteckige Öffnung: Kappen der Hauptstäbe, umlaufende Randverstärkung mit konfigurierbarer Übergreifungslänge | umgesetzt |
| v0.3 | Polygonale Platten (Interactor-Eingabe / Slab-Selektion), mehrere Öffnungen | Roadmap, s. u. |
| v0.4 | Auflagererkennung (Wände/Unterzüge) mit Anschlussbewehrung | Roadmap |

**Hinweis:** Der Code wurde gegen die offizielle 2026-API-Doku und die
Original-Beispiele entwickelt und von einem unabhängigen Review gegen die
Spezifikation geprüft (u. a. Rotationswinkel der Shapes und Hook-Defaults),
aber noch nicht in einer laufenden Allplan-Installation getestet.

## Dateistruktur

```
Library/SlabReinforcement/SlabReinforcement.pyp      Palettendefinition (UI)
PythonPartsScripts/SlabReinforcement/
    SlabReinforcement.py                             Einstieg + Orchestrierung der Placements
    opening_clipping.py                              Reine Band-/Kapp-Logik (ohne Allplan-Import, testbar)
tests/test_opening_clipping.py                       Unit-Tests der Kapp-Logik (laufen ohne Allplan)
```

## Installation

1. `Library/SlabReinforcement/` nach `...\std\Library\SlabReinforcement\` kopieren
   (alternativ in den `usr`-Pfad).
2. `PythonPartsScripts/SlabReinforcement/` nach `...\std\PythonPartsScripts\SlabReinforcement\`
   kopieren (der `<Script><Name>`-Pfad in der `.pyp` ist relativ zum
   `PythonPartsScripts`-Ordner).
3. In Allplan: Bibliothek → Standard → SlabReinforcement starten.

Tests ohne Allplan: `python3 -m unittest discover -s tests`

## Bedienung / Parameter

- **Geometrie:** Länge/Breite/Dicke der (vorerst rechteckigen) Platte.
- **Bewehrung unten / oben:** je Richtung Durchmesser, Stababstand,
  Betondeckung und Stahlgüte. Konvention: X-Lage liegt jeweils außen
  (unten zuerst verlegt, oben zuoberst), Y-Lage innen.
- **Öffnung:** eine rechteckige Öffnung über Lage und Abmessung; Zulagen
  (Anzahl, Ø, Abstand) und Übergreifungslänge sind frei konfigurierbar.
- **Allgemein:** Betongüte, seitliche Deckung, Mindeststablänge (kürzere
  Reststücke neben Öffnungen entfallen ersatzlos), Format-Eigenschaften,
  „Als PythonPart erzeugen".

Bei jeder Parameteränderung ruft Allplan `create_element` neu auf —
das ist die übliche Live-Vorschau von Standard-PythonParts.

### Höhenlagen-Konvention

Die Höhenlage jedes Stabes wird über die „bottom"-Deckung der
`ConcreteCoverProperties` gesteuert (lichter Abstand Stabunterkante zur
Placement-Ebene z = 0 = Plattenunterkante), analog zur Längsbewehrung im
offiziellen `BarPlacement`-Beispiel:

- unten X: `cover_unten`
- unten Y: `cover_unten + Ø(unten X)`
- oben X: `Dicke − cover_oben − Ø(oben X)`
- oben Y: `Dicke − cover_oben − Ø(oben X) − Ø(oben Y)`

Randverstärkungs-Zulagen liegen als eigene Ebenen innerhalb der Hauptlagen
(unten oberhalb der inneren unteren Lage, oben unterhalb der inneren oberen
Lage; X- und Y-Zulagen gestapelt), damit sich keine Stäbe durchdringen.
Lagen, für die die Plattendicke nicht ausreicht, entfallen mit einer Meldung
im Trace-Fenster statt falsch erzeugt zu werden.

### Normen / Bemessung

Bewusst **keine** fest codierten Eurocode-Regeln: Die Übergreifungslänge der
Randverstärkung ist ein freier Palettenparameter (Default 800 mm — reiner
Platzhalter, kein Normwert). Stababstände, Deckungen und Zulagenanzahl sind
ebenfalls frei. Einzige normabhängige Automatik: der Biegerollendurchmesser
wird über `AllplanReinf.BendingRollerService.GetBendingRollerFactor(...)`
aus den Allplan-Projekteinstellungen ermittelt (so auch im offiziellen
Beispiel). Die Bemessung bleibt Aufgabe der Tragwerksplanung.

## Recherche-Zusammenfassung (Quellen)

Kern-APIs, alle gegen die Original-Beispiele (Repo
[`NemetschekAllplan/PythonPartsExamples`](https://github.com/NemetschekAllplan/PythonPartsExamples),
Branch `2026`) und die 2026-Doku verifiziert:

- **Shapes:** `ReinforcementShapeProperties.rebar(...)`,
  `ConcreteCoverProperties.all/left_right_bottom(...)`,
  `GeneralShapeBuilder.create_longitudinal_shape_with_hooks(...)` —
  [GeneralReinfShapeBuilder](https://pythonparts.allplan.com/2026/api_reference/StdReinfShapeBuilder/GeneralReinfShapeBuilder/),
  Vorlage `ReinforcementExamples/BarPlacement/BarPlacement.py`.
- **Placements:** `LinearBarBuilder.create_linear_bar_placement_from_to_by_dist/by_count(...)` —
  [LinearBarPlacementBuilder](https://pythonparts.allplan.com/2026/api_reference/StdReinfShapeBuilder/LinearBarPlacementBuilder/),
  [Placement-Manual 2026](https://pythonparts.allplan.com/2026/manual/features/reinforcement/placement/).
  Für Bereiche mit wechselndem Abstand steht dort zusätzlich
  `calculate_length_of_regions(...)` bereit (hier noch nicht genutzt).
- **PythonPart-Zusammenbau:** `PythonPartUtil.add_pythonpart_view_2d3d(...)` für
  die Geometrie, `add_reinforcement_elements(...)` für die Placements —
  Bewehrung gehört **nicht** in die 2D/3D-View (Muster aus `BarPlacement.py`).
- **Palette:** `.pyp`-Schema 2026 mit `ReinfBarDiameter`, `ReinfSteelGrade`,
  `ReinfConcreteGrade`, `ReinfConcreteCover`, `Expander`, `Visible`-Bedingungen —
  Vorlagen `BarPlacement.pyp`, `PaletteExamples/AllControls.pyp` (Branch 2026).
- **Polygonale Platzierung (für v0.3):** `AllplanReinf.BarPlacement(pos, count,
  start_shape, end_shape)` interpoliert linear zwischen zwei Shapes
  ([BarPlacement-Stub 2026](https://pythonparts.allplan.com/2026/api_reference/InterfaceStubs/NemAll_Python_Reinforcement/BarPlacement/),
  Beispiel `PolygonalPlacement.py`); für unregelmäßige Konturen zeigt
  `ReinforcementExamples/AreaPlacementExpand.py` das Muster
  „Stablinie gegen jede Polygonkante mit `AllplanGeo.IntersectionCalculus` schneiden".
- **Geometrie-Eingabe (für v0.3):** `ScriptObjectInteractors.PolygonInteractor`
  (Polygon zeichnen) bzw. `SingleElementSelectInteractor` +
  `SlabElement.GetGeometryObject()` (bestehende Platte wählen) — Beispiele
  `ArchitectureExamples/Objects/SlabOpening.py`, `ModifyObjects/ModifySlab.py`.
  Erfordert die Umstellung des Skripts auf die `ScriptObject`-Struktur
  (`create_script_object` / `BaseScriptObject`).

### Versionsunterschiede 2024/2025/2026

- Die 2024-Doku ist offline (Redirect auf `/2026/`); ein direkter
  2024-Vergleich war daher nicht möglich.
- 2025 ↔ 2026: Signaturen der hier genutzten Builder
  (`LinearBarPlacementBuilder`, `ReinforcementShapeProperties`) sind identisch;
  die [Release Notes 2026](https://pythonparts.allplan.com/2026/release_notes/)
  nennen keine Reinforcement-Breaking-Changes (Neuerungen: Python 3.13,
  Parent-Child-Relationships). Die Reinforcement-Beispiele wurden mit 2025
  überarbeitet ([Release Notes 2025](https://pythonparts.allplan.com/2025/release_notes/)).
- Beispiel-Repo-Branches heißen `main`, `2025`, `2026` (keine `Release_*`-Branches).

### Nicht verlässlich belegbar (bewusst nicht verwendet)

- Ein direkter **Polygon-Offset** (geschlossenes `Polygon2D/3D` nach innen
  versetzen) für die Betondeckung ist in der API nicht belegt — für v0.3 ist
  daher kantenweises Versetzen + Neuverschneiden geplant.
- Der ältere `.pyp`-Mechanismus `BuildingElementPolygon`/`<UseGeometry>` taucht
  im 2026-Beispiel-Repo nicht mehr auf — stattdessen `PolygonInteractor`.
- Die konkreten Enum-Werte von `AllplanGeo.Comparison.DeterminePosition` für
  Punkt-in-Polygon sind nicht dokumentiert belegt (für v0.3 zu verifizieren).
