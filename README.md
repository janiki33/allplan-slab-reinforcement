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
| v0.3.2 | Elemente werden direkt abgesetzt (nicht mehr an den Zeiger gebunden), Überdeckungsmodell aus den Beispieldateien, automatische Stösse mit SIA-Versatz, Abtreppung an Schrägen, Deckung senkrecht zur Kante | umgesetzt |
| v0.4 | Auflagererkennung (Wände/Unterzüge) mit Anschlussbewehrung, Randbügel/Anschlusseisen an Polygonkanten, Diagonalzulagen an Öffnungsecken | Roadmap |

**Hinweis:** Der Code wurde gegen die offizielle 2026-API-Doku und die
Original-Beispiele entwickelt und je Ausbaustufe von einem unabhängigen
Review geprüft, aber noch nicht in einer laufenden Allplan-Installation
getestet. Beim ersten Live-Test gezielt prüfen:

1. Breite-Handle (6. Argument von `HandleCreator.point_distance` ist ohne
   laufendes Allplan nicht eindeutig belegbar).
2. Stufen mit nur einem Stab: erwartet wird mittige Platzierung im
   Verlegefenster (`create_linear_bar_placement_from_to_by_count` mit
   Stabanzahl 1) — sonst um den halben Stababstand verschoben.
3. Elementmodus mit Einzelfundament: liefert `GetGeometryObject()` das
   Shape-Polygon lokal statt global, muss der Absetzpunkt addiert werden.

## Dateistruktur

```
Library/SlabReinforcement/SlabReinforcement.pyp      Palettendefinition (UI)
PythonPartsScripts/SlabReinforcement/                Python-Paket (Ordner = Modul)
    __init__.py                                      stellt check_allplan_version/create_script_object bereit
    slab_reinforcement.py                            ScriptObject (Eingabemodi) + Placement-Engine
    opening_clipping.py                              Reine Band-/Kapp-Logik Rechteckmodus (ohne Allplan, testbar)
    contour_placement.py                             Reine Scanline- und Abtreppungslogik (ohne Allplan, testbar)
    lap_splitting.py                                 Reine Stosslogik: Teilung, Versatz, Sperrzonen (ohne Allplan, testbar)
tests/                                               65 Unit-Tests der drei Geometriemodule (laufen ohne Allplan)
tools/Update-SlabReinforcement.cmd                   Zum Anklicken: aktualisiert den lokalen Stand
tools/Sync-SlabReinforcement.ps1                     Sync GitHub → lokales Allplan-Verzeichnis (Windows)
```

## Installation

