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
| v0.2.1 | Randausbildung je Kante (U-Randbügel / Anschlusseisen / separate Anschlusseisen / keine), Stoßfaktor, „Alle Lagen gleich", wählbares Lagenschema, Allplan-Layer je Lage, Handles | umgesetzt |
| v0.3 | ScriptObject-Struktur mit drei Eingabemodi (Rechteck-Drag / Polygon zeichnen / Element wählen), Scanline-Verlegung für polygonale Konturen, mehrere Öffnungen, Randverdichtung via `calculate_length_of_regions` | umgesetzt |
| v0.3.3 | Elemente werden direkt abgesetzt (nicht mehr an den Zeiger gebunden), Überdeckungsmodell aus den Beispieldateien, automatische Stösse mit SIA-Versatz, Abtreppung an Schrägen, Deckung senkrecht zur Kante | umgesetzt |
| v0.4 | Verlegekonzept über Rechteckzerlegung (Rechtecke je Lage, Stoss an jeder Verlegungsgrenze, Abtreppung am längsten Stab), Randbügel und Anschlusseisen auch im Polygon-/Elementmodus | umgesetzt |
| v0.5 | Aussparungs-Werkzeug: Rand-, Diagonal- und Bügelzulagen um beliebige Aussparungspolygone, Erkennung der Aussparungselemente ohne Antippen | umgesetzt |
| v0.6 | Aussparungen werden über Palettenbuttons **hinzugefügt** statt vorab festgelegt: beliebig viele, jederzeit, einzeln wieder entfernbar | umgesetzt |
| v0.7 | Neue Stoss-Systematik nach Bürostandard (14-Formen-Studienblatt): minimale Verlegungsanzahl, Fluchten, Passeisen-Grenze, eine Stosslinie je Abtreppung | umgesetzt |
| Korrektur | Separates Anschlusseisen im Konturmodus: Vorzeichenfehler behoben, durch den der Stab an einer von zwei gegenüberliegenden Kantenseiten um 2 × Stoßlänge außerhalb der Platte statt mittig auf ihr lag | umgesetzt |
| v0.8 | Wandanschluss: 3D-Wände antippen, L-förmige Anschlusseisen entlang der langen Wandseiten (Vorbild Büro-PythonPart "AnschlusseisenBew") | umgesetzt |
| v0.8.5 | Wandauswahl als Mehrfachauswahl mit Toggle (erneut wählen = abwählen); ESC beendet nur die Auswahlrunde statt des PythonParts; Aussparungs-Erkennung protokolliert jede Stufe im Trace-Fenster | umgesetzt |
| v0.9 | Auflagererkennung (Wände/Unterzüge) mit automatischer Anschlussbewehrung | Roadmap |

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
Library/SlabReinforcement/layers_outer_*.png         Bilder der beiden Lagenschemata (Palettenauswahl)
PythonPartsScripts/SlabReinforcement/                Python-Paket (Ordner = Modul)
    __init__.py                                      stellt check_allplan_version/create_script_object bereit
    slab_reinforcement.py                            ScriptObject (Eingabemodi) + Placement-Engine
    opening_clipping.py                              Reine Band-/Kapp-Logik Rechteckmodus (ohne Allplan, testbar)
    contour_placement.py                             Reine Scanline- und Abtreppungslogik (ohne Allplan, testbar)
    opening_reinforcement.py                         Reine Geometrie der Aussparungsbewehrung (ohne Allplan, testbar)
    lap_splitting.py                                 Reine Stosslogik: Teilung, Versatz, Sperrzonen (ohne Allplan, testbar)
    state_persistence.py                             Sichert die eingegebene Geometrie ins PythonPart (ohne Allplan, testbar)
    wall_connection.py                               Reine Geometrie der Wand-Anschlusseisen (ohne Allplan, testbar)
    lap_planning.py                                  Stossplanung nach Bürosystematik (ohne Allplan, testbar)
tests/                                               Unit-Tests der Geometriemodule (laufen ohne Allplan)
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

`tools/Sync-SlabReinforcement.ps1` spiegelt zwei Ordner in das
Allplan-Benutzerverzeichnis:

