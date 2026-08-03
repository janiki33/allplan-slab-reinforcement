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
| v0.2.1 | Randausbildung je Kante (U-Randbügel / Anschlusseisen / separate Anschlusseisen / keine), Stoßfaktor, „Alle Lagen gleich", wählbare äußere Lagenrichtung, Allplan-Layer je Lage, Handles | umgesetzt |
| v0.3 | ScriptObject-Struktur mit drei Eingabemodi (Rechteck-Drag / Polygon zeichnen / Element wählen), Scanline-Verlegung für polygonale Konturen, mehrere Öffnungen, Randverdichtung via `calculate_length_of_regions` | umgesetzt |
| v0.4 | Auflagererkennung (Wände/Unterzüge) mit Anschlussbewehrung, Randbügel/Anschlusseisen an Polygonkanten | Roadmap |

**Hinweis:** Der Code wurde gegen die offizielle 2026-API-Doku und die
Original-Beispiele entwickelt und je Ausbaustufe von einem unabhängigen
Review geprüft, aber noch nicht in einer laufenden Allplan-Installation
getestet. Beim ersten Live-Test gezielt prüfen:

1. Breite-Handle (6. Argument von `HandleCreator.point_distance` ist ohne
   laufendes Allplan nicht eindeutig belegbar).
2. Scanline-Einzelstäbe an schrägen Rändern: erwartet wird mittige
   Platzierung im Verlegefenster (`create_linear_bar_placement_from_to_by_count`
   mit Stabanzahl 1) — sonst um den halben Stababstand verschoben.
3. Elementmodus mit Einzelfundament: liefert `GetGeometryObject()` das
   Shape-Polygon lokal statt global, muss der Absetzpunkt addiert werden.

## Dateistruktur