1. `Library/SlabReinforcement/` nach `...\Std\Library\SlabReinforcement\` kopieren
   (alternativ in den `Usr`- oder `Prj`-Pfad).
2. `PythonPartsScripts/SlabReinforcement/` **komplett** (mit `__init__.py`)
   nach `...\Std\PythonPartsScripts\SlabReinforcement\` kopieren.
   **Wichtig:** Den Ordner `PythonPartsScripts` legt Allplan **nicht**
   automatisch an — er muss ggf. selbst erstellt werden. Die `.py`-Dateien
   gehören **nicht** neben die `.pyp` in den `Library`-Baum; das sind zwei
   getrennte Verzeichnisbäume.
3. Den konkreten Pfad findest du über Allmenu → *Service* → *File explorer*.
   Allplan sucht in der Reihenfolge **Prj → Std → Usr** und nimmt die erste
   Fundstelle. `Etc` und `Prg` gehören Allplan — dort nichts ablegen.
4. In Allplan: Bibliothek → Standard → SlabReinforcement starten.

Die `.pyp` verweist auf `<Name>SlabReinforcement.py</Name>` — **diese Datei
gibt es bewusst nicht.** Weil der gleichnamige Ordner ein `__init__.py`
enthält, behandelt Python ihn als Modul. Das ist die offiziell empfohlene
Struktur für PythonParts mit mehreren Modulen
([Key components → File locations](https://pythonparts.allplan.com/2026/manual/key_components/)).

Tests ohne Allplan: `python3 -m unittest discover -s tests`

> **Nach jeder Änderung an der `.py` muss Allplan neu gestartet werden.**
> Allplan lädt ein Skript nur beim ersten Start und hält es danach im
> Speicher: *„When the PythonPart is started for the second time, it's not
> loaded again … It stays in the memory until ALLPLAN is closed"*
> ([Getting started, Abschnitt Reloader](https://pythonparts.allplan.com/2026/manual/getting_started/)).
> `.pyp`-Dateien werden dagegen bei jedem Start neu gelesen — deshalb kann
> die Palette bereits neu aussehen, während noch das alte Skript läuft.
> (Mit installiertem PythonParts-SDK übernimmt der `reloader` das Neuladen.)

## Automatischer Abgleich GitHub → lokal (Windows)

`tools/Sync-SlabReinforcement.ps1` holt die fünf benötigten Dateien direkt von
`raw.githubusercontent.com` und schreibt sie in das Allplan-Benutzerverzeichnis.
GitHub ist dabei die Quelle der Wahrheit — lokale Änderungen an diesen Dateien
werden überschrieben. Geschrieben wird nur, wenn sich der Inhalt (SHA-256)
unterscheidet; bei einer Änderung wird zusätzlich `__pycache__` geleert.

Abgeglichen werden:

| GitHub | lokal (unterhalb `-AllplanUsr`) |
| --- | --- |
| `PythonPartsScripts/SlabReinforcement/SlabReinforcementScript.py` | `PythonPartsScripts\SlabReinforcement\` |
| `PythonPartsScripts/SlabReinforcement/contour_placement.py` | `PythonPartsScripts\SlabReinforcement\` |
| `PythonPartsScripts/SlabReinforcement/opening_clipping.py` | `PythonPartsScripts\SlabReinforcement\` |
| `PythonPartsScripts/SlabReinforcement/lap_splitting.py` | `PythonPartsScripts\SlabReinforcement\` |
| `Library/SlabReinforcement/SlabReinforcement.pyp` | `Library\SlabReinforcement\` |

### Per Doppelklick

`tools/Update-SlabReinforcement.cmd` ist die Datei zum Anklicken. Sie sucht
`Sync-SlabReinforcement.ps1` neben sich, lädt es sonst von GitHub (Ablage unter
`%LOCALAPPDATA%\AllplanSlabReinforcementSync\`), führt den Abgleich mit dem
Standardziel `J:\Allplan\Usr\Janosch` aus und lässt das Fenster mit dem Ergebnis
offen stehen. Anderes Ziel oder anderer Branch: die Zeilen `set "TARGET=..."`
bzw. `set "BRANCH=..."` oben in der Datei anpassen.

Einmal herunterladen, z. B. auf den Desktop:

```powershell
Invoke-WebRequest -UseBasicParsing -OutFile "$env:USERPROFILE\Desktop\Update-SlabReinforcement.cmd" `
  https://raw.githubusercontent.com/janiki33/allplan-slab-reinforcement/claude/slab-reinforcement-sync-nykay9/tools/Update-SlabReinforcement.cmd
```

Danach genügt ein Doppelklick, wann immer der lokale Stand aktualisiert werden
soll. Schalter werden durchgereicht: `Update-SlabReinforcement.cmd -Install`
richtet den automatischen Abgleich ein, `-Uninstall` entfernt ihn wieder.

### Direkt über PowerShell

Einmalig ausführen (Standardziel `J:\Allplan\Usr\Janosch`):

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Sync-SlabReinforcement.ps1 -RemoveStale
```

Dauerhaft alle 10 Minuten und bei jeder Anmeldung (geplante Aufgabe anlegen):

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Sync-SlabReinforcement.ps1 -Install
```

Wieder entfernen: `-Uninstall`. Statt der geplanten Aufgabe geht auch ein
Dauerlauf im Fenster: `-IntervalSeconds 300`.

