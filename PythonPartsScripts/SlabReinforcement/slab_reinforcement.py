"""SlabReinforcement — automatische Flächenbewehrung für Flachdecken.

PythonPart für Allplan 2026 (ScriptObject-Struktur). Erzeugt vier
Bewehrungslagen (oben/unten, jeweils X- und Y-Richtung) als lineare
Stabplatzierungen.

Drei Eingabemodi (Palette "Eingabe"):
    - "Rechteck (Drag)":  parametrische Rechteckplatte, mit der Maus
      abgesetzt, danach über Handles (Länge/Breite/Dicke) ziehbar —
      inkl. Öffnung, Randbügeln, Anschlusseisen (wie v0.2)
    - "Polygon zeichnen": beliebige Kontur zeichnen; weitere gezeichnete
      Polygone werden als Öffnungen interpretiert (Scanline-Verlegung)
    - "Element wählen":   Decke, Boden-/Plattenfundament, Einzel- oder
      Streifenfundament wählen; Kontur (und wo möglich Dicke/Höhenlage)
      werden aus dem Element übernommen

Wechselnde Stababstände: optionale Randverdichtungszonen — im
Rechteckmodus über LinearBarBuilder.calculate_length_of_regions, im
Scanline-Modus über eine äquivalente reine Positionsberechnung.

Aufbau nach den Mustern der offiziellen Beispiele
(NemetschekAllplan/PythonPartsExamples, Branch 2026: BarPlacement,
SlabOpening, ModifySlab, GlobalHandles).

Alle Längenangaben in mm (Allplan-Standardeinheit).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import NemAll_Python_ArchElements as AllplanArchEle
import NemAll_Python_BaseElements as AllplanBaseEle
import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_IFW_ElementAdapter as AllplanEleAdapter
import NemAll_Python_Reinforcement as AllplanReinf
import StdReinfShapeBuilder.GeneralReinfShapeBuilder as GeneralShapeBuilder
import StdReinfShapeBuilder.LinearBarPlacementBuilder as LinearBarBuilder
from BaseScriptObject import BaseScriptObject, BaseScriptObjectData
from BuildingElementListService import BuildingElementListService
from CreateElementResult import CreateElementResult
from HandlePropertiesService import HandlePropertiesService
from PythonPartUtil import PythonPartUtil
from ScriptObjectInteractors.OnCancelFunctionResult import OnCancelFunctionResult
from ScriptObjectInteractors.PointInteractor import PointInteractor, PointInteractorResult
from ScriptObjectInteractors.PolygonInteractor import PolygonInteractor, PolygonInteractorResult
from ScriptObjectInteractors.SingleElementSelectInteractor import (SingleElementSelectInteractor,
                                                                   SingleElementSelectResult)
from StdReinfShapeBuilder.ConcreteCoverProperties import ConcreteCoverProperties
from StdReinfShapeBuilder.ReinforcementShapeProperties import ReinforcementShapeProperties
from StdReinfShapeBuilder.RotationAngles import RotationAngles
from TypeCollections.HandleList import HandleList
from TypeCollections.ModelEleList import ModelEleList
from Utils.HandleCreator import HandleCreator
from Utils.RotationUtil import RotationUtil

def _load_helper_modules():
    """Lädt die drei Nachbarmodule aus demselben Ordner.

    Allplan kann ein Skript auf verschiedene Arten laden (als Paketmodul
    <Ordner>.<Skript>, als Top-Level-Modul oder per exec ohne Paketkontext).
    Deshalb werden nacheinander drei Wege versucht:
        1. relativer Import — wie im offiziellen Beispiel
           ArchitectureExamples/Objects/DoorOpening.py
           ("from .OpeningBase import OpeningBase")
        2. Ordner auf sys.path legen und flach importieren
        3. Direktes Laden über den Dateipfad
    Schlägt alles fehl, wird die ursprüngliche Ursache weitergereicht,
    damit sie im Trace-Fenster sichtbar wird.
    """

    names = ('contour_placement', 'lap_splitting', 'opening_clipping',
             'opening_reinforcement', 'state_persistence', 'lap_planning')

    try:
        from . import (contour_placement, lap_planning,          # noqa: F401
                       lap_splitting, opening_clipping,
                       opening_reinforcement, state_persistence)
        return (contour_placement, lap_splitting, opening_clipping,
                opening_reinforcement, state_persistence, lap_planning)
    except Exception as relative_error:                # noqa: BLE001
        first_error = relative_error

    import importlib
    import importlib.util
    import os
    import sys

    if '__file__' in globals():
        folder = os.path.dirname(os.path.abspath(__file__))
    else:
        # Ohne __file__ (Laden per exec) den Ordner über sys.path suchen
        folder = next((os.path.join(entry, 'SlabReinforcement')
                       for entry in sys.path
                       if os.path.isfile(os.path.join(entry, 'SlabReinforcement',
                                                      'contour_placement.py'))),
                      None)

        if folder is None:
            raise first_error

    if folder not in sys.path:
        sys.path.insert(0, folder)

    try:
        return tuple(importlib.import_module(name) for name in names)
    except Exception:                                  # noqa: BLE001
        pass

    modules = []

    for name in names:
        spec = importlib.util.spec_from_file_location(
            f'SlabReinforcement_{name}', os.path.join(folder, f'{name}.py'))

        if spec is None or spec.loader is None:
            raise first_error

        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        modules.append(module)

    return tuple(modules)


(_contour_placement, _lap_splitting, _opening_clipping,
 _opening_reinforcement, _state_persistence, _lap_planning) = _load_helper_modules()

compute_contour_bars = _contour_placement.compute_contour_bars
decompose_into_zones = _contour_placement.decompose_into_zones
apply_boundary_laps = _contour_placement.apply_boundary_laps
loop_area = _contour_placement.loop_area
loop_bbox = _contour_placement.loop_bbox
split_closed_loops = _contour_placement.split_closed_loops
LONGEST = _contour_placement.LONGEST
SHORTEST = _contour_placement.SHORTEST

split_with_preferred_joints = _lap_splitting.split_with_preferred_joints

compute_edge_bar_runs = _opening_clipping.compute_edge_bar_runs
compute_edge_strip_segments = _opening_clipping.compute_edge_strip_segments
compute_placement_bands = _opening_clipping.compute_placement_bands

opening_edge_bars = _opening_reinforcement.opening_edge_bars
corner_diagonals = _opening_reinforcement.corner_diagonals
clip_bar = _opening_reinforcement.clip_bar
group_equal_bars = _opening_reinforcement.group_equal_bars
outward_normals = _opening_reinforcement.outward_normals
point_in_loop = _opening_reinforcement.point_in_loop

plan_layer_laps = _lap_planning.plan_layer

if TYPE_CHECKING:
    from __BuildingElementStubFiles.SlabReinforcementBuildingElement import \
        SlabReinforcementBuildingElement as BuildingElement  # type: ignore
else:
    from BuildingElement import BuildingElement

SCRIPT_VERSION = '0.7.0'

# Erscheint im Allplan-Trace-Fenster beim Laden — damit im Zweifel erkennbar
# ist, welche Skriptversion Allplan tatsächlich geladen hat
print(f'Load slab_reinforcement.py (Version {SCRIPT_VERSION})')

# Optionen der Seiten-Combos (müssen den ValueList-Einträgen der .pyp entsprechen)
SIDE_STIRRUP = 'Randbügel'
SIDE_CONNECT = 'Anschlusseisen'
SIDE_SEPARATE = 'Separate Anschlusseisen'
SIDE_NONE = 'Keine'

# Optionen des Eingabemodus (ValueList von InputMethod in der .pyp)
INPUT_RECT = 'Rechteck (Drag)'
INPUT_POLYGON = 'Polygon zeichnen'
INPUT_ELEMENT = 'Element wählen'

# Palettenbuttons der Aussparungsseite (EventId in der .pyp)
EVENT_ADD_OPENING = 1001
EVENT_REMOVE_LAST_OPENING = 1002
EVENT_CLEAR_OPENINGS = 1003

# Eingabestadium "Aussparung zeichnen"
OPENING_STAGE = 1


def check_allplan_version(_build_ele: BuildingElement,
                          _version: str) -> bool:
    """Prüfung der Allplan-Version — entwickelt für Allplan >= 2026."""

    return True


def create_script_object(build_ele: BuildingElement,
                         script_object_data: BaseScriptObjectData) -> BaseScriptObject:
    """Erzeugt das ScriptObject."""

    print(f'SlabReinforcement {SCRIPT_VERSION}: create_script_object')

    return SlabReinforcementScript(build_ele, script_object_data)


@dataclass
class LayerConfig:
    """Konfiguration einer Bewehrungslage."""

    name: str            # sprechender Name, nur für Log/Fehlersuche
    direction: str       # "X" oder "Y" — Richtung, in der die Stäbe verlaufen
    is_top: bool         # obere (True) oder untere (False) Lage
    diameter: float      # Stabdurchmesser [mm]
    spacing: float       # Stababstand [mm]
    steel_grade: int     # Index der Stahlgüte (Allplan-Tabelle)
    z_axis: float = 0.0  # Höhe der Stabachse über Plattenunterkante [mm]
    bending_roller: float = 4.0
    allplan_layer: int = 0  # Allplan-Layer-ID; 0 = aktueller Layer

    placements: list = field(default_factory=list)


class SlabReinforcementScript(BaseScriptObject):
    """ScriptObject: steuert die Eingabe (Punkt/Polygon/Element­auswahl)
    und delegiert die Element-Erzeugung an SlabReinforcement.
    """

    def __init__(self,
                 build_ele: BuildingElement,
                 script_object_data: BaseScriptObjectData):
        super().__init__(script_object_data)

        self.build_ele = build_ele

        self.point_result = PointInteractorResult()
        self.polygon_result = PolygonInteractorResult()
        self.opening_result = PolygonInteractorResult()
        self.sel_result = SingleElementSelectResult()

        # 0 = Kontur/Absetzpunkt, OPENING_STAGE = Aussparungen zeichnen
        self.input_stage = 0

        self.placement_pnt = AllplanGeo.Point3D()
        self.contour: list[tuple[float, float]] | None = None

        # Aussparungen aus zwei Quellen, getrennt gehalten: die automatisch
        # erkannten werden bei jeder Neueingabe neu ermittelt, die
        # gezeichneten sammeln sich über den Button an
        self.detected_openings: list[list[tuple[float, float]]] = []
        self.drawn_openings: list[list[tuple[float, float]]] = []
        self.z_offset = 0.0
        self.thickness_override: float | None = None

        # Solange False, liefert execute() ein leeres Ergebnis — sonst würde
        # während der Eingabe bereits eine Platte am Nullpunkt erscheinen
        self.input_finished = False

        # Ein abgesetztes PythonPart wird zum Bearbeiten mit einem frischen
        # ScriptObject geoeffnet: die Palettenwerte stellt Allplan wieder her,
        # die eingegebene Geometrie nicht. Ohne sie bliebe execute() leer und
        # das Element waere nicht mehr bearbeitbar.
        if build_ele.InputMode.value == build_ele.INPUT_MODE_CREATION:
            self._restore_state()


    def start_input(self):
        """Ersteingabe je nach gewähltem Eingabemodus starten."""

        build_ele = self.build_ele

        build_ele.InputMode.value = build_ele.INPUT_MODE_INPUT

        # Ergebnisse einer vorherigen Eingabe verwerfen (Moduswechsel)
        self.input_finished = False
        self.input_stage = 0
        self.contour = None
        self.detected_openings = []
        self.drawn_openings = []
        self.z_offset = 0.0
        self.thickness_override = None
        self.placement_pnt = AllplanGeo.Point3D()

        input_method = build_ele.InputMethod.value

        print(f'SlabReinforcement: start_input, Modus "{input_method}"')

        if input_method == INPUT_ELEMENT:
            self.script_object_interactor = SingleElementSelectInteractor(
                self.sel_result,
                [AllplanEleAdapter.Slab_TypeUUID,
                 AllplanEleAdapter.SlabFoundationTier_TypeUUID,
                 AllplanEleAdapter.IndividualFoundation_TypeUUID,
                 AllplanEleAdapter.StripFoundation_TypeUUID],
                'Decke oder Fundament wählen')

        elif input_method == INPUT_POLYGON:
            self.script_object_interactor = PolygonInteractor(
                self.polygon_result,
                z_coord_input=False,
                multi_polygon_input=True)

        else:
            self.script_object_interactor = PointInteractor(
                self.point_result, True,
                'Absetzpunkt der Platte', self.draw_placement_preview)


    def start_next_input(self):
        """Eingabeergebnis übernehmen und in den Erzeugungsmodus wechseln."""

        build_ele = self.build_ele

        if build_ele.InputMode.value != build_ele.INPUT_MODE_INPUT:
            return

        if self.input_stage == OPENING_STAGE:
            self._process_drawn_openings()
            self._finish_input()
            return

        input_method = build_ele.InputMethod.value

        if input_method == INPUT_ELEMENT:
            self._process_selected_element()
        elif input_method == INPUT_POLYGON:
            self._process_drawn_polygons()
        else:
            self.placement_pnt = self.point_result.input_point

        self._finish_input()


    @property
    def openings(self) -> list[list[tuple[float, float]]]:
        """Alle Aussparungen: automatisch erkannte plus gezeichnete."""

        detected = self.detected_openings \
            if self.build_ele.DetectOpenings.value else []

        return list(detected) + list(self.drawn_openings)


    def _finish_input(self):
        """Eingabe abschliessen und in den Erzeugungsmodus wechseln."""

        self.build_ele.InputMode.value = self.build_ele.INPUT_MODE_CREATION

        self.input_stage = 0
        self.script_object_interactor = None
        self.input_finished = True

        self._save_state()

        print(f'SlabReinforcement: Eingabe abgeschlossen — '
              f'Kontur: {"ja" if self.contour else "nein (Rechteck)"}, '
              f'Aussparungen: {len(self.openings)} '
              f'({len(self.detected_openings)} erkannt, '
              f'{len(self.drawn_openings)} gezeichnet)')


    # ============ Zustand eines abgesetzten PythonParts ============

    def _save_state(self):
        """Eingegebene Geometrie in einen versteckten Palettenparameter legen.

        Die Palettenwerte stellt Allplan beim Bearbeiten selbst wieder her,
        die per Interactor eingegebene Geometrie dagegen nicht — die lebt
        nur im ScriptObject und waere nach dem Verlassen verloren.
        """

        try:
            self.build_ele.GeometryState.value = _state_persistence.encode_state(
                (self.placement_pnt.X, self.placement_pnt.Y, self.placement_pnt.Z),
                self.contour,
                self.detected_openings,
                self.drawn_openings,
                self.z_offset,
                self.thickness_override)
        except (TypeError, ValueError) as exc:
            print(f'SlabReinforcement: Geometrie konnte nicht gesichert werden ({exc}) — '
                  f'das Element waere nach dem Verlassen nicht mehr bearbeitbar')


    def _restore_state(self) -> bool:
        """Gegenstueck zu _save_state; True, wenn etwas geladen wurde."""

        state = _state_persistence.decode_state(self.build_ele.GeometryState.value)

        if state is None:
            print('SlabReinforcement: kein brauchbarer Geometriestand gespeichert — '
                  'das Element stammt aus einer aelteren Fassung und muss neu '
                  'abgesetzt werden')
            return False

        pnt = state['placement_pnt']
        self.placement_pnt = AllplanGeo.Point3D(pnt[0], pnt[1], pnt[2])

        self.contour = state['contour']
        self.detected_openings = state['detected_openings']
        self.drawn_openings = state['drawn_openings']
        self.z_offset = state['z_offset']
        self.thickness_override = state['thickness_override']

        self.input_finished = True

        print(f'SlabReinforcement: Geometriestand geladen — '
              f'Kontur: {"ja" if self.contour else "nein (Rechteck)"}, '
              f'Aussparungen: {len(self.detected_openings)} erkannt, '
              f'{len(self.drawn_openings)} gezeichnet')

        return True


    def on_control_event(self, event_id: int) -> bool:
        """Palettenbuttons der Aussparungsseite.

        Aussparungen sind keine Voreinstellung, sondern werden nach und
        nach hinzugefügt: "Aussparung zeichnen" startet jederzeit eine
        weitere Eingaberunde und hängt das Ergebnis an die Liste an. Die
        bereits erzeugte Bewehrung bleibt währenddessen sichtbar.

        Rückgabe True = Palette neu aufbauen (Vertrag ab 2025).
        """

        if event_id == EVENT_ADD_OPENING:
            self._start_opening_input()
            return True

        if event_id == EVENT_REMOVE_LAST_OPENING:
            if self.drawn_openings:
                self.drawn_openings.pop()
                self._save_state()
                print(f'SlabReinforcement: letzte gezeichnete Aussparung '
                      f'entfernt ({len(self.drawn_openings)} verbleiben)')
            else:
                print('SlabReinforcement: keine gezeichnete Aussparung vorhanden')

            return True

        if event_id == EVENT_CLEAR_OPENINGS:
            print(f'SlabReinforcement: {len(self.drawn_openings)} gezeichnete '
                  f'Aussparung(en) entfernt')
            self.drawn_openings = []
            self._save_state()

            return True

        return False


    def _start_opening_input(self):
        """Weitere Eingaberunde: beliebig viele Aussparungspolygone
        zeichnen, ESC beendet die Runde.
        """

        if not self.input_finished:
            print('SlabReinforcement: zuerst die Plattenkontur eingeben')
            return

        self.input_stage = OPENING_STAGE
        self.opening_result = PolygonInteractorResult()

        # InputMode zurück auf INPUT, damit start_next_input das Ergebnis
        # abholt; input_finished bleibt True, damit die bereits erzeugte
        # Bewehrung während des Zeichnens sichtbar bleibt
        self.build_ele.InputMode.value = self.build_ele.INPUT_MODE_INPUT

        self.script_object_interactor = PolygonInteractor(
            self.opening_result,
            z_coord_input=False,
            multi_polygon_input=True)

        self.script_object_interactor.start_input(self.coord_input)

        print('SlabReinforcement: Aussparung(en) zeichnen — ESC beendet die Eingabe')


    def _process_drawn_openings(self):
        """Die gezeichneten Polygone an die Aussparungsliste anhängen."""

        loops = self._loops_from_polygon_result(self.opening_result)

        # Im Rechteckmodus liegt die Platte im lokalen System des
        # Absetzpunkts — die gezeichneten Polygone kommen global herein
        if self.build_ele.InputMethod.value == INPUT_RECT:
            origin = self.placement_pnt
            loops = [[(x - origin.X, y - origin.Y) for x, y in loop]
                     for loop in loops]

        self.drawn_openings += loops

        print(f'SlabReinforcement: {len(loops)} Aussparung(en) hinzugefügt '
              f'({len(self.drawn_openings)} gezeichnete insgesamt)')


    def execute(self) -> CreateElementResult:
        """Elemente erzeugen (wird auch bei Parameteränderung erneut gerufen).

        Vor abgeschlossener Eingabe bleibt das Ergebnis leer: Im Polygon-
        und Elementmodus gibt es dann noch keine Kontur, im Rechteckmodus
        noch keinen Absetzpunkt — sonst würde Allplan eine Platte in
        Default-Größe am Nullpunkt zeichnen.
        """

        if not self.input_finished:
            return CreateElementResult()

        engine = SlabReinforcement(self.build_ele, self.document,
                                   contour=self.contour,
                                   openings=self.openings,
                                   origin=self.placement_pnt,
                                   z_offset=self.z_offset,
                                   thickness_override=self.thickness_override)

        return engine.create()


    def draw_placement_preview(self):
        """Vorschau im Rechteckmodus: Plattenkörper folgt dem Fadenkreuz."""

        build_ele = self.build_ele

        preview_list = ModelEleList(build_ele.CommonProp.value)
        preview_list.append_geometry_3d(
            AllplanGeo.Polyhedron3D.CreateCuboid(
                AllplanGeo.AxisPlacement3D(self.point_result.input_point),
                build_ele.SlabLength.value,
                build_ele.SlabWidth.value,
                build_ele.SlabThickness.value))

        AllplanBaseEle.DrawElementPreview(self.document, AllplanGeo.Matrix3D(),
                                          preview_list, False, None)


    def move_handle(self,
                    handle_prop,
                    input_pnt: AllplanGeo.Point3D):
        """Handle-Verschiebung (nur Rechteckmodus): Parameterwert übernehmen."""

        HandlePropertiesService.update_property_value(self.build_ele, handle_prop, input_pnt)


    def on_cancel_function(self) -> OnCancelFunctionResult:
        """ESC-Behandlung: während einer laufenden Eingabe entscheidet der
        Interactor (bei der Mehrfach-Polygon-Eingabe schließt ESC die Eingabe
        ab, statt sie zu verwerfen); danach werden die Elemente erzeugt.
        """

        BuildingElementListService.write_to_default_favorite_file([self.build_ele])

        if self.script_object_interactor is not None:
            return self.script_object_interactor.on_cancel_function()

        return OnCancelFunctionResult.CREATE_ELEMENTS


    def modify_element_property(self,
                                name: str,
                                _value: Any) -> bool:
        """Palettenänderungen: Wechsel des Eingabemodus startet die Eingabe
        neu — auch nach bereits abgeschlossener Eingabe.
        """

        if name == 'InputMethod':
            self.start_input()

            if self.script_object_interactor is not None:
                self.script_object_interactor.start_input(self.coord_input)

        return False


    def _loops_from_polygon_result(self, result) -> list[list[tuple[float, float]]]:
        """Geschlossene Loops aus einem PolygonInteractor-Ergebnis."""

        input_polygon = result.input_polygon

        polygons = input_polygon if isinstance(input_polygon, list) else [input_polygon]

        points: list[tuple[float, float]] = []

        for polygon in polygons:
            if polygon is None:
                continue

            converted = AllplanGeo.ConvertTo2D(polygon)
            polygon_2d = converted[1] if isinstance(converted, tuple) else converted

            points += [(p.X, p.Y) for p in polygon_2d.Points]

        return split_closed_loops(points)


    def _process_drawn_polygons(self):
        """Gezeichnete Polygone übernehmen: größte Fläche = Kontur,
        alle weiteren Loops = Aussparungen.
        """

        self._set_contour_from_loops(self._loops_from_polygon_result(self.polygon_result))


    def _process_selected_element(self):
        """Kontur, Dicke und Höhenlage aus dem gewählten Element übernehmen."""

        sel_element = self.sel_result.sel_element

        if sel_element is None or (hasattr(sel_element, 'IsNull') and sel_element.IsNull()):
            return

        element = AllplanBaseEle.GetElement(sel_element)

        geometry = element.GetGeometryObject()

        # Streifenfundament zuerst prüfen: seine Geometrie ist die Achse —
        # eine Polylinien-Achse hätte ebenfalls 'Points' und würde sonst
        # fälschlich als (entartete) Kontur interpretiert
        if isinstance(element, AllplanArchEle.StripFoundationElement):
            self._set_contour_from_axis(element, geometry)

        elif hasattr(geometry, 'Points'):
            points = [(p.X, p.Y) for p in geometry.Points]
            self._set_contour_from_loops(split_closed_loops(points))

            # Aussparungen sind in Allplan eigene Kindelemente der Decke —
            # sie stecken nicht in deren Konturpolygon und müssen deshalb
            # zusätzlich gelesen werden. Ohne sie anzutippen.
            self.detected_openings += self._child_openings(sel_element)

        else:
            print('SlabReinforcement: Geometrie des gewählten Elements wird '
                  'nicht unterstützt — Rechteck aus der Palette wird verwendet')

        self._read_element_thickness_and_level(element)


    def _set_contour_from_loops(self, loops: list[list[tuple[float, float]]]):
        """Größter Loop wird Kontur, die übrigen Öffnungen."""

        if not loops:
            print('SlabReinforcement: keine geschlossene Kontur erkannt')
            return

        loops = sorted(loops, key=lambda loop: abs(loop_area(loop)), reverse=True)

        self.contour = loops[0]
        self.detected_openings = self._filter_openings(loops[1:])


    def _child_openings(self, sel_element) -> list[list[tuple[float, float]]]:
        """Aussparungen der gewählten Decke aus deren Kindelementen lesen.

        In Allplan ist eine Aussparung ein eigenes Element unterhalb der
        Decke, nicht Teil ihres Konturpolygons. Über
        `BaseElementAdapterChildElementsService.GetChildModelElements`
        (2026-API-Referenz) sind sie erreichbar, ohne dass der Anwender sie
        einzeln antippen muss.

        Gefiltert wird **nicht** über eine Typ-UUID: welche Konstante die
        Aussparung bezeichnet, liess sich in der Doku nicht belegen. Statt
        zu raten, wird jedes Kindelement genommen, aus dem sich eine
        geschlossene Kontur lesen lässt, die vollständig innerhalb der
        Plattenkontur liegt und kleiner ist als diese — das trifft auf
        Aussparungen zu und auf sonst kaum ein Kindelement.
        """

        if not self.build_ele.DetectOpenings.value or self.contour is None:
            return []

        service = getattr(AllplanEleAdapter,
                          'BaseElementAdapterChildElementsService', None)

        if service is None or not hasattr(service, 'GetChildModelElements'):
            print('SlabReinforcement: BaseElementAdapterChildElementsService '
                  'nicht verfügbar — Aussparungselemente werden nicht gelesen')
            return []

        try:
            children = service.GetChildModelElements(sel_element)
        except Exception as error:                     # noqa: BLE001
            print(f'SlabReinforcement: Kindelemente nicht lesbar ({error})')
            return []

        loops: list[list[tuple[float, float]]] = []

        for child in children:
            loops += self._loops_from_element(child)

        inside = [loop for loop in loops if self._loop_is_inside_contour(loop)]

        print(f'SlabReinforcement: {len(inside)} Aussparungselement(e) erkannt')

        return self._filter_openings(inside)


    def _loops_from_element(self, element) -> list[list[tuple[float, float]]]:
        """Geschlossene Grundriss-Loops eines Elements, so defensiv wie
        möglich: Polygon-/Polylinien-Geometrie über `Points`, Körper über
        ihre Eckpunkte (konvexe Hülle wäre falsch, deshalb nur `Points`).
        """

        try:
            geometry = AllplanBaseEle.GetElement(element).GetGeometryObject()
        except Exception:                              # noqa: BLE001
            return []

        if geometry is None or not hasattr(geometry, 'Points'):
            return []

        try:
            points = [(p.X, p.Y) for p in geometry.Points]
        except Exception:                              # noqa: BLE001
            return []

        return [loop for loop in split_closed_loops(points) if len(loop) >= 3]


    def _loop_is_inside_contour(self, loop: list[tuple[float, float]]) -> bool:
        """Liegt der Loop vollständig in der Plattenkontur und ist er
        kleiner als sie? (Die Kontur selbst darf nicht als Aussparung
        durchgehen.)
        """

        if abs(loop_area(loop)) >= abs(loop_area(self.contour)) * 0.999:
            return False

        return all(point_in_loop(point, self.contour) for point in loop)


    def _filter_openings(self,
                         loops: list[list[tuple[float, float]]]
                         ) -> list[list[tuple[float, float]]]:
        """Automatisch erkannte Innenkonturen als Aussparungen übernehmen.

        Nur wenn die Palette das vorsieht, und nur ab der eingestellten
        Mindestgrösse — winzige Innenkonturen sind meist Zeichnungsartefakte
        (Rundungen, doppelte Punkte) und keine echten Aussparungen.
        """

        if not self.build_ele.DetectOpenings.value:
            return []

        minimum = self.build_ele.MinOpeningSize.value

        kept = []

        for loop in loops:
            xs = [p[0] for p in loop]
            ys = [p[1] for p in loop]

            if min(max(xs) - min(xs), max(ys) - min(ys)) < minimum:
                continue

            kept.append(loop)

        if len(kept) < len(loops):
            print(f'SlabReinforcement: {len(loops) - len(kept)} Innenkontur(en) '
                  f'kleiner als {minimum} mm ignoriert')

        return kept


    def _set_contour_from_axis(self, element, axis):
        """Rechteckkontur um eine gerade Streifenfundament-Achse."""

        try:
            width = element.Properties.Width
        except AttributeError:
            width = 0.0

        if width <= 0:
            print('SlabReinforcement: Breite des Streifenfundaments nicht '
                  'lesbar — Element wird nicht übernommen')
            return

        # Polylinien-/Kurvenachsen (mehrteilig, erkennbar an 'Points') werden
        # noch nicht unterstützt — nur die gerade Linie mit Start-/Endpunkt
        if hasattr(axis, 'Points') or \
                not (hasattr(axis, 'StartPoint') and hasattr(axis, 'EndPoint')):
            print('SlabReinforcement: nur gerade Streifenfundament-Achsen '
                  'werden unterstützt (Polylinien-Achse: Roadmap v0.4)')
            return

        x1, y1 = axis.StartPoint.X, axis.StartPoint.Y
        x2, y2 = axis.EndPoint.X, axis.EndPoint.Y

        length = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5

        if length <= 0:
            return

        # Normale auf die Achse, halbe Breite in beide Richtungen
        nx, ny = -(y2 - y1) / length * width / 2.0, (x2 - x1) / length * width / 2.0

        self.contour = [(x1 + nx, y1 + ny), (x2 + nx, y2 + ny),
                        (x2 - nx, y2 - ny), (x1 - nx, y1 - ny)]
        self.detected_openings = []


    def _read_element_thickness_and_level(self, element):
        """Dicke und Unterkanten-Höhe defensiv aus dem Element lesen —
        was nicht lesbar ist, bleibt beim Palettenwert bzw. z=0.
        """

        try:
            properties = element.Properties
        except AttributeError:
            return

        if hasattr(properties, 'TierCount'):
            self.thickness_override = sum(
                properties.GetSlabTierProperties(i).Thickness
                for i in range(properties.TierCount))
        elif hasattr(properties, 'Height'):
            self.thickness_override = properties.Height

        if self.thickness_override:
            self.build_ele.SlabThickness.value = self.thickness_override
        else:
            print('SlabReinforcement: Dicke nicht aus dem Element lesbar — '
                  'Palettenwert wird verwendet')

        try:
            self.z_offset = properties.PlaneReferences.GetAbsBottomElevation()
        except AttributeError:
            print('SlabReinforcement: Höhenlage nicht aus dem Element lesbar — '
                  'Bewehrung wird auf z=0 aufgebaut')


class SlabReinforcement():
    """Erzeugt die Deckenbewehrung aus den Palettenparametern.

    Zwei Pfade:
        - Rechteckmodus (contour is None): Band-Logik mit Öffnung aus der
          Palette, Randbügeln/Anschlusseisen und Handles
        - Konturmodus: Scanline-Verlegung über eine beliebige polygonale
          Kontur mit beliebig vielen Öffnungen
    """

    def __init__(self,
                 build_ele: BuildingElement,
                 doc: AllplanEleAdapter.DocumentAdapter,
                 contour: list[tuple[float, float]] | None = None,
                 openings: list[list[tuple[float, float]]] | None = None,
                 origin: AllplanGeo.Point3D = AllplanGeo.Point3D(),
                 z_offset: float = 0.0,
                 thickness_override: float | None = None):
        self.build_ele = build_ele
        self.document = doc

        self.contour = contour
        self.contour_openings = openings or []
        self.origin = origin
        self.base_z = origin.Z + z_offset

        self.length = build_ele.SlabLength.value
        self.width = build_ele.SlabWidth.value
        self.thickness = thickness_override or build_ele.SlabThickness.value

        # Betondeckung: entweder ein Wert für alles oder getrennt nach
        # unten (UK Decke bis Aussenkante 1. Lage), oben (OK Decke bis
        # Aussenkante 4. Lage) und seitlich (Stabenden)
        if build_ele.CoverMode.value == 'Getrennt':
            self.cover_bottom = build_ele.CoverBottom.value
            self.cover_top = build_ele.CoverTop.value
            self.cover_side = build_ele.CoverSide.value
        else:
            self.cover_bottom = self.cover_top = self.cover_side = \
                build_ele.ConcreteCover.value

        # Seitliche Deckung wirkt auf die Stabenden und Verlegeränder
        self.concrete_cover = self.cover_side

        self.stirrup_style = build_ele.StirrupStyle.value
        self.opening_stirrup_style = build_ele.OpeningStirrupStyle.value
        self.concrete_grade = build_ele.ConcreteGrade.value

        # Seitenausbildung und Stoßlänge (als Vielfaches des Stabdurchmessers)
        self.overlap_factor = build_ele.OverlapFactor.value
        self.side_left = build_ele.SideLeft.value
        self.side_right = build_ele.SideRight.value
        self.side_bottom = build_ele.SideBottom.value
        self.side_top = build_ele.SideTop.value

        # Randverdichtung (wechselnde Stababstände)
        self.edge_zones_active = build_ele.EdgeZonesActive.value
        self.edge_zone_length = build_ele.EdgeZoneLength.value
        self.edge_zone_spacing = build_ele.EdgeZoneSpacing.value

        # Abtreppung an schrägen Rändern
        self.step_max_loss = build_ele.StepMaxLoss.value
        self.step_length_raster = build_ele.StepLengthRaster.value

        # Passeisen-Grenze: ab dieser Länge enthält jedes Eisen mindestens
        # einen Stoss (Bürosystematik, bestätigt am Studienblatt)
        self.pass_bar_threshold = build_ele.PassBarThreshold.value

        # Mindestlänge eines Abtreppungsstücks: unterschreitet das kürzeste
        # Stufenstück diesen Wert, rutscht die ganze Stosslinie nach innen
        self.step_min_piece = build_ele.StepMinPieceLength.value

        self.max_edge_setback = build_ele.MaxEdgeSetback.value

        # Variante A: Rechteckgrenzen fluchten über die Bänder hinweg,
        # Variante B: das Rechteck endet erst am Beginn der Schräge
        self.snap_rect_to_contour = build_ele.RectBoundary.value == 'An Konturkanten'

        # Stösse
        self.max_bar_length = build_ele.MaxBarLength.value
        self._lap_warning_shown = False
        self.lap_opening_margin = build_ele.LapOpeningMargin.value

        self.position_counter = 0

        self.layers = self._create_layer_configs()

        # ---------- Aussparungen ----------
        # Rechteckmodus mit Zahlen-Eingabe: eine achsparallele Öffnung, die
        # über die Bandlogik läuft (schnellster Weg für den Standardfall)
        self.has_opening = (build_ele.RectOpeningActive.value
                            and self.contour is None
                            and not self.contour_openings)
        self.opening_x = (build_ele.OpeningX.value,
                          build_ele.OpeningX.value + build_ele.OpeningWidth.value)
        self.opening_y = (build_ele.OpeningY.value,
                          build_ele.OpeningY.value + build_ele.OpeningHeight.value)

        if self.has_opening and (build_ele.OpeningWidth.value <= 0 or build_ele.OpeningHeight.value <= 0):
            print('SlabReinforcement: Aussparung mit Breite/Höhe <= 0 wird ignoriert')
            self.has_opening = False

        # Polygonale Aussparungen im Rechteckmodus: die Bandlogik kennt nur
        # achsparallele Rechtecke, deshalb wird die Rechteckplatte hier zur
        # Kontur und läuft über den (allgemeinen) Scanline-Pfad
        if self.contour is None and self.contour_openings:
            self.contour = [(0.0, 0.0), (self.length, 0.0),
                            (self.length, self.width), (0.0, self.width)]
            print('SlabReinforcement: polygonale Aussparung im Rechteckmodus — '
                  'die Platte wird als Kontur verlegt')

        if build_ele.RectOpeningActive.value and not self.has_opening:
            # Überall sonst wird das Zahlen-Rechteck als gewöhnliches
            # Aussparungspolygon behandelt und einfach mit angehängt
            x_from, x_to = self.opening_x
            y_from, y_to = self.opening_y

            if x_to > x_from and y_to > y_from:
                self.contour_openings = list(self.contour_openings) + \
                    [[(x_from, y_from), (x_to, y_from),
                      (x_to, y_to), (x_from, y_to)]]


    def _pnt(self, x: float, y: float, z: float = 0.0) -> AllplanGeo.Point3D:
        """Punkt im Plattensystem -> globales System (Rechteckmodus:
        Absetzpunkt-Offset; Konturmodus: nur Höhenlage).
        """

        if self.contour is None:
            return AllplanGeo.Point3D(x + self.origin.X, y + self.origin.Y, z + self.base_z)

        return AllplanGeo.Point3D(x, y, z + self.base_z)


    def _next_position(self) -> int:
        """Nächste freie Positionsnummer (Markennummer)."""

        self.position_counter += 1
        return self.position_counter


    def _create_layer_configs(self) -> list[LayerConfig]:
        """Liest die vier Lagen aus der Palette und berechnet ihre Höhenlage.

        Welche Richtung außen liegt (direkt auf bzw. unter der Deckung),
        bestimmt der Palettenparameter "Äußere Lagen"; die jeweils andere
        Richtung liegt innen. Bei aktivem "Alle Lagen gleich" überschreiben
        DiaAll/SpacingAll die Einzelwerte aller vier Lagen.
        """

        build_ele = self.build_ele

        bottom_x = LayerConfig('Bewehrung unten X', 'X', False,
                               build_ele.BottomXDiameter.value,
                               build_ele.BottomXSpacing.value,
                               build_ele.BottomXSteelGrade.value)
        bottom_y = LayerConfig('Bewehrung unten Y', 'Y', False,
                               build_ele.BottomYDiameter.value,
                               build_ele.BottomYSpacing.value,
                               build_ele.BottomYSteelGrade.value)
        top_x = LayerConfig('Bewehrung oben X', 'X', True,
                            build_ele.TopXDiameter.value,
                            build_ele.TopXSpacing.value,
                            build_ele.TopXSteelGrade.value)
        top_y = LayerConfig('Bewehrung oben Y', 'Y', True,
                            build_ele.TopYDiameter.value,
                            build_ele.TopYSpacing.value,
                            build_ele.TopYSteelGrade.value)

        if build_ele.SameDiameterForAll.value:
            for layer in (bottom_x, bottom_y, top_x, top_y):
                layer.diameter = float(build_ele.DiaAll.value)
                layer.spacing = build_ele.SpacingAll.value

        bottom_x.allplan_layer = build_ele.LayerBottomX.value
        bottom_y.allplan_layer = build_ele.LayerBottomY.value
        top_x.allplan_layer = build_ele.LayerTopX.value
        top_y.allplan_layer = build_ele.LayerTopY.value

        # Höhenlage der Stabachsen über Plattenunterkante — Formeln aus dem
        # Deckenplatte-PythonPart des Anwenders (z1..z4): die äußere Richtung
        # liegt direkt auf bzw. unter der Betondeckung, die innere darüber
        # bzw. darunter. Eine einzige Betondeckung gilt für alle Lagen und
        # für die Stabenden (Seitendeckung).
        # Auf den Anfangsbuchstaben pruefen statt auf den vollen Text: sonst
        # landet jede geaenderte Beschriftung stillschweigend im Else-Zweig,
        # und der Umschalter wirkt scheinbar gar nicht
        outer_direction = 'X' if str(build_ele.OuterLayerDirection.value).strip().upper().startswith('X') \
            else 'Y'

        # Im Trace-Fenster nachvollziehbar, welche Richtung tatsaechlich
        # aussen liegt — der Hoehenunterschied betraegt nur einen
        # Stabdurchmesser und ist in der Draufsicht nicht zu sehen
        print(f'SlabReinforcement: äußere Lagen in {outer_direction}-Richtung '
              f'(Palettenwert "{build_ele.OuterLayerDirection.value}")')

        if outer_direction == 'X':
            bottom_outer, bottom_inner = bottom_x, bottom_y
            top_outer, top_inner = top_x, top_y
        else:
            bottom_outer, bottom_inner = bottom_y, bottom_x
            top_outer, top_inner = top_y, top_x

        # unten: Deckung bis Aussenkante der 1. Lage, die 2. Lage liegt
        # darüber; oben spiegelbildlich ab Aussenkante der 4. Lage
        bottom_outer.z_axis = self.cover_bottom + bottom_outer.diameter / 2.0
        bottom_inner.z_axis = self.cover_bottom + bottom_outer.diameter + \
            bottom_inner.diameter / 2.0
        top_outer.z_axis = self.thickness - self.cover_top - top_outer.diameter / 2.0
        top_inner.z_axis = self.thickness - self.cover_top - top_outer.diameter - \
            top_inner.diameter / 2.0

        layers = [bottom_outer, bottom_inner, top_inner, top_outer]

        # Plausibilität: bei dünner Platte und großen Durchmessern können
        # sich obere und untere Lagen durchdringen — betroffene obere Lagen
        # entfallen dann mit Warnung, statt falsche Bewehrung zu erzeugen
        bottom_layer_top = bottom_inner.z_axis + bottom_inner.diameter / 2.0

        valid_layers = []

        for layer in layers:
            if layer.z_axis <= 0 or \
                    (layer.is_top and layer.z_axis - layer.diameter / 2.0 < bottom_layer_top):
                print(f'SlabReinforcement: Lage "{layer.name}" entfällt — '
                      f'Plattendicke {self.thickness} zu gering für die '
                      f'gewählten Deckungen/Durchmesser')
                continue

            valid_layers.append(layer)

        # Biegerollendurchmesser normabhängig aus Allplan ermitteln (kein Bügel)
        for layer in valid_layers:
            layer.bending_roller = AllplanReinf.BendingRollerService.GetBendingRollerFactor(
                layer.diameter, layer.steel_grade, -1, False)

        return valid_layers


    # ==================== Erzeugung ====================

    def create(self) -> CreateElementResult:
        """Erzeugt Ansichtsgeometrie und alle Placements."""

        model_ele_list = ModelEleList(self.build_ele.CommonProp.value)
        for geometry in self._create_view_geometry():
            model_ele_list.append_geometry_3d(geometry)

        reinf_ele_list = ModelEleList()

        if self.contour is None:
            for layer in self.layers:
                for placement in self._create_layer_placements(layer):
                    reinf_ele_list.append(placement)

            if self.has_opening and self.build_ele.EdgeReinfActive.value:
                for placement in self._create_opening_edge_reinforcement():
                    reinf_ele_list.append(placement)

            for placement in self._create_separate_connection_bars():
                reinf_ele_list.append(placement)

            for placement in self._create_edge_stirrups():
                reinf_ele_list.append(placement)

            handle_list = self._create_handles()
        else:
            for placement in self._create_contour_edge_reinforcement():
                reinf_ele_list.append(placement)

            for layer in self.layers:
                for placement in self._create_contour_layer_placements(layer):
                    reinf_ele_list.append(placement)

            for placement in self._create_opening_reinforcement():
                reinf_ele_list.append(placement)

            handle_list = HandleList()

        # Alle Elemente sind bereits im globalen Koordinatensystem aufgebaut
        # (Rechteckmodus über den Absetzpunkt, Kontur-/Elementmodus über die
        # Originalkoordinaten). placement_point = Nullpunkt setzt sie direkt
        # ab, statt sie noch einmal an den Mauszeiger zu binden — wie im
        # offiziellen Beispiel Slab.py.
        placement_point = AllplanGeo.Point3D()

        if self.build_ele.IsPythonPart.value:
            pyp_util = PythonPartUtil()
            pyp_util.add_pythonpart_view_2d3d(model_ele_list)
            pyp_util.add_reinforcement_elements(reinf_ele_list)

            return CreateElementResult(pyp_util.create_pythonpart(self.build_ele),
                                       handle_list,
                                       placement_point=placement_point)

        return CreateElementResult(elements=model_ele_list + reinf_ele_list,
                                   handles=handle_list,
                                   placement_point=placement_point)


    def _create_view_geometry(self) -> list:
        """Ansichtsgeometrie: Rechteckmodus ein Plattenkörper (Aussparung
        wird, wenn möglich, boolesch abgezogen); Konturmodus die Kontur- und
        Aussparungspolygone auf Höhe der Plattenunterkante.
        """

        if self.contour is None:
            slab = AllplanGeo.Polyhedron3D.CreateCuboid(
                AllplanGeo.AxisPlacement3D(self._pnt(0, 0)),
                self.length, self.width, self.thickness)

            if not self.has_opening:
                return [slab]

            opening = AllplanGeo.Polyhedron3D.CreateCuboid(
                AllplanGeo.AxisPlacement3D(self._pnt(self.opening_x[0], self.opening_y[0], -1.0)),
                self.opening_x[1] - self.opening_x[0],
                self.opening_y[1] - self.opening_y[0],
                self.thickness + 2.0)

            err, slab_with_opening = AllplanGeo.MakeSubtraction(slab, opening)

            if err != AllplanGeo.eGeometryErrorCode.eOK or slab_with_opening is None:
                return [slab]

            return [slab_with_opening]

        polygons = []

        for loop in [self.contour] + list(self.contour_openings):
            polygon = AllplanGeo.Polygon3D()

            for x, y in loop:
                polygon += AllplanGeo.Point3D(x, y, self.base_z)

            polygon += AllplanGeo.Point3D(loop[0][0], loop[0][1], self.base_z)

            polygons.append(polygon)

        return polygons


    def _create_handles(self) -> HandleList:
        """Zug-Handles für Länge, Breite und Dicke (nur Rechteckmodus)."""

        handle_list = HandleList()
        origin = self._pnt(0, 0)

        HandleCreator.point_distance(handle_list, 'SlabLength',
                                     self._pnt(self.length, 0), origin,
                                     True, False, info_text='Länge (X)')
        HandleCreator.point_distance(handle_list, 'SlabWidth',
                                     self._pnt(0, self.width), origin,
                                     True, False, info_text='Breite (Y)')
        HandleCreator.point_distance(handle_list, 'SlabThickness',
                                     self._pnt(0, 0, self.thickness), origin,
                                     True, True, info_text='Dicke')

        return handle_list


    def _set_placement_layer(self, placement: AllplanReinf.BarPlacement, layer_id: int):
        """Weist dem Placement einen Allplan-Layer zu (0 = aktueller Layer)."""

        if layer_id <= 0:
            return

        common_props = AllplanBaseEle.CommonProperties()
        common_props.GetGlobalProperties()
        common_props.Layer = layer_id

        placement.SetCommonProperties(common_props)


    def _shape_props(self, layer: LayerConfig) -> ReinforcementShapeProperties:
        return ReinforcementShapeProperties.rebar(layer.diameter,
                                                  layer.bending_roller,
                                                  layer.steel_grade,
                                                  self.concrete_grade,
                                                  AllplanReinf.BendingShapeType.LongitudinalBar)


    def _create_straight_bar_shape(self,
                                   layer: LayerConfig,
                                   length: float,
                                   cover_start: float,
                                   cover_end: float) -> AllplanReinf.BendingShape:
        """Gerader Stab in Lagenrichtung.

        Deckungsmodell wie im Deckenplatte-PythonPart des Anwenders: Die
        Quer-Betondeckung des Shapes ist 0, die Höhenlage steckt allein in
        der z-Koordinate der Verlegepunkte (Stabachse, siehe z_axis). Damit
        liegt die Verlegeachse exakt auf der gewünschten Höhe, und dieselbe
        Rechnung gilt für Lagenstäbe und Randbügel.

        `length` ist das Rohmass (z. B. volle Plattenlänge); cover_start und
        cover_end kürzen den Stab beidseitig auf das Nettomass.
        """

        model_angles = RotationAngles(0, 0, 0) if layer.direction == 'X' else RotationAngles(0, 0, 90)

        cover_props = ConcreteCoverProperties(cover_start, cover_end, 0.0, 0.0)

        # start_hook/end_hook = -1: keine Haken (der Default 0 würde Haken
        # mit automatisch berechneter Länge erzeugen)
        return GeneralShapeBuilder.create_longitudinal_shape_with_hooks(length,
                                                                        model_angles,
                                                                        self._shape_props(layer),
                                                                        cover_props,
                                                                        start_hook=-1,
                                                                        end_hook=-1)


    # ==================== Rechteckmodus ====================

    def _distribution_regions(self,
                              layer: LayerConfig,
                              from_pnt: AllplanGeo.Point3D,
                              to_pnt: AllplanGeo.Point3D,
                              cover_from: float,
                              cover_to: float) -> list[tuple[AllplanGeo.Point3D, AllplanGeo.Point3D, float, float, float]]:
        """Zerlegt eine Verteilstrecke in Bereiche (from, to, spacing,
        cover_from, cover_to).

        Ohne Randverdichtung ein Bereich mit dem Lagenabstand; mit
        Randverdichtung drei Bereiche über
        LinearBarBuilder.calculate_length_of_regions (Zone/Feld/Zone).
        """

        default = [(from_pnt, to_pnt, layer.spacing, cover_from, cover_to)]

        if not self.edge_zones_active:
            return default

        # Zonen nur, wenn zwischen beiden Verdichtungszonen noch ein
        # Mittelfeld verbleibt — sonst würden sich die Regionen überlappen
        distribution_length = ((to_pnt.X - from_pnt.X) ** 2 +
                               (to_pnt.Y - from_pnt.Y) ** 2) ** 0.5 - cover_from - cover_to

        if 2 * self.edge_zone_length >= distribution_length:
            return default

        value_list = [(self.edge_zone_length, self.edge_zone_spacing, layer.diameter),
                      (0.0, layer.spacing, layer.diameter),
                      (self.edge_zone_length, self.edge_zone_spacing, layer.diameter)]

        regions = LinearBarBuilder.calculate_length_of_regions(
            value_list, from_pnt, to_pnt, cover_from, cover_to)

        if len(regions) != len(value_list):
            return default

        return [(region_from, region_to, value[1], 0.0, 0.0)
                for (region_from, region_to), value in zip(regions, value_list)]


    def _create_layer_placements(self, layer: LayerConfig) -> list[AllplanReinf.BarPlacement]:
        """Erzeugt die Placements einer Lage (Rechteckmodus), bei aktiver
        Öffnung bandweise mit gekappten Stäben links/rechts der Öffnung.
        """

        if layer.diameter <= 0 or layer.spacing <= 0:
            return []

        if layer.direction == 'X':
            run_len, dist_len = self.length, self.width
            opening_run, opening_dist = self.opening_x, self.opening_y
            side_start, side_end = self.side_left, self.side_right
        else:
            run_len, dist_len = self.width, self.length
            opening_run, opening_dist = self.opening_y, self.opening_x
            side_start, side_end = self.side_bottom, self.side_top

        if not self.has_opening:
            opening_run = opening_dist = None

        # Reststäbe unterhalb der konfigurierten Mindestlänge (mindestens aber
        # beidseitige Deckung + 10 mm Reststab) entfallen ersatzlos; ein
        # Anschlusseisen-Überstand zählt dabei zur Segmentlänge dazu, damit
        # der Bewehrungsanschluss an der Kante nicht stillschweigend entfällt
        # compute_placement_bands prüft gegen das Rohmass, der Stab wird
        # danach noch um beidseitige Deckung kürzer -> Deckung aufschlagen
        min_segment_length = max(self.build_ele.MinBarLength.value,
                                 10.0) + 2 * self.concrete_cover

        lap = self.overlap_factor * layer.diameter

        bands = compute_placement_bands(dist_len, run_len, opening_dist, opening_run,
                                        min_segment_length=min_segment_length,
                                        bonus_start=lap if side_start == SIDE_CONNECT else 0.0,
                                        bonus_end=lap if side_end == SIDE_CONNECT else 0.0)

        placements: list[AllplanReinf.BarPlacement] = []

        for band in bands:
            for run_from, run_to in band.run_segments:
                # Anschlusseisen: Stäbe, die an einer entsprechend
                # konfigurierten Plattenkante enden, stehen um die Stoßlänge
                # (Stoßfaktor x Ø) über den Plattenrand über
                ae_start = lap if run_from == 0 and side_start == SIDE_CONNECT else 0.0
                ae_end = lap if run_to == run_len and side_end == SIDE_CONNECT else 0.0

                # Deckung an den Stabenden: Plattenrand -> seitliche Deckung,
                # Öffnungsrand -> ebenfalls seitliche Deckung (konfigurierbar
                # über denselben Parameter, bewusst keine Norm-Annahme);
                # überstehende Anschlusseisen-Enden ohne Deckung
                cover_start = 0.0 if ae_start else self.concrete_cover
                cover_end = 0.0 if ae_end else self.concrete_cover

                # Nettospanne des Stabes (Deckung bzw. Anschlusseisen-Überstand
                # bereits berücksichtigt) — Grundlage für die Stossteilung
                net_from = run_from - ae_start + cover_start
                net_to = run_to + ae_end - cover_end

                # Sperrzone für Stossfugen rund um die Öffnung
                zones = []
                if self.has_opening and self.lap_opening_margin > 0:
                    zones = [(opening_run[0] - self.lap_opening_margin,
                              opening_run[1] + self.lap_opening_margin)]

                if layer.direction == 'X':
                    from_pnt = self._pnt(0, band.dist_from, layer.z_axis)
                    to_pnt = self._pnt(0, band.dist_to, layer.z_axis)
                else:
                    from_pnt = self._pnt(band.dist_from, 0, layer.z_axis)
                    to_pnt = self._pnt(band.dist_to, 0, layer.z_axis)

                # Verteil-Deckung nur an echten Plattenrändern, nicht an
                # Bandgrenzen mitten in der Platte
                place_cover_from = self.concrete_cover if band.dist_from == 0 else 0
                place_cover_to = self.concrete_cover if band.dist_to == dist_len else 0

                # Randverdichtung nur für Bänder über die volle Plattenbreite,
                # damit die Zonen an den Plattenrändern (nicht an Bandgrenzen
                # mitten in der Platte) liegen
                full_band = band.dist_from == 0 and band.dist_to == dist_len

                if full_band:
                    regions = self._distribution_regions(layer, from_pnt, to_pnt,
                                                         place_cover_from, place_cover_to)
                else:
                    regions = [(from_pnt, to_pnt, layer.spacing,
                                place_cover_from, place_cover_to)]

                for region_from, region_to, spacing, region_cover_from, region_cover_to in regions:
                    for piece_from, piece_to in self._lap_pieces((net_from, net_to),
                                                                 layer, 0.0, zones):
                        if True:
                            piece_shape = self._create_straight_bar_shape(
                                layer, piece_to - piece_from, 0.0, 0.0)

                            if layer.direction == 'X':
                                offset = AllplanGeo.Point3D(piece_from, 0, 0)
                            else:
                                offset = AllplanGeo.Point3D(0, piece_from, 0)

                            placement = LinearBarBuilder.create_linear_bar_placement_from_to_by_dist(
                                self._next_position(),
                                piece_shape,
                                region_from + offset,
                                region_to + offset,
                                region_cover_from,
                                region_cover_to,
                                spacing)

                            self._set_placement_layer(placement, layer.allplan_layer)
                            placements.append(placement)

        layer.placements = placements

        return placements


    def _create_opening_edge_reinforcement(self) -> list[AllplanReinf.BarPlacement]:
        """Randverstärkung um die Öffnung (Rechteckmodus): je Öffnungskante
        eine Schar Zulagestäbe parallel zur Kante, mit beidseitigem Überstand
        um die (konfigurierbare) Übergreifungslänge.
        """

        build_ele = self.build_ele

        lap_length = build_ele.LapLength.value
        bar_count = build_ele.EdgeBarCount.value
        bar_spacing = build_ele.EdgeBarSpacing.value
        edge_diameter = build_ele.EdgeBarDiameter.value

        # Verlegezone mit (n-1) Zwischenräumen, damit der Palettenwert dem
        # tatsächlichen Achsabstand entspricht; die erste Stabachse wird um
        # einen Stabdurchmesser von der Öffnungskante abgerückt
        zone_width = max((bar_count - 1) * bar_spacing, 1.0)
        edge_margin = edge_diameter

        # Zulagen liegen als eigene Ebenen innerhalb der Hauptlagen: unten
        # oberhalb der inneren unteren Lage, oben unterhalb der inneren oberen
        # Lage — X- und Y-Zulagen übereinander gestapelt, damit sich weder
        # Haupt- noch Zulagestäbe durchdringen
        bottom_mains = [layer for layer in self.layers if not layer.is_top]
        top_mains = [layer for layer in self.layers if layer.is_top]

        # Oberkante der unteren bzw. Unterkante der oberen Hauptbewehrung
        bottom_base = max(layer.z_axis + layer.diameter / 2.0
                          for layer in bottom_mains) if bottom_mains else None
        top_base = min(layer.z_axis - layer.diameter / 2.0
                       for layer in top_mains) if top_mains else None

        edge_layers = []

        for direction in ('X', 'Y'):
            stack_index = 0 if direction == 'X' else 1

            for is_top in (False, True):
                main_layer = next((layer for layer in self.layers
                                   if layer.direction == direction and layer.is_top == is_top), None)

                if main_layer is None or (top_base if is_top else bottom_base) is None:
                    continue

                edge_layer = LayerConfig(f'Randeinfassung {direction} {"oben" if is_top else "unten"}',
                                         direction, is_top,
                                         edge_diameter,
                                         bar_spacing,
                                         main_layer.steel_grade)

                if is_top:
                    edge_layer.z_axis = top_base - (stack_index + 0.5) * edge_diameter
                else:
                    edge_layer.z_axis = bottom_base + (stack_index + 0.5) * edge_diameter

                if edge_layer.z_axis <= 0 or \
                        (is_top and bottom_base is not None and edge_layer.z_axis < bottom_base):
                    print(f'SlabReinforcement: Zulage "{edge_layer.name}" entfällt — '
                          f'kein Platz innerhalb der Hauptlagen')
                    continue

                edge_layer.bending_roller = AllplanReinf.BendingRollerService.GetBendingRollerFactor(
                    edge_layer.diameter, edge_layer.steel_grade, -1, False)

                # Layer der Hauptlage gleicher Richtung und Höhenlage
                edge_layer.allplan_layer = main_layer.allplan_layer

                edge_layers.append(edge_layer)

        placements: list[AllplanReinf.BarPlacement] = []

        for edge_layer in edge_layers:
            if edge_layer.direction == 'X':
                run_len, dist_len = self.length, self.width
                opening_run, opening_dist = self.opening_x, self.opening_y
            else:
                run_len, dist_len = self.width, self.length
                opening_run, opening_dist = self.opening_y, self.opening_x

            # Öffnungsintervall auf der Verteilachse um den Randabstand
            # aufweiten, damit die erste Stabachse nicht auf der Kante liegt
            opening_dist_with_margin = (opening_dist[0] - edge_margin,
                                        opening_dist[1] + edge_margin)

            for run in compute_edge_bar_runs(dist_len, run_len, opening_dist_with_margin,
                                             opening_run, lap_length, zone_width,
                                             dist_margin=self.concrete_cover
                                             + edge_layer.diameter / 2.0):
                cover_start = self.concrete_cover if run.run_from == 0 else 0
                cover_end = self.concrete_cover if run.run_to == run_len else 0

                # Zulagen können ebenfalls zu lang für einen Stab werden
                net = (run.run_from + cover_start, run.run_to - cover_end)

                for piece_from, piece_to in self._lap_pieces(net, edge_layer, 0.0, []):
                    shape = self._create_straight_bar_shape(edge_layer,
                                                            piece_to - piece_from,
                                                            0.0, 0.0)

                    if edge_layer.direction == 'X':
                        from_pnt = self._pnt(piece_from, run.dist_from, edge_layer.z_axis)
                        to_pnt = self._pnt(piece_from, run.dist_to, edge_layer.z_axis)
                    else:
                        from_pnt = self._pnt(run.dist_from, piece_from, edge_layer.z_axis)
                        to_pnt = self._pnt(run.dist_to, piece_from, edge_layer.z_axis)

                    placement = LinearBarBuilder.create_linear_bar_placement_from_to_by_count(
                        self._next_position(),
                        shape,
                        from_pnt,
                        to_pnt,
                        0,
                        0,
                        bar_count)

                    self._set_placement_layer(placement, edge_layer.allplan_layer)
                    placements.append(placement)

        return placements


    def _create_separate_connection_bars(self) -> list[AllplanReinf.BarPlacement]:
        """Separate Anschlusseisen (Rechteckmodus): eigene gerade Stäbe mit
        Länge 2 x Stoßlänge, mittig auf der jeweiligen Plattenkante, in Höhe
        und Raster der Lagen, die senkrecht auf diese Kante zulaufen.
        """

        placements: list[AllplanReinf.BarPlacement] = []

        for direction, side_start, side_end in (('X', self.side_left, self.side_right),
                                                ('Y', self.side_bottom, self.side_top)):
            if direction == 'X':
                run_len, dist_len = self.length, self.width
                opening_run, opening_dist = self.opening_x, self.opening_y
            else:
                run_len, dist_len = self.width, self.length
                opening_run, opening_dist = self.opening_y, self.opening_x

            if not self.has_opening:
                opening_run = opening_dist = None

            for layer in [layer for layer in self.layers if layer.direction == direction]:
                lap = self.overlap_factor * layer.diameter

                for side_option, at_start in ((side_start, True), (side_end, False)):
                    if side_option != SIDE_SEPARATE:
                        continue

                    # Stab steht je zur Hälfte in und außerhalb der Platte
                    run_pos = -lap if at_start else run_len - lap

                    # Verlegestrecke unterbrechen, wo die Öffnung den innen
                    # liegenden Teil des Stabstreifens schneidet
                    strip_run = (0.0, lap) if at_start else (run_len - lap, run_len)

                    for dist_from, dist_to in compute_edge_strip_segments(
                            dist_len, opening_dist, opening_run, strip_run):
                        shape = self._create_straight_bar_shape(layer, 2 * lap, 0, 0)

                        if direction == 'X':
                            from_pnt = self._pnt(run_pos, dist_from, layer.z_axis)
                            to_pnt = self._pnt(run_pos, dist_to, layer.z_axis)
                        else:
                            from_pnt = self._pnt(dist_from, run_pos, layer.z_axis)
                            to_pnt = self._pnt(dist_to, run_pos, layer.z_axis)

                        placement = LinearBarBuilder.create_linear_bar_placement_from_to_by_dist(
                            self._next_position(),
                            shape,
                            from_pnt,
                            to_pnt,
                            self.concrete_cover if dist_from == 0 else 0,
                            self.concrete_cover if dist_to == dist_len else 0,
                            layer.spacing)

                        self._set_placement_layer(placement, layer.allplan_layer)
                        placements.append(placement)

        return placements


    def _create_edge_stirrups(self) -> list[AllplanReinf.BarPlacement]:
        """Offene U-Randbügel (Steckbügel, Rechteckmodus) entlang der
        gewählten Plattenkanten.

        Der Bügel umgreift die beiden Lagen, deren Stäbe senkrecht auf die
        Kante zulaufen: Außenmaß = Abstand Unterkante untere Lage bis
        Oberkante obere Lage (auf ganze cm abgerundet), Schenkellänge =
        Stoßlänge − Ø/2 (Achsmaß), Ø/Abstand/Stahlgüte von der unteren Lage.
        Rotationswinkel wie im Deckenplatte-Vorbild: Ry=-90 stellt den Steg
        vertikal, Rz richtet die Schenkel nach innen.
        """

        placements: list[AllplanReinf.BarPlacement] = []

        for direction, edge_options in (('X', ((self.side_left, True), (self.side_right, False))),
                                        ('Y', ((self.side_bottom, True), (self.side_top, False)))):
            if all(option != SIDE_STIRRUP for option, _ in edge_options):
                continue

            direction_layers = [layer for layer in self.layers if layer.direction == direction]
            bottom_layer = next((layer for layer in direction_layers if not layer.is_top), None)
            top_layer = next((layer for layer in direction_layers if layer.is_top), None)

            if bottom_layer is None or top_layer is None:
                print(f'SlabReinforcement: Randbügel {direction} entfallen — '
                      f'zugehörige Lagen sind nicht vorhanden')
                continue

            diameter = bottom_layer.diameter

            # Außenmaß über beide Lagen (UK untere Lage bis OK obere Lage),
            # auf ganze cm abgerundet; für den ShapeBuilder wird das Achsmaß
            # (Außenmaß − Ø) übergeben
            outer_height = (top_layer.z_axis + top_layer.diameter / 2.0) - \
                           (bottom_layer.z_axis - bottom_layer.diameter / 2.0)
            web_height = int(outer_height / 10.0) * 10.0 - diameter
            leg_length = self.overlap_factor * diameter - 0.5 * diameter

            if web_height <= 0 or leg_length <= 0:
                print(f'SlabReinforcement: Randbügel {direction} entfallen — '
                      f'Bügelhöhe/Schenkellänge nicht darstellbar')
                continue

            # Verlegeachse auf Höhe der Stabachse der unteren Lage — wie im
            # Deckenplatte-Vorbild (z_lr = z1)
            z_pos = bottom_layer.z_axis

            shape_props = ReinforcementShapeProperties.rebar(
                diameter, bottom_layer.bending_roller, bottom_layer.steel_grade,
                self.concrete_grade, AllplanReinf.BendingShapeType.OpenStirrup)

            no_cover = ConcreteCoverProperties(0.0, 0.0, 0.0, 0.0)

            # Layer wie die Lage, die in Bügelrichtung verläuft — dieselbe
            # Lage, von der auch Ø, Abstand und Stahlgüte stammen
            stirrup_layer_id = bottom_layer.allplan_layer

            if direction == 'X':
                run_len, dist_len = self.length, self.width
                opening_run, opening_dist = self.opening_x, self.opening_y
            else:
                run_len, dist_len = self.width, self.length
                opening_run, opening_dist = self.opening_y, self.opening_x

            if not self.has_opening:
                opening_run = opening_dist = None

            for side_option, at_start in edge_options:
                if side_option != SIDE_STIRRUP:
                    continue

                if direction == 'X':
                    angles = RotationAngles(0, -90, -90) if at_start else RotationAngles(0, -90, 90)
                    edge_pos = self.concrete_cover if at_start else self.length - self.concrete_cover
                else:
                    angles = RotationAngles(0, -90, 0) if at_start else RotationAngles(0, -90, 180)
                    edge_pos = self.concrete_cover if at_start else self.width - self.concrete_cover

                shape = GeneralShapeBuilder.create_open_stirrup(
                    web_height, leg_length, angles, shape_props, no_cover,
                    -1, -1, 0.0, 0.0)

                if not shape.IsValid():
                    print(f'SlabReinforcement: Randbügel-Shape {direction} ungültig — übersprungen')
                    continue

                # Verlegestrecke unterbrechen, wo die Öffnung den Randstreifen
                # (Bügelschenkel-Tiefe ab Kante) schneidet
                strip_depth = self.concrete_cover + leg_length
                strip_run = (0.0, strip_depth) if at_start else (run_len - strip_depth, run_len)

                for dist_from, dist_to in compute_edge_strip_segments(
                        dist_len, opening_dist, opening_run, strip_run):
                    if direction == 'X':
                        from_pnt = self._pnt(edge_pos, dist_from, z_pos)
                        to_pnt = self._pnt(edge_pos, dist_to, z_pos)
                    else:
                        from_pnt = self._pnt(dist_from, edge_pos, z_pos)
                        to_pnt = self._pnt(dist_to, edge_pos, z_pos)

                    placement = LinearBarBuilder.create_linear_bar_placement_from_to_by_dist(
                        self._next_position(),
                        AllplanReinf.BendingShape(shape),
                        from_pnt,
                        to_pnt,
                        self.concrete_cover if dist_from == 0 else 0,
                        self.concrete_cover if dist_to == dist_len else 0,
                        bottom_layer.spacing)

                    self._set_placement_layer(placement, stirrup_layer_id)
                    placements.append(placement)

        return placements


    def _hook_length(self, layer: LayerConfig) -> float:
        """Schenkellänge des angebogenen Randbügels.

        Entspricht dem Achsmass des einzelnen U-Bügels: Aussenmass über
        beide Lagen derselben Richtung, auf ganze cm abgerundet, minus
        Stabdurchmesser.
        """

        partners = [item for item in self.layers if item.direction == layer.direction]

        bottom = next((item for item in partners if not item.is_top), None)
        top = next((item for item in partners if item.is_top), None)

        if bottom is None or top is None:
            return 0.0

        outer = (top.z_axis + top.diameter / 2.0) - (bottom.z_axis - bottom.diameter / 2.0)

        return max(int(outer / 10.0) * 10.0 - layer.diameter, 0.0)


    def _hook_edges(self, layer: LayerConfig) -> list[tuple[tuple, tuple]]:
        """Kanten, an denen die Stäbe dieser Lage angebogen werden.

        Angebogen wird nur an den unteren Lagen (1. und 2. Lage) und nur an
        Kanten, in die die Stäbe hineinlaufen — Kanten parallel zur
        Stabrichtung scheiden aus. Schrägen sind ausdrücklich dabei: dort
        entsteht die Abtreppung, und auch deren Stäbe brauchen einen
        Abschlussbügel. Plattenrand und Aussparungsrand haben je eine
        eigene Palettenoption (StirrupStyle bzw. OpeningStirrupStyle).

        Returns:
            Liste (Startpunkt, Endpunkt) der Kante als 2D-Tupel.
        """

        if layer.is_top or not self.contour:
            return []

        dist_axis = 1 if layer.direction == 'X' else 0

        edges = []

        if self.stirrup_style != 'Einzeln':
            for _, option, _, start, end, _ in self._contour_edges():
                if option != SIDE_STIRRUP:
                    continue

                # Kante parallel zur Stabrichtung -> der Stab läuft nicht hinein
                if abs(end[dist_axis] - start[dist_axis]) < 1.0:
                    continue

                edges.append((start, end))

        # Aussparungskanten: gleiche Regel, eigene Palettenoption
        if self.opening_stirrup_style == 'Am Eisen angebogen':
            for opening in self.contour_openings:
                for index, start in enumerate(opening):
                    end = opening[(index + 1) % len(opening)]

                    if abs(end[dist_axis] - start[dist_axis]) < 1.0:
                        continue

                    edges.append((start, end))

        return edges


    def _edge_run_at(self, edge: tuple[tuple, tuple], position: float,
                     run_axis: int) -> float | None:
        """Koordinate auf der Stabachse, an der die Kante die Scanlinie bei
        position schneidet — None, wenn die Kante dort nicht liegt.
        """

        dist_axis = 1 - run_axis
        start, end = edge

        d1, d2 = start[dist_axis], end[dist_axis]

        if abs(d2 - d1) < 1e-9:
            return None

        if not (min(d1, d2) - 1.0 <= position <= max(d1, d2) + 1.0):
            return None

        t = (position - d1) / (d2 - d1)

        return start[run_axis] + t * (end[run_axis] - start[run_axis])


    def _piece_hooks(self,
                     layer: LayerConfig,
                     piece: tuple[float, float],
                     positions: list[float]) -> tuple[float, float]:
        """Bügelschenkel für die beiden Enden eines Teilstabes.

        Ein Ende bekommt einen Bügel, wenn es an einer Randkante endet — im
        rechtwinkligen Fall genau um die Deckung davor, in einer
        Abtreppung um zusätzlich bis zu einer Stufe (Verkürzung + Raster)
        zurückversetzt. Geprüft wird gegen die tatsächliche Kantenlage an
        den Scan-Positionen der Verlegung, damit auch Schrägen greifen und
        ein Stoss mitten in der Platte keinen Bügel bekommt.
        """

        edges = self._hook_edges(layer)
        hook = self._hook_length(layer)

        if not edges or hook <= 0:
            return (0.0, 0.0)

        run_axis = 0 if layer.direction == 'X' else 1

        # Rückversatz, den ein Stabende gegenüber der Kante haben darf:
        # Deckung (an der Schräge cover/sin, begrenzt durch MaxEdgeSetback)
        # plus die Stufengrösse der Abtreppung
        tol = max(self.cover_side, self.max_edge_setback) \
            + self.step_max_loss + self.step_length_raster + 1.0

        def hooked(value: float) -> bool:
            for edge in edges:
                for position in positions:
                    edge_run = self._edge_run_at(edge, position, run_axis)

                    if edge_run is not None and abs(value - edge_run) <= tol:
                        return True

            return False

        return (hook if hooked(piece[0]) else 0.0,
                hook if hooked(piece[1]) else 0.0)


    def _create_bar_with_edge_stirrups(self,
                                       layer: LayerConfig,
                                       length: float,
                                       start_leg: float,
                                       end_leg: float) -> AllplanReinf.BendingShape:
        """Stab mit angebogenem Randbügel an einem oder beiden Enden.

        Der Bügel hat dieselbe Form wie ein einzelner U-Bügel: Der Stab
        bildet den unteren Schenkel, am Rand geht er über den Steg nach
        oben und mit dem oberen Schenkel wieder nach innen. Ein einfacher
        Haken (nur eine Biegung) reicht dafür nicht, deshalb wird die Form
        über eine Freiform aus Punkten aufgebaut.
        """

        web = self._hook_length(layer)
        leg = self.overlap_factor * layer.diameter - 0.5 * layer.diameter

        points = []

        if start_leg > 0:
            points.append(AllplanGeo.Point2D(min(leg, length), web))
            points.append(AllplanGeo.Point2D(0.0, web))

        points.append(AllplanGeo.Point2D(0.0, 0.0))
        points.append(AllplanGeo.Point2D(length, 0.0))

        if end_leg > 0:
            points.append(AllplanGeo.Point2D(length, web))
            points.append(AllplanGeo.Point2D(length - min(leg, length), web))

        model_angles = RotationUtil(90, 0, 0) if layer.direction == 'X' \
            else RotationUtil(90, 0, 90)

        return GeneralShapeBuilder.create_freeform_shape_with_hooks(
            points, model_angles, self._shape_props(layer), 0.0, -1, -1)


    # ==================== Konturmodus: Randausbildung ====================

    def _contour_edges(self) -> list[tuple[int, str, float, tuple, tuple]]:
        """Klassifiziert jede Konturkante nach ihrer Aussennormalen.

        Die vier Palettenoptionen (Links/Rechts/Unten/Oben) gelten damit
        auch für Polygone: Jede Kante bekommt die Option der Richtung, in
        die ihre Aussennormale zeigt.

        Returns:
            Liste (Kantenindex, Option, Innennormalen-Winkel [Grad],
            Startpunkt, Endpunkt)
        """

        if not self.contour:
            return []

        # Umlaufsinn bestimmen, damit die Normale wirklich nach aussen zeigt
        area = loop_area(self.contour)
        sign = 1.0 if area > 0 else -1.0

        edges = []

        bbox = loop_bbox(self.contour)

        for index, start in enumerate(self.contour):
            end = self.contour[(index + 1) % len(self.contour)]

            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy)

            if length < 1.0:
                continue

            # Achsparallel? Nur solche Kanten bekommen Randbügel; schräge
            # Kanten werden ignoriert und die parallelen Nachbarkanten
            # laufen bis zur Bounding Box weiter, als wäre die Schräge
            # ausgefüllt
            axis_parallel = abs(dx) < 1.0 or abs(dy) < 1.0

            if axis_parallel:
                previous = self.contour[index - 1]
                following = self.contour[(index + 2) % len(self.contour)]

                start, end = self._extend_over_slants(start, end, previous,
                                                      following, bbox)

                dx, dy = end[0] - start[0], end[1] - start[1]
                length = math.hypot(dx, dy)

            # Aussennormale bei positivem Umlaufsinn: (dy, -dx)
            nx, ny = sign * dy / length, -sign * dx / length

            if abs(nx) >= abs(ny):
                option = self.side_right if nx > 0 else self.side_left
            else:
                option = self.side_top if ny > 0 else self.side_bottom

            # Innennormale (dorthin zeigen die Bügelschenkel)
            inward = math.degrees(math.atan2(-ny, -nx))

            edges.append((index, option, inward, start, end, axis_parallel))

        return edges


    def _extend_over_slants(self, start, end, previous, following, bbox):
        """Verlängert eine achsparallele Kante über angrenzende Schrägen
        hinweg bis zur Bounding Box — der Randbügel fährt dann durch, als
        wäre die Schräge ausgefüllt.
        """

        horizontal = abs(end[1] - start[1]) < 1.0
        axis = 0 if horizontal else 1
        low, high = bbox[axis], bbox[axis + 2]

        forward = end[axis] >= start[axis]

        def slanted(a, b):
            return abs(a[0] - b[0]) > 1.0 and abs(a[1] - b[1]) > 1.0

        new_start, new_end = list(start), list(end)

        if slanted(previous, start):
            new_start[axis] = low if forward else high

        if slanted(end, following):
            new_end[axis] = high if forward else low

        return tuple(new_start), tuple(new_end)


    def _edge_extensions(self, layer: LayerConfig) -> dict[int, float]:
        """Überstand je Konturkante für Anschlusseisen dieser Lage."""

        lap = self.overlap_factor * layer.diameter

        return {index: lap for index, option, _, _, _, _ in self._contour_edges()
                if option == SIDE_CONNECT}


    # ============ Aussparungen: Bewehrung beliebiger Polygone ============

    def _opening_reinf_layer(self,
                             name: str,
                             is_top: bool,
                             stack_index: int,
                             diameter: float,
                             spacing: float,
                             allplan_layer: int | None = None) -> LayerConfig | None:
        """Zulagenebene innerhalb der Hauptlagen.

        Unten liegen die Zulagen **oberhalb** der inneren unteren Lage, oben
        **unterhalb** der inneren oberen Lage. stack_index stapelt mehrere
        Zulagenrichtungen übereinander, damit sich Stäbe nicht durchdringen.
        Gibt None zurück, wenn dafür kein Platz zwischen den Hauptlagen ist.
        """

        mains = [layer for layer in self.layers if layer.is_top == is_top]
        opposite = [layer for layer in self.layers if layer.is_top != is_top]

        if not mains:
            return None

        if is_top:
            base = min(layer.z_axis - layer.diameter / 2.0 for layer in mains)
            z_axis = base - (stack_index + 0.5) * diameter
            limit = max((layer.z_axis + layer.diameter / 2.0
                         for layer in opposite), default=0.0)
            no_room = z_axis - diameter / 2.0 < limit
        else:
            base = max(layer.z_axis + layer.diameter / 2.0 for layer in mains)
            z_axis = base + (stack_index + 0.5) * diameter
            limit = min((layer.z_axis - layer.diameter / 2.0
                         for layer in opposite), default=self.thickness)
            no_room = z_axis + diameter / 2.0 > limit

        if no_room:
            print(f'SlabReinforcement: Zulage "{name}" entfällt — '
                  f'kein Platz zwischen den Hauptlagen')
            return None

        reference = next((layer for layer in mains), None)

        layer = LayerConfig(name, 'X', is_top, diameter, spacing,
                            reference.steel_grade)
        layer.z_axis = z_axis
        layer.allplan_layer = allplan_layer if allplan_layer is not None \
            else reference.allplan_layer
        layer.bending_roller = AllplanReinf.BendingRollerService.GetBendingRollerFactor(
            diameter, layer.steel_grade, -1, False)

        return layer


    def _place_free_bars(self,
                         layer: LayerConfig,
                         bars: list) -> AllplanReinf.BarPlacement | None:
        """Verlegt eine Gruppe paralleler, gleich langer Stäbe beliebiger
        Richtung als **eine** Verlegung.

        Die Stabrichtung steckt im Rotationswinkel des Shapes, die
        Verlegerichtung im Richtungspunkt — damit lassen sich auch die
        schiefen Zulagen einer Aussparung wie eine normale Schar absetzen.
        """

        if not bars:
            return None

        first = bars[0]
        length = first.length

        if length <= 0:
            return None

        model_angles = RotationAngles(0, 0, first.angle)

        shape = GeneralShapeBuilder.create_longitudinal_shape_with_hooks(
            length, model_angles, self._shape_props(layer),
            ConcreteCoverProperties(0.0, 0.0, 0.0, 0.0),
            start_hook=-1, end_hook=-1)

        from_pnt = self._pnt(first.start[0], first.start[1], layer.z_axis)

        if len(bars) > 1:
            second = bars[1]
            direction_pnt = self._pnt(second.start[0], second.start[1], layer.z_axis)
            spacing = math.hypot(second.start[0] - first.start[0],
                                 second.start[1] - first.start[1])
        else:
            # Einzelstab: Verlegerichtung senkrecht zur Stabachse
            angle = math.radians(first.angle)
            direction_pnt = self._pnt(first.start[0] - math.sin(angle),
                                      first.start[1] + math.cos(angle),
                                      layer.z_axis)
            spacing = layer.spacing

        placement = LinearBarBuilder.create_linear_bar_placement_from_by_dist_count(
            self._next_position(), shape, from_pnt, direction_pnt,
            0.0, spacing, len(bars))

        self._set_placement_layer(placement, layer.allplan_layer)

        return placement


    def _create_opening_reinforcement(self) -> list[AllplanReinf.BarPlacement]:
        """Randzulagen und Diagonalzulagen um beliebige Aussparungspolygone.

        Je Aussparungskante läuft eine Schar Zulagestäbe **parallel zu
        dieser Kante**, mit Überstand um die Übergreifungslänge über beide
        Ecken hinaus; anschliessend wird jeder Stab an der Plattenkontur und
        an allen anderen Aussparungen abgeschnitten. Die Diagonalzulagen
        überspannen die Ecken senkrecht zur Winkelhalbierenden.

        Keine Norm belegt Anzahl, Durchmesser oder Länge dieser Zulagen —
        SIA 262 fordert lediglich, freie Plattenränder einzufassen. Die
        Werte sind daher Palettenparameter (Bürostandard).
        """

        build_ele = self.build_ele

        if not self.contour_openings or self.contour is None:
            return []

        edge_active = build_ele.EdgeReinfActive.value
        diagonal_active = build_ele.DiagonalActive.value

        if not edge_active and not diagonal_active:
            return []

        min_length = max(build_ele.MinBarLength.value, 10.0)

        placements: list[AllplanReinf.BarPlacement] = []

        for opening in self.contour_openings:
            others = [loop for loop in self.contour_openings if loop is not opening]

            if edge_active:
                placements += self._place_opening_bars(
                    opening, others, min_length,
                    diameter=build_ele.EdgeBarDiameter.value,
                    spacing=build_ele.EdgeBarSpacing.value,
                    name='Randzulage Aussparung',
                    bars_by_stack=self._opening_edge_bars_by_stack(opening),
                    allplan_layer=build_ele.LayerOpeningEdge.value)

            if diagonal_active:
                diagonals = corner_diagonals(
                    opening,
                    build_ele.DiagonalCount.value,
                    build_ele.DiagonalDiameter.value + build_ele.EdgeBarDiameter.value,
                    build_ele.DiagonalLength.value,
                    build_ele.DiagonalSpacing.value)

                placements += self._place_opening_bars(
                    opening, others, min_length,
                    diameter=build_ele.DiagonalDiameter.value,
                    spacing=build_ele.DiagonalSpacing.value,
                    name='Diagonalzulage Aussparung',
                    bars_by_stack={2: diagonals},
                    allplan_layer=build_ele.LayerOpeningDiagonal.value)

            placements += self._create_opening_stirrups(opening)

        return placements


    def _create_opening_stirrups(self, opening: list) -> list[AllplanReinf.BarPlacement]:
        """Separate U-Randbügel entlang der Aussparungskanten.

        Aufbau identisch zu den Randbügeln der Plattenkante: der offene
        U-Bügel umgreift die beiden Lagen, deren Stäbe senkrecht auf die
        Kante zulaufen, die Schenkel zeigen in den Beton hinein — bei einer
        Aussparung also von der Öffnung weg.

        Bei "Am Eisen angebogen" entsteht hier nichts: dann bekommen die
        Lagenstäbe, die an der Aussparung enden, den Bügel angebogen
        (siehe _hook_edges).
        """

        if self.opening_stirrup_style != 'Einzeln':
            return []

        spacing = self.build_ele.OpeningStirrupSpacing.value

        if spacing <= 0:
            return []

        placements: list[AllplanReinf.BarPlacement] = []

        normals = outward_normals(opening)

        for index, start in enumerate(opening):
            end = opening[(index + 1) % len(opening)]

            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy)

            if length < 1.0:
                continue

            # Die Schenkel zeigen in den Beton: das ist bei einer Aussparung
            # die Aussennormale des Öffnungspolygons
            nx, ny = normals[index]
            inward = math.degrees(math.atan2(ny, nx))

            # Stäbe, die senkrecht auf diese Kante zulaufen
            direction = 'X' if abs(nx) >= abs(ny) else 'Y'

            layers = [layer for layer in self.layers if layer.direction == direction]
            bottom = next((layer for layer in layers if not layer.is_top), None)
            top = next((layer for layer in layers if layer.is_top), None)

            if bottom is None or top is None:
                continue

            # Verlegelinie: Kante um die Deckung nach aussen versetzt und an
            # beiden Enden um die Deckung eingezogen
            ux, uy = dx / length, dy / length
            offset = self.cover_side

            from_2d = (start[0] + nx * offset + ux * offset,
                       start[1] + ny * offset + uy * offset)
            to_2d = (end[0] + nx * offset - ux * offset,
                     end[1] + ny * offset - uy * offset)

            if math.hypot(to_2d[0] - from_2d[0], to_2d[1] - from_2d[1]) < spacing:
                continue

            placement = self._create_contour_stirrup(
                bottom, top, inward, from_2d, to_2d,
                spacing=spacing,
                # Layer der Lage, die in Bügelrichtung verläuft — dieselbe
                # Lage, von der auch Ø, Abstand und Stahlgüte stammen
                allplan_layer=bottom.allplan_layer)

            if placement is not None:
                placements.append(placement)

        return placements


    def _opening_edge_bars_by_stack(self, opening: list) -> dict:
        """Randzulagen je Aussparung, nach Stapelebene sortiert.

        Benachbarte Kanten stehen (fast) senkrecht aufeinander — ihre
        Zulagen dürfen sich nicht durchdringen. Deshalb landen Kanten mit
        geradem Index in der einen, Kanten mit ungeradem Index in der
        anderen Ebene: bei einer rechteckigen Aussparung genau die beiden
        Hauptrichtungen.
        """

        build_ele = self.build_ele

        bars = opening_edge_bars(
            opening,
            build_ele.EdgeBarCount.value,
            build_ele.EdgeBarDiameter.value,
            build_ele.EdgeBarSpacing.value,
            build_ele.LapLength.value)

        by_stack: dict = {0: [], 1: []}

        for bar in bars:
            by_stack[bar.edge_index % 2].append(bar)

        return by_stack


    def _place_opening_bars(self,
                            opening: list,
                            others: list,
                            min_length: float,
                            diameter: float,
                            spacing: float,
                            name: str,
                            bars_by_stack: dict,
                            allplan_layer: int | None = None) -> list[AllplanReinf.BarPlacement]:
        """Schneidet die Stäbe an Kontur und übrigen Aussparungen ab und
        verlegt sie in allen vier Zulagenebenen (unten/oben je Stapel).
        """

        placements: list[AllplanReinf.BarPlacement] = []

        holes = [opening] + list(others)

        for stack_index, bars in bars_by_stack.items():
            if not bars:
                continue

            clipped: list = []

            for bar in bars:
                clipped += clip_bar(bar, self.contour, holes,
                                    cover=self.cover_side,
                                    max_setback=self.max_edge_setback,
                                    min_length=min_length)

            if not clipped:
                continue

            for is_top in (False, True):
                layer = self._opening_reinf_layer(
                    f'{name} {"oben" if is_top else "unten"} {stack_index + 1}',
                    is_top, stack_index, diameter, spacing, allplan_layer)

                if layer is None:
                    continue

                for group in group_equal_bars(clipped):
                    placement = self._place_free_bars(layer, group)

                    if placement is not None:
                        placements.append(placement)

        return placements


    def _create_contour_edge_reinforcement(self) -> list[AllplanReinf.BarPlacement]:
        """Randbügel und separate Anschlusseisen entlang der Konturkanten.

        Aufbau wie im Deckenplatte-PythonPart: offene U-Bügel umgreifen die
        beiden Lagen, deren Stäbe senkrecht auf die Kante zulaufen; die
        Schenkel zeigen nach innen. Separate Anschlusseisen sind gerade
        Stäbe der Länge 2 x Übergreifung, mittig auf der Kante.
        """

        placements: list[AllplanReinf.BarPlacement] = []

        for index, option, inward, start, end, axis_parallel in self._contour_edges():
            if option in (SIDE_NONE, SIDE_CONNECT):
                continue

            # Randbügel nur an achsparallelen Kanten; an schrägen Kanten
            # übernehmen die verlängerten Nachbarkanten
            if option == SIDE_STIRRUP and not axis_parallel:
                continue

            # "Am Eisen angebogen": kein eigener Bügel, stattdessen bekommen
            # die Lagenstäbe an dieser Kante einen Haken
            if option == SIDE_STIRRUP and self.stirrup_style != 'Einzeln':
                continue

            dx, dy = end[0] - start[0], end[1] - start[1]
            length = math.hypot(dx, dy)

            # Stäbe, die senkrecht auf diese Kante zulaufen
            direction = 'X' if abs(math.cos(math.radians(inward))) >= \
                abs(math.sin(math.radians(inward))) else 'Y'

            layers = [layer for layer in self.layers if layer.direction == direction]
            bottom = next((layer for layer in layers if not layer.is_top), None)
            top = next((layer for layer in layers if layer.is_top), None)

            if bottom is None or top is None:
                continue

            # Verlegelinie: Kante um die Deckung nach innen versetzt und an
            # beiden Enden um die Deckung eingezogen
            ux, uy = dx / length, dy / length
            ix, iy = math.cos(math.radians(inward)), math.sin(math.radians(inward))
            offset = self.concrete_cover

            from_2d = (start[0] + ix * offset + ux * offset,
                       start[1] + iy * offset + uy * offset)
            to_2d = (end[0] + ix * offset - ux * offset,
                     end[1] + iy * offset - uy * offset)

            if math.hypot(to_2d[0] - from_2d[0], to_2d[1] - from_2d[1]) < bottom.spacing:
                continue


            if option == SIDE_STIRRUP:
                placement = self._create_contour_stirrup(bottom, top, inward,
                                                         from_2d, to_2d)
            else:
                placement = self._create_contour_separate_bar(bottom, inward,
                                                              from_2d, to_2d)

            if placement is not None:
                placements.append(placement)

        return placements


    def _create_contour_stirrup(self,
                                bottom: LayerConfig,
                                top: LayerConfig,
                                inward: float,
                                from_2d: tuple,
                                to_2d: tuple,
                                spacing: float | None = None,
                                allplan_layer: int | None = None):
        """Offener U-Randbügel entlang einer Kante — Plattenrand oder
        Aussparungsrand, je nach übergebener Verlegelinie und Innenrichtung.
        """

        diameter = bottom.diameter

        # Aussenmass über beide Lagen, auf ganze cm abgerundet; der
        # ShapeBuilder bekommt das Achsmass (Aussenmass - ø)
        outer_height = (top.z_axis + top.diameter / 2.0) - \
                       (bottom.z_axis - bottom.diameter / 2.0)
        web_height = int(outer_height / 10.0) * 10.0 - diameter
        leg_length = self.overlap_factor * diameter - 0.5 * diameter

        if web_height <= 0 or leg_length <= 0:
            print(f'SlabReinforcement: Randbügel entfällt — Bügelhöhe/Schenkel '
                  f'nicht darstellbar')
            return None

        shape_props = ReinforcementShapeProperties.rebar(
            diameter, bottom.bending_roller, bottom.steel_grade,
            self.concrete_grade, AllplanReinf.BendingShapeType.OpenStirrup)

        # Ry = -90 stellt den Steg senkrecht, Rz richtet die Schenkel nach
        # innen (Vorbild: Rz = 0 / 180 / -90 / 90 für unten/oben/links/rechts,
        # allgemein also Innennormale - 90 Grad)
        angles = RotationAngles(0, -90, inward - 90.0)

        shape = GeneralShapeBuilder.create_open_stirrup(
            web_height, leg_length, angles, shape_props,
            ConcreteCoverProperties(0.0, 0.0, 0.0, 0.0), -1, -1, 0.0, 0.0)

        if not shape.IsValid():
            print('SlabReinforcement: Randbügel-Shape ungültig — übersprungen')
            return None

        placement = LinearBarBuilder.create_linear_bar_placement_from_to_by_dist(
            self._next_position(), shape,
            self._pnt(from_2d[0], from_2d[1], bottom.z_axis),
            self._pnt(to_2d[0], to_2d[1], bottom.z_axis),
            0.0, 0.0, spacing if spacing else bottom.spacing)

        if allplan_layer is not None:
            layer_id = allplan_layer
        else:
            layer_id = self.build_ele.LayerStirrupX.value if bottom.direction == 'X' \
                else self.build_ele.LayerStirrupY.value

        self._set_placement_layer(placement, layer_id)

        return placement


    def _create_contour_separate_bar(self,
                                     layer: LayerConfig,
                                     inward: float,
                                     from_2d: tuple,
                                     to_2d: tuple):
        """Separates Anschlusseisen: gerader Stab der Länge 2 x Übergreifung,
        mittig auf der Kante, senkrecht dazu.
        """

        lap = self.overlap_factor * layer.diameter

        # Der Stab steht je zur Hälfte in und ausserhalb der Platte; die
        # Verlegelinie liegt deshalb um die Deckung zurück auf der Kante
        ix, iy = math.cos(math.radians(inward)), math.sin(math.radians(inward))
        back = self.concrete_cover

        bar = LayerConfig(f'Separates Anschlusseisen {layer.direction}',
                          layer.direction, layer.is_top, layer.diameter,
                          layer.spacing, layer.steel_grade)
        bar.z_axis = layer.z_axis
        bar.bending_roller = layer.bending_roller
        bar.allplan_layer = layer.allplan_layer

        shape = self._create_straight_bar_shape(bar, 2 * lap, 0.0, 0.0)

        # Stabanfang: von der Kante aus lap nach aussen
        start = (from_2d[0] - ix * back - ix * lap, from_2d[1] - iy * back - iy * lap)
        end = (to_2d[0] - ix * back - ix * lap, to_2d[1] - iy * back - iy * lap)

        placement = LinearBarBuilder.create_linear_bar_placement_from_to_by_dist(
            self._next_position(), shape,
            self._pnt(start[0], start[1], bar.z_axis),
            self._pnt(end[0], end[1], bar.z_axis),
            0.0, 0.0, bar.spacing)

        self._set_placement_layer(placement, bar.allplan_layer)

        return placement


    # ==================== Konturmodus (Scanline) ====================

    def _create_contour_layer_placements(self, layer: LayerConfig) -> list[AllplanReinf.BarPlacement]:
        """Scanline-Verlegung einer Lage über die polygonale Kontur.

        Je Scanlinie werden die Segmente innerhalb der Kontur abzüglich
        aller Öffnungen ermittelt; aufeinanderfolgende Linien mit gleichen
        Segmenten und gleichem Abstand werden zu einem linearen Placement
        zusammengefasst (an schrägen Rändern entstehen Einzelstab-Läufe).
        """

        if layer.diameter <= 0 or layer.spacing <= 0 or self.contour is None:
            return []

        run_axis = 0 if layer.direction == 'X' else 1

        min_bar_length = max(self.build_ele.MinBarLength.value, 10.0)

        # Die zurückgegebenen Segmente sind bereits Nettomasse: die
        # Betondeckung ist senkrecht zur jeweiligen Kante abgezogen
        bars = compute_contour_bars(
            self.contour, self.contour_openings, run_axis,
            layer.spacing, self.concrete_cover, min_bar_length,
            edge_zone_length=self.edge_zone_length if self.edge_zones_active else 0.0,
            edge_zone_spacing=self.edge_zone_spacing if self.edge_zones_active else 0.0,
            max_setback=self.max_edge_setback,
            dist_margin=self.concrete_cover + layer.diameter / 2.0,
            edge_extensions=self._edge_extensions(layer))

        # Stossplanung nach Bürosystematik (lap_planning.py): minimale
        # Verlegungsanzahl, Fluchten, Passeisen-Regel, eine Stosslinie je
        # Abtreppung — die Stufenbildung selbst bleibt wie bisher
        lap_length = self.overlap_factor * layer.diameter

        groups = plan_layer_laps(
            bars, self.contour, self.contour_openings, run_axis,
            lmax=self.max_bar_length,
            lap=lap_length,
            pass_threshold=self.pass_bar_threshold,
            step_deviation=self.step_max_loss,
            raster=self.step_length_raster,
            min_piece=self.step_min_piece,
            min_bar=min_bar_length)

        placements: list[AllplanReinf.BarPlacement] = []

        for positions, piece in groups:
            placements.append(
                self._place_contour_piece(layer, run_axis, piece, positions))

        layer.placements = placements

        return placements




    def _lap_pieces(self,
                    segment: tuple[float, float],
                    layer: LayerConfig,
                    preferred_shift: float,
                    forbidden_zones: list[tuple[float, float]]) -> list[tuple[float, float]]:
        """Zerlegt ein Stabsegment in gestossene Teilstäbe."""

        lap_length = self.overlap_factor * layer.diameter

        if self.max_bar_length <= lap_length:
            if not self._lap_warning_shown:
                print(f'SlabReinforcement: max. Stablänge {self.max_bar_length} ist nicht '
                      f'größer als die Übergreifungslänge {lap_length} — es wird nicht gestossen')
                self._lap_warning_shown = True

            return [segment]

        return split_with_preferred_joints(segment,
                                           self.max_bar_length,
                                           lap_length,
                                           preferred_shift=preferred_shift,
                                           forbidden_zones=forbidden_zones,
                                           min_piece_length=2 * lap_length)


    def _lap_forbidden_zones(self,
                             run_axis: int,
                             positions: list[float]) -> list[tuple[float, float]]:
        """Sperrzonen für Stossfugen: Bereiche der Öffnungen, die von diesem
        Verlegelauf gekreuzt werden, zuzüglich Sicherheitsabstand.
        """

        if not self.contour_openings or self.lap_opening_margin <= 0:
            return []

        dist_axis = 1 - run_axis
        run_from, run_to = positions[0], positions[-1]

        zones = []

        for opening in self.contour_openings:
            bbox = loop_bbox(opening)

            if bbox[dist_axis + 2] < run_from or bbox[dist_axis] > run_to:
                continue

            zones.append((bbox[run_axis] - self.lap_opening_margin,
                          bbox[run_axis + 2] + self.lap_opening_margin))

        return zones


    def _place_contour_piece(self,
                             layer: LayerConfig,
                             run_axis: int,
                             piece: tuple[float, float],
                             positions: list[float]) -> AllplanReinf.BarPlacement:
        """Erzeugt das Placement eines Teilstabes über die gegebenen
        Scan-Positionen.
        """

        piece_from, piece_to = piece

        # Nettolänge: die Deckung steckt bereits in den Segmentgrenzen.
        # Liegt ein Ende auf einer Randkante mit angebogenem Bügel, wird der
        # Stab als Freiform mit vollem U-Bügel aufgebaut.
        start_leg, end_leg = self._piece_hooks(layer, piece, positions)

        if start_leg > 0 or end_leg > 0:
            shape = self._create_bar_with_edge_stirrups(layer, piece_to - piece_from,
                                                        start_leg, end_leg)
        else:
            shape = self._create_straight_bar_shape(layer, piece_to - piece_from, 0.0, 0.0)

        first = positions[0]

        # Abstand und Anzahl sind aus den Scan-Positionen exakt bekannt,
        # deshalb wird über Startpunkt/Abstand/Anzahl verlegt: so liegt der
        # erste Stab exakt auf der ersten Scan-Position (kein Nachzentrieren
        # wie bei der from_to-Variante, die bei einem Rest beide Enden
        # gleichmäßig aufweitet)
        spacing = (positions[1] - first) if len(positions) > 1 else layer.spacing

        if run_axis == 0:
            from_pnt = self._pnt(piece_from, first, layer.z_axis)
            direction_pnt = self._pnt(piece_from, first + spacing, layer.z_axis)
        else:
            from_pnt = self._pnt(first, piece_from, layer.z_axis)
            direction_pnt = self._pnt(first + spacing, piece_from, layer.z_axis)

        placement = LinearBarBuilder.create_linear_bar_placement_from_by_dist_count(
            self._next_position(), shape, from_pnt, direction_pnt,
            0.0, spacing, len(positions))

        self._set_placement_layer(placement, layer.allplan_layer)

        return placement