```
Library/SlabReinforcement/SlabReinforcement.pyp      Palettendefinition (UI)
PythonPartsScripts/SlabReinforcement/
    SlabReinforcement.py                             ScriptObject (Eingabemodi) + Placement-Engine
    opening_clipping.py                              Reine Band-/Kapp-Logik Rechteckmodus (ohne Allplan, testbar)
    contour_placement.py                             Reine Scanline-Logik für polygonale Konturen (ohne Allplan, testbar)
tests/                                               Unit-Tests beider Geometrie-Module (laufen ohne Allplan)
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

- **Eingabemodus** (Seite „Geometrie"):
  - *Rechteck (Drag):* Platte mit der Maus absetzen (Vorschau folgt dem
    Fadenkreuz), danach über Handles Länge/Breite/Dicke ziehen. Voller
    Funktionsumfang inkl. Palettenöffnung, Randbügeln und Anschlusseisen.
  - *Polygon zeichnen:* beliebige Kontur zeichnen; jedes weitere
    gezeichnete Polygon wird als Öffnung interpretiert (größte Fläche =
    Kontur). Verlegung per Scanline: Stablinien werden mit der Kontur und
    allen Öffnungen verschnitten, gleiche aufeinanderfolgende Stäbe zu
    linearen Placements zusammengefasst, an schrägen Rändern entstehen
    Einzelstab-Placements.
  - *Element wählen:* Decke (`Slab`), Boden-/Plattenfundament
    (`SlabFoundationTier`), Einzelfundament (`IndividualFoundation`) oder
    Streifenfundament (`StripFoundation`) wählen. Kontur kommt aus
    `GetGeometryObject()` (beim Streifenfundament aus Achse × Breite);
    Dicke und Unterkanten-Höhenlage werden, wo lesbar
    (Tier-Properties/`Height`/`PlaneReferences`), aus dem Element
    übernommen, sonst gilt der Palettenwert mit Meldung im Trace-Fenster.
- **Geometrie:** Länge/Breite/Dicke (Rechteckmodus), Handles am
  Absetzpunkt. Unter „Verlegung" ist wählbar, ob die X- oder die Y-Lagen
  außen liegen; dort sitzt auch die **Randverdichtung** (Zonenlänge +
  engerer Stababstand an beiden Verteilrändern): im Rechteckmodus über
  `LinearBarBuilder.calculate_length_of_regions`, im Scanline-Modus über
  eine äquivalente Positionsberechnung. Verdichtungszonen wirken im
  Rechteckmodus nur auf Bänder über die volle Plattenbreite.
- **Bewehrung unten / oben:** je Richtung Durchmesser, Stababstand,
  Betondeckung und Stahlgüte. Mit „Alle Lagen gleicher Durchmesser" gilt
  eine gemeinsame ø/a-Eingabe für alle vier Lagen.
- **Seiten** (Konzept aus dem Deckenplatte-PythonPart des Anwenders
  übernommen): je Plattenkante wählbar —
  „Randbügel" (offene U-Steckbügel über beide Lagen der senkrecht
  zulaufenden Richtung; Außenhöhe auf ganze cm abgerundet, Schenkellänge =
  Stoßlänge − ø/2), „Anschlusseisen" (Lagenstäbe stehen um die Stoßlänge
  über den Rand über), „Separate Anschlusseisen" (eigene Stäbe der Länge
  2 × Stoßlänge, mittig auf der Kante) oder „Keine". Die Stoßlänge ist als
  Stoßfaktor (Vielfaches von ø) konfigurierbar — bewusst kein Normwert.
  Randbügel und separate Anschlusseisen sparen den Bereich einer Öffnung
  aus, wenn diese den jeweiligen Randstreifen schneidet. Bekannte
  Einschränkungen: Randbügel/Anschlusseisen gibt es nur im Rechteckmodus
  (an freien Polygonkanten: Roadmap v0.4); bei aktiver Öffnung starten die
  Hauptlagen-Bänder ihr Raster je Band neu, sodass Randbügel/Anschluss-
  eisen dort nicht zwingend mit den Lagenstäben fluchten; die Format-
  Eigenschaften (Stift/Farbe) wirken auf den Plattenkörper, die Bewehrung
  übernimmt die globalen Eigenschaften (bzw. den je Lage gewählten Layer).
  Im Polygon-/Elementmodus wird als Ansichtsgeometrie die Kontur (kein
  3D-Körper) gezeichnet; beim Elementmodus existiert der Körper ohnehin.
  Die seitliche Deckung wird im Scanline-Pfad achsparallel angesetzt — an
  stark schrägen Rändern ist die wahre (senkrechte) Deckung etwas kleiner.
- **Öffnung:** eine rechteckige Öffnung über Lage und Abmessung; Zulagen
  (Anzahl, Ø, Abstand) und Übergreifungslänge sind frei konfigurierbar.
- **Allgemein:** Betongüte, seitliche Deckung, Mindeststablänge (kürzere
  Reststücke neben Öffnungen entfallen ersatzlos), Format-Eigenschaften,
  Allplan-Layer je Lage und für die Randbügel (0 = aktueller Layer),
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
- **ScriptObject-Struktur (v0.3):** `create_script_object` /
  `BaseScriptObject` mit `start_input` → `start_next_input` → `execute`,
  Eingabezustand über `<Constants>` + verstecktes `InputMode`-Feld,
  `on_cancel_function` mit Favoriten-Speicherung — Muster 1:1 aus
  `ArchitectureExamples/Objects/SlabOpening.py` (Branch 2026).
- **Geometrie-Eingabe (v0.3):** `ScriptObjectInteractors.PolygonInteractor`
  (Polygon zeichnen, `multi_polygon_input=True`), `PointInteractor` mit
  Preview-Callback (Rechteck-Drag), `SingleElementSelectInteractor` mit den
  Typ-UUIDs `Slab_TypeUUID`, `SlabFoundationTier_TypeUUID`,
  `IndividualFoundation_TypeUUID`, `StripFoundation_TypeUUID` — Beispiele
  `SlabOpening.py`, `Slab.py`, `ModifySlab.py`, `ModifyStripFoundation.py`,
  `ModifyBlockFoundation.py`, `ModifySlabFoundation.py`. Dicke über
  `GetSlabTierProperties(i).Thickness`, Streifenfundament-Geometrie ist die
  Achse (`GetGeometryObject()` → Linie).
- **Scanline statt Shape-Interpolation:** Die polygonale
  `BarPlacement`-Variante (Start-/End-Shape mit Interpolation,
  `PolygonalPlacement.py`) eignet sich für stetig veränderliche Shapes;
  für beliebige Konturen mit Öffnungen nutzt v0.3 stattdessen das
  Scanline-Muster aus `ReinforcementExamples/AreaPlacementExpand.py`
  (Stablinie gegen Kontur schneiden) — als reine, testbare
  Python-Implementierung in `contour_placement.py`.
- **Wechselnde Abstände:** `LinearBarBuilder.calculate_length_of_regions(
  value_list, from_pnt, to_pnt, cover_l, cover_r)` mit
  `value_list = [(Zonenlänge, Abstand, Ø), (0, Abstand, Ø), ...]` —
  [Doku 2026](https://pythonparts.allplan.com/2026/api_reference/StdReinfShapeBuilder/LinearBarPlacementBuilder/).

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