| GitHub | lokal (unterhalb `-AllplanUsr`) |
| --- | --- |
| `PythonPartsScripts/SlabReinforcement/` | `PythonPartsScripts\SlabReinforcement\` |
| `Library/SlabReinforcement/` | `Library\SlabReinforcement\` |

Welche `.py`/`.pyp`-Dateien darin liegen, fragt das Skript bei **jedem Lauf**
über die GitHub-API ab — es gibt keine fest verdrahtete Dateiliste, die bei
einer Umbenennung veraltet. Neue Dateien kommen dadurch automatisch mit.

GitHub ist die Quelle der Wahrheit:

- Verglichen wird über den Git-Blob-Hash; heruntergeladen wird nur, was sich
  unterscheidet.
- Lokale Änderungen an den gespiegelten Dateien werden überschrieben.
- Lokale `.py`/`.pyp`-Dateien, die es im Repository nicht (mehr) gibt, werden
  gelöscht — das fängt Umbenennungen ab, die sonst als Karteileiche den Import
  blockieren. Mit `-KeepExtraFiles` unterbleibt das.
- Bei jeder Änderung wird `__pycache__` geleert.

Die API erlaubt 60 Abfragen pro Stunde und IP; der Abgleich braucht zwei davon.
Reicht das im Büro nicht, `-Token <GitHub-PAT>` mitgeben.

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
  https://raw.githubusercontent.com/janiki33/allplan-slab-reinforcement/main/tools/Update-SlabReinforcement.cmd
```

Danach genügt ein Doppelklick, wann immer der lokale Stand aktualisiert werden
soll. Schalter werden durchgereicht: `Update-SlabReinforcement.cmd -Install`
richtet den automatischen Abgleich ein, `-Uninstall` entfernt ihn wieder.

### Direkt über PowerShell