Nützliche Parameter: `-AllplanUsr <Pfad>` (anderes Zielverzeichnis),
`-Branch <name>` (anderer Branch), `-LogFile <Pfad>` (Protokoll),
`-RemoveStale` (löscht die veraltete `SlabReinforcement.py`, deren Name mit dem
Paketordner kollidiert und den Import verhindert).

> Das Skript kopiert Dateien, es startet Allplan nicht neu — nach einer
> Aktualisierung der `.py` gilt weiterhin der Hinweis oben.

Die geplante Aufgabe läuft im angemeldeten Benutzerkontext, weil das verbundene
Laufwerk `J:` nur dort existiert. Meldet das Protokoll trotzdem
„Zielverzeichnis nicht erreichbar", stattdessen den UNC-Pfad übergeben, z. B.
`-AllplanUsr \\server\freigabe\Allplan\Usr\Janosch`.

## Fehlersuche

**Trace-Fenster einschalten** (zeigt `print()`-Ausgaben und Python-Tracebacks):
`Strg+F3` → *„Write into window"* ankreuzen → **Allplan neu starten**
(die Ausgabe erscheint erst nach dem Neustart). Optional zusätzlich
*„Write into file"* → `allplan_python.out` im TMP-Verzeichnis
(Allmenu → Service → File explorer → *My own temporary CAD data (TMP)*).

Beim Start des PythonParts sollte im Trace stehen:

```
Load slab_reinforcement.py (Version 0.3.3)
SlabReinforcement 0.3.3: create_script_object
SlabReinforcement: start_input, Modus "Polygon zeichnen"
```

- **Keine dieser Zeilen:** Allplan lädt eine andere/alte Datei → Punkt
  „Doppelte Skriptdateien" unten.
- **Andere Versionsnummer:** altes Skript im Speicher → Allplan neu starten.
- **Traceback statt der Zeilen:** die Fehlermeldung zeigt die Ursache.

**Doppelte Skriptdateien:** Allplan sucht die `.py` der Reihe nach in
`Prg`, `Etc`, `Std`, `Usr`, `Prj` und nimmt die **erste** gefundene. Eine
vergessene Kopie an früherer Stelle überschattet die neue dauerhaft. Prüfen
mit `dir /s /B SlabReinforcement*.py` über das Allplan-Verzeichnis; alle
Dubletten bis auf die gewollte löschen. Ebenso einen eventuell
mitkopierten `__pycache__`-Ordner im Zielverzeichnis löschen.

**`Script … not found`:** Diese Meldung heisst, dass Allplan die `.py`
nicht in einem seiner Suchverzeichnisse findet. Häufigste Ursachen:
der Ordner `Std\PythonPartsScripts` existiert nicht (Allplan legt ihn nicht
an), die `.py` liegt versehentlich neben der `.pyp` im `Library`-Baum, oder
im `<Script><Name>` steht ein **führender** Backslash. Ein Fehler *im*
Skript zeigt sich dagegen als Traceback im Trace-Fenster.

**Import der Nachbarmodule:** Das Paket-`__init__.py` macht den Ordner zum
Modul, dadurch funktionieren die relativen Importe zuverlässig. Zusätzlich
probiert `_load_helper_modules()` bei Bedarf den flachen Import über
`sys.path` und das Laden über den Dateipfad — alle drei Wege sind lokal
verifiziert.

## Bedienung / Parameter

- **Eingabemodus** (Seite „Geometrie"):
  - *Rechteck (Drag):* Platte mit der Maus absetzen (Vorschau folgt dem
    Fadenkreuz), danach über Handles Länge/Breite/Dicke ziehen. Voller
    Funktionsumfang inkl. Palettenöffnung, Randbügeln und Anschlusseisen.
  - *Polygon zeichnen:* beliebige Kontur zeichnen; jedes weitere
    gezeichnete Polygon wird als Öffnung interpretiert (größte Fläche =
    Kontur). Verlegung per Scanline: Stablinien werden mit der Kontur und
    allen Öffnungen verschnitten, gleiche aufeinanderfolgende Stäbe zu
    linearen Placements zusammengefasst, schräge Ränder werden abgetreppt
    (siehe Konzept unten).
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
- **Bewehrung unten / oben:** je Richtung Durchmesser, Stababstand und
  Stahlgüte. Mit „Alle Lagen gleicher Durchmesser" gilt eine gemeinsame
  ø/a-Eingabe für alle vier Lagen. Die **Betondeckung** ist ein einziger
  Wert für alle Lagen und Stabenden (Seite „Allgemein") — Modell aus
  deinem Deckenplatte-PythonPart übernommen.
- **Stösse** (eigene Seite): Übergreifungslänge als Faktor × ø, maximale
  Stablänge, Versatz benachbarter Stösse und Sperrabstand zu Öffnungen.
  Konzept und Normbezug siehe unten.
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

Die Höhenlage jedes Stabes steckt in der z-Koordinate der Verlegepunkte
(Stabachse); die Quer-Betondeckung des Shapes ist 0. Dieses Modell stammt
aus deinem Deckenplatte-PythonPart und ergibt mit einer einzigen
Betondeckung `c` (äussere Richtung = die unter „Verlegung" gewählte):

- unten aussen: `c + ø/2`
- unten innen:  `c + ø_aussen + ø/2`
- oben aussen:  `Dicke − c − ø/2`
- oben innen:   `Dicke − c − ø_aussen − ø/2`

Randverstärkungs-Zulagen liegen als eigene Ebenen innerhalb der Hauptlagen
(unten oberhalb der inneren unteren Lage, oben unterhalb der inneren oberen
Lage; X- und Y-Zulagen gestapelt), damit sich keine Stäbe durchdringen.
Lagen, für die die Plattendicke nicht ausreicht, entfallen mit einer
Meldung im Trace-Fenster statt falsch erzeugt zu werden.

## Konzept: Stösse, Schrägen, Öffnungen (Schweizer Praxis / SIA 262)

Quellenlage: Die SIA 262 wurde teilrevidiert und ist per **1.11.2025** in
Kraft; die Abschnitte Verankerung/Stösse wurden überarbeitet. Die Zitate
unten stammen aus dem **Vernehmlassungsentwurf prSIA 262:2024-04** (das
Dokument trägt den Vermerk „keine Gültigkeit") und aus der **Richtlinie zur
Betonstahlverarbeitung, 1. Auflage 2025 (SSHV/SIA)**. Vor produktivem
Einsatz an der gekauften Endfassung gegenprüfen.

### 1. Stösse — wann

Gestossen wird, sobald die erforderliche Stablänge die einstellbare
**maximale Stablänge** überschreitet (Palette „Stösse", Default **8.0 m**
auf deinen Wunsch). Zum Vergleich die Verarbeitungsrichtlinie: abgewickelte
Länge bei Stabmaterial **in der Regel 12 m, ausnahmsweise 14 m** (Ziff.
3.3.2); ausserdem sollen Stäbe **über 60 kg** vermieden werden (Ziff.
3.3.3) — bei Ø30 sind das schon ~10.8 m. Biegeformen sollen in ein
Rechteck **2.4 × 12.0 m** passen (Ziff. 3.3.1).

### 2. Stösse — wie viele Teilstäbe

Die kleinste Anzahl *n*, mit der alle Teilstäbe die zulässige Länge
einhalten. Bei *n* Teilstäben gibt es *(n−1)* Übergreifungen, also gilt
`n · l_max ≥ L + (n−1) · l_s`. Die Teilung erfolgt in **gleich lange
Stäbe** — das minimiert die Anzahl Positionen, was die Richtlinie
ausdrücklich verlangt („In der Regel gilt es, die Anzahl Positionen zu
minimieren", Ziff. 4.1.1) und wofür je Position ein fixer Betrag
verrechnet wird (Ziff. 7.1).

### 3. Stösse — wo, und der Versatz

**Normativ (prSIA 262, Ziff. 5.2.6.6):** Bei Zugstäben muss für
1.2 σ_sd statt 1.0 σ_sd bemessen werden — **ausser** wenn bei **Platten
höchstens die Hälfte der Stäbe** gestossen ist **und** der Abstand
zwischen verschiedenen Übergreifungsstössen **mindestens 0.3 · l_sd**
beträgt. Genau das setzt das Tool um:

- Ein Verlegelauf wird in **gerade und ungerade Stäbe** aufgeteilt (zwei
  Placements mit doppeltem Stababstand). Damit ist in jedem Schnitt
  höchstens die Hälfte der Stäbe gestossen.
- Beide Gruppen erhalten gegenläufig verschobene Stosslagen; der
  Längsversatz ist **`StaggerFactor` × Übergreifungslänge**, Default
  **0.3** entsprechend der Norm.

**Ebenfalls normativ (Ziff. 5.2.6.3):** *„Stossverbindungen sind nach
Möglichkeit in Zonen geringer Beanspruchung anzuordnen."* Da du Wände und
Lastverteilung ausdrücklich ausgeklammert hast, kennt das Tool die
Auflager nicht und kann diese Zonen nicht selbst bestimmen. Es setzt die
Stösse deshalb geometrisch gleichmässig und hält sie nur von Öffnungen
frei. **Das bleibt eine Prüfaufgabe:** Als Praxisregel gilt für
Flachdecken — untere Bewehrung im Auflagerbereich stossen, obere
Bewehrung im Feld, nie über der Stütze. Zu beachten ist zusätzlich
Ziff. 5.5.3.3: mindestens die Hälfte der Feldbewehrung ist **bis über die
Auflager** zu führen.

**Öffnungen:** Stossfugen werden aus einer Sperrzone um jede Öffnung
herausgeschoben (`LapOpeningMargin`, Default 500 mm). Reicht der
zulässige Spielraum nicht, wird die Lage gewählt, die den grössten
Abstand zur Sperrzone hat.

### 4. Übergreifungslänge

`l_s = OverlapFactor × ø`, Default **50 ø** (dein bisheriger Bürowert).
**Wichtiger Hinweis:** Nach prSIA 262 gilt `l_sd = 1.2 · l_bd` (min. 15 ø),
und l_bd hängt von Betonsorte, **Verbundbedingung**, Stabdurchmesser und
rechnerischer Überdeckung ab (Gl. 106, Tabellen 19/20). Debrunner Acifer
weist ausdrücklich darauf hin, dass die alte Faustregel **50 ø künftig
nicht mehr generell ausreicht** — insbesondere bei *mässigen*
Verbundbedingungen (+20 %). Verbundbedingungen sind *gut*, wenn der Stab
≤ 300 mm über dem Schalungsboden oder > 300 mm unter der Oberfläche der
Betonieretappe liegt — bei üblichen Deckenstärken also beide Lagen, bei
dicken Bodenplatten ist die **obere Lage mässig**. Der Faktor bleibt
deshalb ein Palettenwert und wird nicht fest codiert.

### 5. Schrägen — Abtreppung

Für die Abtreppung gibt es **keine SIA- oder Verbandsregel** (geprüft in
prSIA 262 und in der Verarbeitungsrichtlinie). Das Tool verwendet daher
eine klar definierte, konfigurierbare **Bürostandard-Regel**:

> Aufeinanderfolgende Stäbe bilden eine Stufe, solange **kein Stab der
> Stufe dadurch mehr als `StepMaxLoss` kürzer wird**, als er geometrisch
> sein könnte (Default 250 mm). Alle Stäbe einer Stufe erhalten dieselbe
> Länge: Anfang = grösster Anfang, Ende = kleinstes Ende der Stufe.

Daraus folgt unmittelbar:

- Kein Stab ragt je über die Betonkante hinaus (es wird immer das
  ungünstigste Ende der Stufe verwendet, und das Längenraster
  `StepLengthRaster`, Default 50 mm, rundet **nach innen**).
- Die unbewehrte Zone an der Schräge ist durch `StepMaxLoss` begrenzt.
- Ein grösserer Wert ergibt weniger, dafür gröbere Stufen — bei 45° und
  15 cm Stababstand liefert der Default 2 Stäbe je Stufe und 30 cm
  Längensprung.
- Eine Stufe bricht ausserdem, wo sich die Segmentanzahl ändert (Beginn
  einer Öffnung) oder der Stababstand wechselt. Rechtwinklige Bereiche
  bleiben ein einziges Placement.

**Betondeckung an der Schräge:** Die Deckung wird **senkrecht zur Kante**
eingehalten. Bei einem Winkel α zwischen Stabachse und Kante ist der
Rückversatz in Stabrichtung `c / sin α` — bei 45° also das 1.41-fache der
Deckung. Für spitze Winkel begrenzt `MaxEdgeSetback` (Default 150 mm) den
Rückversatz, damit Stäbe in spitzen Ecken nicht unbrauchbar kurz werden.
Öffnungsränder erhalten dieselbe Behandlung.

### 6. Öffnungen — Zulagen

Auch hier gibt es **in SIA 262 keine Regel** zur Zulagebewehrung um
Deckenöffnungen; die Norm fordert lediglich, freie Plattenränder mit
aufgebogener Längsbewehrung oder Bügeln zu umschliessen (Ziff. 4.4 /
5.5.3.5). Die im Tool umgesetzten Zulagen (Anzahl, Ø, Abstand, Überstand)
sind daher **konfigurierbarer Bürostandard, nicht normbelegt**. Verbreitete
Praxis: mindestens die gekappte Querschnittsfläche je Richtung zulegen und
die Zulagen um mindestens die Verankerungslänge über die Öffnungsecke
hinausführen; zusätzlich Diagonalstäbe an den Ecken gegen die 45°-Risse.
Diagonalzulagen erzeugt das Tool derzeit **nicht** (Roadmap v0.4).

### 7. Betondeckung — Nennwerte

prSIA 262 Tabelle 18, planmässige Bewehrungsüberdeckung `c_nom` [mm]:

| XC1 | XC2 | XC3 | XC4 | XD1–XD3 |
|-----|-----|-----|-----|---------|
| 20  | 35  | 40  | 40  | 55      |

Zuordnung: XC1 Geschossdecke innen (trocken), XC2 Fundationen/erdberührt,
XC3 mässige Feuchte bzw. aussen vor Regen geschützt, XC4 aussen
ungeschützt, XD3 Parkdeck/Taumittel. **Zwingend zusätzlich (Ziff.
5.2.2.5):** Beton direkt gegen Erdreich `c_nom ≥ 90 mm`, gegen
vorbereiteten Untergrund (Sauberkeitsschicht) `≥ 50 mm`. Massgebend ist
stets der grösste Wert aus Verbund, Feuerwiderstand und Korrosion
(Ziff. 5.2.2.1). SIA arbeitet **nicht** mit einem additiven Δc_dev wie
EC2 — `c_nom` ist bereits der Planwert. Der Palettenwert
„Betondeckung" (Default 35 mm) ist entsprechend zu setzen.

### Normen / Bemessung — Zusammenfassung

Es sind **keine** Normwerte fest codiert. Normativ begründete Defaults
(Stossversatz 0.3 × l_s, max. 50 % gestossene Stäbe je Schnitt) sind als
Palettenwerte einstellbar und oben mit Fundstelle belegt. Alles, wofür es
in SIA 262 keine Regel gibt — Abtreppung, Öffnungszulagen, Stosslänge als
Faktor × ø — ist ausdrücklich als konfigurierbarer Bürostandard
gekennzeichnet. Einzige normabhängige Automatik: der
Biegerollendurchmesser über
`AllplanReinf.BendingRollerService.GetBendingRollerFactor(...)` aus den
Allplan-Projekteinstellungen (SIA 262: d₃ = 4 ø bis Ø16, 7 ø bis Ø30).
**Die Bemessung bleibt Aufgabe der Tragwerksplanung** — das Tool verlegt
geometrisch, es bemisst nicht.

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