Einmalig ausführen (Standardziel `J:\Allplan\Usr\Janosch`):

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Sync-SlabReinforcement.ps1
```

Dauerhaft alle 10 Minuten und bei jeder Anmeldung (geplante Aufgabe anlegen):

```powershell
powershell -ExecutionPolicy Bypass -File .\tools\Sync-SlabReinforcement.ps1 -Install
```

Wieder entfernen: `-Uninstall`. Statt der geplanten Aufgabe geht auch ein
Dauerlauf im Fenster: `-IntervalSeconds 300`.

Nützliche Parameter: `-AllplanUsr <Pfad>` (anderes Zielverzeichnis),
`-Branch <name>` (anderer Branch), `-LogFile <Pfad>` (Protokoll),
`-KeepExtraFiles` (lokale Dateien behalten, die es im Repository nicht gibt),
`-Token <PAT>` (bei erschöpftem API-Limit).

> Das Skript kopiert Dateien, es startet Allplan nicht neu — nach einer
> Aktualisierung der `.py` gilt weiterhin der Hinweis oben.

Die geplante Aufgabe läuft im angemeldeten Benutzerkontext, weil das verbundene
Laufwerk `J:` nur dort existiert. Meldet das Protokoll trotzdem
„Zielverzeichnis nicht erreichbar", stattdessen den UNC-Pfad übergeben, z. B.
`-AllplanUsr \\server\freigabe\Allplan\Usr\Janosch`.

## Wandanschluss (Anschlusseisen an 3D-Wänden)

Auf der Palettenseite **Wandanschluss** werden Wände per
**Mehrfachauswahl** erfasst (Klick oder Auswahlfenster, ESC beendet nur die
Runde). **Erneutes Wählen einer bereits erfassten Wand wählt sie ab** —
hinzufügen und abwählen gehen mit derselben Auswahl; zusätzlich gibt es
„Letzte/Alle entfernen". Aus jeder
Wand wird der Grundriss gelesen; entlang der **langen Wandseiten** entsteht
je eine Verlegung L-förmiger Anschlusseisen:

- **Vertikaler Schenkel** an der Wandseite (seitliche Deckung in die Wand),
  ragt um `Stossfaktor × ø` über OK Platte — Stoss mit der Wandbewehrung.
- **Horizontaler Schenkel** unten in der Platte, von der Wand weg. Länge
  automatisch nach dem Büro-Vorbild (`Stosslänge − verfügbarer Weg in der
  Plattendicke`, mindestens die Mindest-Schenkellänge, auf 10 mm gerundet)
  oder fest vorgegeben.

Biegeform und Rotation folgen dem Büro-PythonPart „AnschlusseisenBew"
(Fall 2, getrennte L-Eisen je Wandseite): `ReinforcementShapeBuilder` mit
Deckungswerten je Segment, gedreht mit `Rz = Winkel der Aussennormalen`.

Die kurzen **Stirnseiten** der Wand bekommen keine Eisen (Kanten kürzer als
1.6 × Wanddicke entfallen). Wände dürfen über die Platte hinauslaufen — die
Verlegung wird an der Plattenkontur abgeschnitten; Reststücke unter einem
Stababstand entfallen. Die gewählten Wände werden mit dem PythonPart
gespeichert und überleben das spätere Bearbeiten.

## Späteres Bearbeiten eines abgesetzten PythonParts

Ein abgesetztes PythonPart wird beim Doppelklick mit einem **frischen**
ScriptObject geöffnet. Allplan stellt dabei nur die Palettenwerte wieder
her — die per Interactor eingegebene Geometrie (Absetzpunkt, gezeichnete
Kontur, Aussparungspolygone) lebt allein im ScriptObject und ist danach weg.
Ohne sie liefert `execute()` ein leeres Ergebnis und das Element lässt sich
nicht mehr bearbeiten.

Deshalb legt `state_persistence.py` diese Geometrie beim Abschluss jeder
Eingaberunde als Zeichenkette im versteckten Parameter `GeometryState` ab
(Koordinaten auf 0.1 mm gerundet). Beim Öffnen mit
`InputMode == INPUT_MODE_CREATION` wird sie zurückgelesen und die Eingabe
gilt als abgeschlossen.

Der Stand trägt eine Fassungsnummer (`STATE_VERSION`). Passt sie nicht oder
ist der Parameter leer, wird der Stand verworfen statt falsch ausgelegt —
im Trace-Fenster erscheint dann ein Hinweis.

> **Elemente aus einer Fassung vor dieser Änderung** haben keinen
> gespeicherten Geometriestand und lassen sich weiterhin nicht bearbeiten.
> Sie müssen einmal neu abgesetzt werden.

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
  2 × Stoßlänge, mittig auf der Kante) oder „Keine". Im Polygon- und
  Elementmodus gilt die Option **je Konturkante**: Jede Kante bekommt die
  Einstellung der Richtung, in die ihre Aussennormale zeigt — eine schräge
  Kante also die der überwiegenden Richtung. Die Bügelschenkel zeigen
  immer nach innen (Rotation = Innennormale − 90°).
  **Randbügel ignorieren schräge Plattenseiten:** An einer Schräge wird
  kein Bügel gesetzt; stattdessen laufen die angrenzenden achsparallelen
  Kanten bis zur Bounding Box durch, als wäre die Schräge ausgefüllt — so
  wie es die Rechtecke aus Schritt 1 vorgeben.
  **Randbügel-Ausführung** ist wählbar: *Einzeln* erzeugt eigene U-Bügel,
  *Am Eisen angebogen* verzichtet darauf und biegt stattdessen die Stäbe
  der 1. und 2. Lage an dieser Kante ab (Hakenlänge = Achsmass des
  Bügels). Lage und Verlegung der Bewehrungslagen ändern sich dadurch
  nicht. Die Stoßlänge ist als
  Stoßfaktor (Vielfaches von ø) konfigurierbar — bewusst kein Normwert.
  Randbügel und separate Anschlusseisen sparen den Bereich einer Öffnung
  aus, wenn diese den jeweiligen Randstreifen schneidet. Bekannte
  Einschränkungen: bei aktiver Öffnung starten die
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
  Allplan-Layer je Lage (0 = aktueller Layer; Randbügel und
  Öffnungszulagen erben den Layer der Lage ihrer Richtung),
  „Als PythonPart erzeugen".

Bei jeder Parameteränderung ruft Allplan `create_element` neu auf —
das ist die übliche Live-Vorschau von Standard-PythonParts.

### Lagerichtung

Die Lagerichtung wird über den Parameter **`LayerVariant`** gewählt —
eine `StringComboBox` mit den Werten `Variante 1` und `Variante 2`.
Darunter zeigt ein `Picture`-Parameter die gewählte Variante gross an
(`LayerVariantPic1` / `LayerVariantPic2`, umgeschaltet über
`<Visible>LayerVariant == "Variante 1"</Visible>`).

| Variante | Bild | Bedeutung |
| --- | --- | --- |
| Variante 1 | `layers_outer_y.png` | 1. Lage senkrecht, 2. waagrecht, 3. waagrecht, 4. senkrecht → **1./4. Lage in Y** |
| Variante 2 | `layers_outer_x.png` | 1. Lage waagrecht, 2. senkrecht, 3. senkrecht, 4. waagrecht → **1./4. Lage in X** |

Durchgezogen = untere Lagen, gestrichelt = obere. Die Bildpfade sind
relativ zur `.pyp`
([Picture](https://pythonparts.allplan.com/2026/manual/key_components/palette/parameter_with_layout_control/)).

Die Auswertung steckt in `layer_scheme.py` (`layer_scheme_value`,
`outer_direction`) und ist ohne Allplan testbar — die Zuordnung war
mehrfach die Ursache falsch herum liegender Lagen.

**Warum nicht `PictureButtonList` oder `RadioButtonGroup`:**
`PictureButtonList` ist eine Ereignis-Knopfleiste ohne Zustand, die
Auswahl erreichte den Parameter nie. Eine `RadioButtonGroup` nach dem
offiziellen Beispiel
[RadioButtons.pyp](https://github.com/NemetschekAllplan/PythonPartsExamples/blob/main/Library/Examples/PythonParts/PaletteExamples/BasicControls/RadioButtons.pyp)
griff in dieser Palette ebenfalls nicht. `StringComboBox` mit
String-`<Visible>` ist hier nachweislich funktionierend (`InputMethod`),
darum die Umstellung. Bei jedem Wechsel des Steuerelementtyps wird der
Parameter umbenannt, weil `<ReadLastInput>True</ReadLastInput>` sonst
den gespeicherten Altwert des alten Typs weiterreicht.

### Allplan-Layer der Hauptbewehrung

Die vier Folien hängen an der **Lagennummer**, nicht an der Richtung
(`LayerLevel1` … `LayerLevel4`): die 1. Lage ist immer die unterste,
unabhängig davon, ob sie in X oder in Y läuft. Beim Wechsel der
Lagerichtung wandert der Layer damit mit der Lage mit.

Vorher hiessen die Parameter `LayerBottomX`/`LayerBottomY`/`LayerTopX`/
`LayerTopY` und waren an die Richtung gebunden — dadurch blieb die Folie
der „1. Lage" beim Variantenwechsel auf den waagrechten Eisen stehen,
obwohl die Höhenlagen im Modell korrekt tauschten.

### Betondeckung und Höhenlagen

Die Betondeckung ist wahlweise **ein Wert für alles** („Alle gleich") oder
**getrennt** einstellbar:

- **unten** `c_u` — Abstand Unterkante Decke bis **Aussenkante der 1. Lage**;
  die Höhe der 2. Lage folgt daraus.
- **oben** `c_o` — Abstand Oberkante Decke bis **Aussenkante der 4. Lage**;
  die Höhe der 3. Lage folgt daraus.
- **seitlich** `c_s` — gilt für die Stabenden und die Verlegeränder.

Die Höhenlage steckt in der z-Koordinate der Verlegepunkte (Stabachse),
die Quer-Betondeckung des Shapes ist 0 — Modell aus dem
Deckenplatte-PythonPart. Mit der äusseren Richtung aus „Verlegung":

- 1. Lage (unten aussen): `c_u + ø/2`
- 2. Lage (unten innen):  `c_u + ø_1 + ø/2`
- 4. Lage (oben aussen):  `Dicke − c_o − ø/2`
- 3. Lage (oben innen):   `Dicke − c_o − ø_4 − ø/2`

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

### 0. Verlegekonzept in drei Schritten

Die Verlegung entsteht nicht Stab für Stab, sondern über Bereiche:

1. **Rechtecke bilden.** Die Kontur wird in achsparallele Rechtecke
   zerlegt. Getrennt wird dort, wo die Kontur eine Kante **parallel zur
   Stabrichtung** hat — deshalb sind die Rechtecke je Lage anders
   ausgerichtet (X-Lage bricht an waagrechten, Y-Lage an senkrechten
   Kanten). Ein schräger Rand lässt den allen Stäben gemeinsamen Teil als
   Rechteck stehen; der veränderliche Rest wird zur Abtreppungszone. Über
   den Palettenwert **Rechteckgrenze** ist wählbar, ob das Rechteck an der
   nächsten Konturkante endet (Rechtecke fluchten über die Bänder hinweg)
   oder erst am Beginn der Schräge.
2. **Stosslage.** Wo zwei Verlegungen längs aneinanderstossen — typisch
   Rechteck und angrenzende Abtreppung — überlappen sie sich um die
   Übergreifungslänge, unabhängig von der Stablänge. Verlängert wird die
   Abtreppungszone in das Rechteck hinein, sodass die Rechteckgrenze die
   Stosslage definiert.
3. **Verlegungen.** Je Zone eine Verlegung. Ist ein Stab danach immer noch
   länger als die zulässige Stablänge, wird er zusätzlich gestossen.
   Verlegungen mit nur einem Stab entstehen nicht: Ein einzelner Stab wird
   der Nachbarverlegung zugeschlagen, die dafür verlängert wird.

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

### 3. Stösse — wo

**Kein automatischer Stossversatz.** SIA 262 Ziff. 5.2.6.6 verlangt für
Platten, dass höchstens die Hälfte der Stäbe im selben Schnitt gestossen
ist und benachbarte Stösse mindestens 0.3 · l_sd auseinanderliegen. Das
Tool setzt das **nicht** automatisch um: Ein automatischer Versatz müsste
jeden Verlegelauf in gerade und ungerade Stäbe aufteilen, was zwei
ineinandergeschobene Verlegungen je Bereich ergibt — auf Wunsch des
Anwenders bewusst entfernt. **Der Versatz ist damit eine Prüfaufgabe der
Tragwerksplanung.**

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
> Stufe dadurch mehr als `StepMaxLoss` von seiner geometrischen Länge
> abweicht** (Default 250 mm). Alle Stäbe einer Stufe erhalten dieselbe
> Länge.

Woran diese Länge gemessen wird, ist eine Entscheidung mit einem
unvermeidlichen Zielkonflikt — deshalb die Palettenoption
**`StepMeasuredAt`**:

| Einstellung | Länge der Stufe | Folge |
| --- | --- | --- |
| **Kürzestes Eisen** | Schnittmenge aller Stäbe | Kein Stab verlässt den Beton, die seitliche Deckung ist überall eingehalten. Die längeren Stäbe verlieren bis zu `StepMaxLoss` an Verankerungslänge. |
| **Längstes Eisen** (Default) | Hülle aller Stäbe | Die Stufe folgt der Schräge so eng wie möglich. Die kürzeren Stäbe ragen dafür um bis zu `StepMaxLoss` über ihre eigene Länge hinaus — also **in die seitliche Deckung hinein und darüber hinaus**. |

Beides zugleich geht nicht: eine Verlegung hat genau eine Stablänge. Wer
die Stufe am längsten Stab vermisst, akzeptiert damit, dass die kürzeren
Stäbe über die Betonkante hinauslaufen; `StepMaxLoss` begrenzt, wie weit.

Daraus folgt weiter:

- Das Längenraster `StepLengthRaster` (Default 50 mm) rundet **nach
  innen**. Ein Stab darf nie über den Referenzstab hinauswachsen, sonst
  wäre die seitliche Deckung schon durch die Rundung verletzt.
- Ein grösserer Wert ergibt weniger, dafür gröbere Stufen — bei 45° und
  15 cm Stababstand liefert der Default 2 Stäbe je Stufe und 30 cm
  Längensprung.
- Eine Stufe bricht ausserdem, wo sich die Segmentanzahl ändert (Beginn
  einer Öffnung) oder der Stababstand wechselt. Rechtwinklige Bereiche
  bleiben ein einziges Placement.

## Aussparungen

Aussparungen sind **keine Voreinstellung**, die vor der Eingabe
feststeht, sondern werden nach und nach hinzugefügt. Auf der
Palettenseite *Aussparungen*:

| Bedienelement | Wirkung |
| --- | --- |
| **Aussparung zeichnen (hinzufügen)** | Startet jederzeit eine weitere Eingaberunde. Beliebig viele Polygone zeichnen, ESC beendet die Runde; das Ergebnis wird an die Liste **angehängt**. Beliebig oft wiederholbar, in allen drei Eingabemodi. Die bereits erzeugte Bewehrung bleibt während des Zeichnens sichtbar. |
| **Letzte gezeichnete entfernen** | Nimmt die zuletzt hinzugefügte Aussparung wieder heraus. |
| **Alle gezeichneten entfernen** | Leert die Liste der gezeichneten Aussparungen; die automatisch erkannten bleiben. |
| **Vorhandene automatisch erkennen** | Innenkonturen der Eingabe und Aussparungselemente der gewählten Decke. Jederzeit ein-/ausschaltbar, ohne die Eingabe zu wiederholen. |
| *Rechteckige Aussparung (Zahleneingabe)* | Optional zusätzlich eine Aussparung über X/Y/Breite/Länge. |

Technisch sind das Palettenbuttons (`<ValueType>Button</ValueType>` mit
`<EventId>`), die im Skript in `on_control_event(event_id) -> bool`
landen — der Rückgabewert baut die Palette neu auf
([Button-Parameter](https://pythonparts.allplan.com/2024/manual/key_components/palette/parameters/parameter_with_button/)).
Erkannte und gezeichnete Aussparungen werden getrennt gehalten: die
erkannten ermittelt jede Neueingabe neu, die gezeichneten sammeln sich an.

`MinOpeningSize` (Default 150 mm) filtert automatisch erkannte
Innenkonturen: alles, dessen kleinere Seite darunter liegt, ist in der
Praxis ein Zeichnungsartefakt (doppelte Punkte, Rundungen) und keine
Aussparung.

Eine polygonale Aussparung im Rechteckmodus schaltet die Platte intern auf
den Konturpfad um — die Bandlogik des Rechteckmodus kennt nur
achsparallele Rechtecke, der Scanline-Pfad beliebige Polygone.

**Aussparungen als eigene Elemente:** In Allplan ist eine Aussparung in
einer Decke kein Teil von deren Konturpolygon, sondern ein **Kindelement**.
Im Elementmodus liest das Tool sie deshalb zusätzlich über
`BaseElementAdapterChildElementsService.GetChildModelElements`
([2026-API-Referenz](https://pythonparts.allplan.com/2026/api_reference/InterfaceStubs/NemAll_Python_IFW_ElementAdapter/BaseElementAdapterChildElementsService/))
— die Aussparungen müssen also **nicht einzeln angetippt** werden.
Gefiltert wird bewusst **nicht** über eine Typ-UUID: welche Konstante die
Aussparung bezeichnet, liess sich in der Dokumentation **nicht belegen**.
Statt zu raten, wird jedes Kindelement genommen, aus dem sich eine
geschlossene Kontur lesen lässt, die vollständig innerhalb der
Plattenkontur liegt und kleiner ist als diese.

### Bewehrung um die Aussparung

Beides läuft über `opening_reinforcement.py` und funktioniert für
**beliebige, auch schiefe** Aussparungspolygone:

- **Randzulagen:** je Aussparungskante eine Schar Stäbe **parallel zu
  dieser Kante**, erste Achse einen Stabdurchmesser von der Kante entfernt,
  weitere im eingestellten Abstand nach aussen. Jeder Stab ragt um die
  Übergreifungslänge über beide Ecken hinaus.
- **Diagonalzulagen:** je Ecke Stäbe senkrecht zur Winkelhalbierenden, die
  die Ecke überspannen — gegen den 45°-Riss, der von jeder einspringenden
  Ecke ausgeht. Nur an echten Knicken (> 20°), ein Zwischenpunkt auf einer
  geraden Kante erzeugt keine Diagonale.

Jeder Zulagestab wird anschliessend an der Plattenkontur **und an allen
anderen Aussparungen** abgeschnitten, mit derselben Deckungsregel wie die
Hauptlagen (senkrecht zur geschnittenen Kante, an Schrägen `c / sin α`).
Reststücke unter der Mindeststablänge entfallen.

- **Randbügel** (`OpeningStirrupStyle`), wie am Plattenrand mit derselben
  Auswahl:
  - *Einzeln* — separate offene U-Bügel entlang jeder Aussparungskante, im
    eingestellten Abstand, Schenkel von der Öffnung weg in den Beton
  - *Am Eisen angebogen* — kein eigener Bügel; stattdessen bekommen die
    Lagenstäbe, die an der Aussparung enden, den vollen U-Bügel angebogen
    (dieselbe Freiform wie am Plattenrand)
  - *Keine*

Plattenrand und Aussparungsrand haben dafür **getrennte** Optionen
(`StirrupStyle` bzw. `OpeningStirrupStyle`) — am Rand einzeln und an der
Aussparung angebogen (oder umgekehrt) ist damit möglich.

Randzulagen und Diagonalzulagen haben einen eigenen Allplan-Layer
(`LayerOpeningEdge`, `LayerOpeningDiagonal`, 0 = aktueller Layer, auf der
Seite *Allgemein*). Die **Randbügel der Aussparung** dagegen erben den
Layer der Lage, deren Stäbe senkrecht auf die jeweilige Kante zulaufen —
dieselbe Lage, aus der auch Ø, Abstand und Stahlgüte des Bügels stammen.
Eine eigene Einstellung dafür gibt es bewusst nicht.

Die Höhenlage: Zulagen liegen **innerhalb** der Hauptlagen — unten
oberhalb der inneren unteren Lage, oben unterhalb der inneren oberen Lage.
Kanten mit geradem Index liegen in der einen, Kanten mit ungeradem Index
in der nächsten Ebene darüber (bei einer rechteckigen Aussparung genau die
beiden Hauptrichtungen), die Diagonalen in einer dritten. So durchdringen
sich weder Zulagen untereinander noch Zulagen und Hauptlagen. Ist zwischen
den Hauptlagen kein Platz mehr, entfällt die Ebene mit einer Meldung im
Trace-Fenster statt zu kollidieren.

## Stoss-Systematik (Bürostandard)

Abgenommen am interaktiven 14-Formen-Studienblatt. Leitsatz: **minimale
Anzahl Verlegungen — Stösse selbst kosten nichts.** Kein Stossraster.

1. **Überlänge:** Stäbe über `MaxBarLength` werden gleichmässig geteilt
   (13 m → mittig, 19 m → gedrittelt), Stösse äquidistant.
2. **Passeisen-Grenze** (`PassBarThreshold`, Default 3 m): jedes Eisen ab
   dieser Länge enthält mindestens einen Stoss — nie ein exakt
   geschnittenes Passeisen; die Teilstücke lassen sich stattdessen
   schieben. Kürzere Eisen dürfen Passeisen sein.
3. **Fluchten:** Aussparungskanten und einspringende Ecken quer zur
   Stabrichtung sind bevorzugte Stossachsen und laufen durch die ganze
   Platte (Aussparung → 4 Verlegungen: links/rechts/darüber/darunter) —
   aber nur, wenn sie sich lohnen: die Kante muss mindestens
   `FluchtMinShare` (Default 25 %) der Plattenbreite belegen. Kleine
   Aussparungen in grossen Platten fallen durch — dort stösst jedes
   Segment für sich mittig (belegt am realen Projektbeispiel
   20.5 × 15 m). Eine Eck-Flucht entfällt zusätzlich, wenn die kurze
   Seite ohnehin mittig gestossen wird (≥ Passeisen-Grenze).
4. **Abtreppung:** je Bereich **eine gerade Stosslinie**, geerbt vom
   Pflichtstoss der vollen Bahnen; sie rutscht parallel nach innen, bis
   jedes Stufenstück die `StepMinPieceLength` (Default 2 m) erreicht.
   Ein abgetrepptes Eisen ist nie ein Passeisen — der Überstand wandert
   als zusätzliche Übergreifung in den Stoss statt geschnitten zu
   werden. Die Stufenbildung selbst ist unverändert (Vermessung am
   längsten Stab, Raster nach aussen, `StepMaxLoss`).
5. **Anker-Regel:** Fällt eine Aussparungszone unter die Flucht-Grenze,
   wird ihre Aussenkante trotzdem zur Stossachse, wenn die dort
   beginnenden freien Eisen selbst überlang sind — gestörte und volle
   Bahnen teilen sich dann die Überlängen-Achsen des freien Felds, das
   als **eine durchgehende Verlegung** über die ganze Platte läuft
   (Regel aus dem Projektbeispiel: „rechts eine über die ganze Länge,
   links davon die Höhenunterschiede").
6. **Keine Ein-Stab-Verlegungen:** Einzelgänger werden mit dem Nachbarn
   zusammengefasst; Verlegungen mit identischem Stück und nahtlos
   anschliessenden Positionen werden zusammengelegt.

Diese Regeln sind **Bürostandard, nicht normbelegt** — SIA 262 regelt
Übergreifungslänge und Stossanteile (Ziff. 5.2.6), aber nicht die
Stossanordnung in Flächen. Umgesetzt in `lap_planning.py`.

**Betondeckung an der Schräge:** Die Deckung wird **senkrecht zur Kante**
eingehalten. Bei einem Winkel α zwischen Stabachse und Kante ist der
Rückversatz in Stabrichtung `c / sin α` — bei 45° also das 1.41-fache der
Deckung. Für spitze Winkel begrenzt `MaxEdgeSetback` (Default 150 mm) den
Rückversatz, damit Stäbe in spitzen Ecken nicht unbrauchbar kurz werden.
Öffnungsränder erhalten dieselbe Behandlung.

**Hilfsparallelen (strikte Deckungszonen):** Um jede Aussparung liegt
eine nach aussen um die Deckung verbreiterte Zone, innerhalb der
Plattenkontur eine nach innen versetzte — **in der Zone dürfen keine
Eisen liegen.** Für die äusseren Ränder erledigt das der Randabstand der
Stabachsen (`Deckung + ø/2`); stabparallele Kanten (einspringende Ecken
UND Aussparungskanten) sperren ihren Deckungsstreifen zusätzlich: ein
Stab, der hineinfiele, wird auf der (um die Deckung verlängerten)
Ausdehnung der Kante **abgeschnitten**, nicht ganz verworfen. Auch die
Zulagen halten den Abstand: die erste Randzulage liegt mindestens
`Deckung + ø/2` neben der Aussparungskante. Einzige Ausnahme: Eisen
einer Abtreppung, die am längsten Stab der Stufe vermessen sind, dürfen
über die Kante der kürzeren Nachbarn hinauslaufen (bewusst so
abgenommen).

### 6. Öffnungen — Zulagen

Auch hier gibt es **in SIA 262 keine Regel** zur Zulagebewehrung um
Deckenöffnungen; die Norm fordert lediglich, freie Plattenränder mit
aufgebogener Längsbewehrung oder Bügeln zu umschliessen (Ziff. 4.4 /
5.5.3.5). Die im Tool umgesetzten Zulagen (Anzahl, Ø, Abstand, Überstand)
sind daher **konfigurierbarer Bürostandard, nicht normbelegt**. Verbreitete
Praxis: mindestens die gekappte Querschnittsfläche je Richtung zulegen und
die Zulagen um mindestens die Verankerungslänge über die Öffnungsecke
hinausführen; zusätzlich Diagonalstäbe an den Ecken gegen die 45°-Risse.
Beides erzeugt das Tool, beides ist über die Palette einstellbar.

### Bürovorgaben als Defaults

Aus deiner Palette übernommen: **Betondeckung 40 mm**, Mindeststablänge
300 mm, „Als PythonPart erzeugen" aktiv, und die Bewehrungslayer nach
eurem Standard — die IDs stammen aus deiner Deckenplatte-`.pyp`, die
Bezeichnungen decken sich:

| Parameter | Layer | ID |
|---|---|---|
| untere Lage X | RU_P_UNT_1 (Unten 1. Lage) | 7580 |
| untere Lage Y | RU_P_UNT_2 (Unten 2. Lage) | 7586 |
| obere Lage X | RU_P_OBE_4 (Oben 4. Lage) | 7583 |
| obere Lage Y | RU_P_OBE_3 (Oben 3. Lage) | 7582 |
| Randbügel links/rechts | RU_P_UNT_1_BGL | 64265 |
| Randbügel unten/oben | RU_P_UNT_2_BGL | 64264 |

Die **Betongüte** bleibt bewusst auf `-1` — das heisst „aus den
Allplan-Projekteinstellungen übernehmen" und ergibt in deinem Projekt
bereits C25/30. Ein fester Index wäre ohne laufendes Allplan nicht
verlässlich zu bestimmen und würde die Projekteinstellung überstimmen.

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
