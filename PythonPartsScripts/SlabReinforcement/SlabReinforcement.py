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

# Nachbarmodule im selben Ordner: relativer Import wie im offiziellen
# Beispiel (ArchitectureExamples/Objects/DoorOpening.py: "from .OpeningBase
# import OpeningBase"). Ein absoluter Import "from SlabReinforcement.x"
# scheitert, sobald Allplan dieses Skript selbst als Modul
# "SlabReinforcement" lädt (Namenskollision Modul <-> Ordner).
# Der Fallback greift, falls das Skript ohne Paketkontext geladen wird.
try:
    from .contour_placement import (compute_contour_bars, group_bars_into_runs,
                                    loop_area, split_closed_loops)
    from .opening_clipping import (compute_edge_bar_runs, compute_edge_strip_segments,
                                   compute_placement_bands)
except ImportError:
    import os
    import sys

    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

    from contour_placement import (compute_contour_bars, group_bars_into_runs,
                                   loop_area, split_closed_loops)
    from opening_clipping import (compute_edge_bar_runs, compute_edge_strip_segments,
                                  compute_placement_bands)

if TYPE_CHECKING:
    from __BuildingElementStubFiles.SlabReinforcementBuildingElement import \
        SlabReinforcementBuildingElement as BuildingElement  # type: ignore
else:
    from BuildingElement import BuildingElement

SCRIPT_VERSION = '0.3.1'

# Erscheint im Allplan-Trace-Fenster beim Laden — damit im Zweifel erkennbar
# ist, welche Skriptversion Allplan tatsächlich geladen hat
print(f'Load SlabReinforcement.py (Version {SCRIPT_VERSION})')

# Optionen der Seiten-Combos (müssen den ValueList-Einträgen der .pyp entsprechen)
SIDE_STIRRUP = 'Randbügel'
SIDE_CONNECT = 'Anschlusseisen'
SIDE_SEPARATE = 'Separate Anschlusseisen'
SIDE_NONE = 'Keine'

# Optionen des Eingabemodus (ValueList von InputMethod in der .pyp)
INPUT_RECT = 'Rechteck (Drag)'
INPUT_POLYGON = 'Polygon zeichnen'
INPUT_ELEMENT = 'Element wählen'


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
    cover: float         # Betondeckung zur maßgebenden Plattenoberfläche [mm]
    steel_grade: int     # Index der Stahlgüte (Allplan-Tabelle)
    z_clear: float = 0.0  # lichter Abstand Stabunterkante zu OK Rohdecke unten (z=0)
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
        self.sel_result = SingleElementSelectResult()

        self.placement_pnt = AllplanGeo.Point3D()
        self.contour: list[tuple[float, float]] | None = None
        self.openings: list[list[tuple[float, float]]] = []
        self.z_offset = 0.0
        self.thickness_override: float | None = None

        # Solange False, liefert execute() ein leeres Ergebnis — sonst würde
        # während der Eingabe bereits eine Platte am Nullpunkt erscheinen
        self.input_finished = False


    def start_input(self):
        """Ersteingabe je nach gewähltem Eingabemodus starten."""

        build_ele = self.build_ele

        build_ele.InputMode.value = build_ele.INPUT_MODE_INPUT

        # Ergebnisse einer vorherigen Eingabe verwerfen (Moduswechsel)
        self.input_finished = False
        self.contour = None
        self.openings = []
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

        input_method = build_ele.InputMethod.value

        if input_method == INPUT_ELEMENT:
            self._process_selected_element()
        elif input_method == INPUT_POLYGON:
            self._process_drawn_polygons()
        else:
            self.placement_pnt = self.point_result.input_point

        build_ele.InputMode.value = build_ele.INPUT_MODE_CREATION

        self.script_object_interactor = None
        self.input_finished = True

        print(f'SlabReinforcement: Eingabe abgeschlossen — '
              f'Kontur: {"ja" if self.contour else "nein (Rechteck)"}, '
              f'Öffnungen: {len(self.openings)}')


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


    def _process_drawn_polygons(self):
        """Gezeichnete Polygone übernehmen: größte Fläche = Kontur,
        alle weiteren Loops = Öffnungen.
        """

        input_polygon = self.polygon_result.input_polygon

        polygons = input_polygon if isinstance(input_polygon, list) else [input_polygon]

        points: list[tuple[float, float]] = []

        for polygon in polygons:
            converted = AllplanGeo.ConvertTo2D(polygon)
            polygon_2d = converted[1] if isinstance(converted, tuple) else converted

            points += [(p.X, p.Y) for p in polygon_2d.Points]

        self._set_contour_from_loops(split_closed_loops(points))


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
        self.openings = loops[1:]


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
        self.openings = []


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

        self.side_cover = build_ele.SideCover.value
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

        self.position_counter = 0

        self.layers = self._create_layer_configs()

        # Öffnungsdaten des Rechteckmodus (eine rechteckige Öffnung)
        self.has_opening = build_ele.HasOpening.value and self.contour is None
        self.opening_x = (build_ele.OpeningX.value,
                          build_ele.OpeningX.value + build_ele.OpeningWidth.value)
        self.opening_y = (build_ele.OpeningY.value,
                          build_ele.OpeningY.value + build_ele.OpeningHeight.value)

        if self.has_opening and (build_ele.OpeningWidth.value <= 0 or build_ele.OpeningHeight.value <= 0):
            print('SlabReinforcement: Öffnung mit Breite/Höhe <= 0 wird ignoriert')
            self.has_opening = False


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
                               build_ele.BottomXCover.value,
                               build_ele.BottomXSteelGrade.value)
        bottom_y = LayerConfig('Bewehrung unten Y', 'Y', False,
                               build_ele.BottomYDiameter.value,
                               build_ele.BottomYSpacing.value,
                               build_ele.BottomYCover.value,
                               build_ele.BottomYSteelGrade.value)
        top_x = LayerConfig('Bewehrung oben X', 'X', True,
                            build_ele.TopXDiameter.value,
                            build_ele.TopXSpacing.value,
                            build_ele.TopXCover.value,
                            build_ele.TopXSteelGrade.value)
        top_y = LayerConfig('Bewehrung oben Y', 'Y', True,
                            build_ele.TopYDiameter.value,
                            build_ele.TopYSpacing.value,
                            build_ele.TopYCover.value,
                            build_ele.TopYSteelGrade.value)

        if build_ele.SameDiameterForAll.value:
            for layer in (bottom_x, bottom_y, top_x, top_y):
                layer.diameter = float(build_ele.DiaAll.value)
                layer.spacing = build_ele.SpacingAll.value

        bottom_x.allplan_layer = build_ele.LayerBottomX.value
        bottom_y.allplan_layer = build_ele.LayerBottomY.value
        top_x.allplan_layer = build_ele.LayerTopX.value
        top_y.allplan_layer = build_ele.LayerTopY.value

        # lichte Abstände der Stabunterkanten zur Plattenunterkante (z=0);
        # die äußere Richtung liegt direkt auf/unter der Deckung
        if build_ele.OuterLayerDirection.value == 'X-Richtung':
            bottom_outer, bottom_inner = bottom_x, bottom_y
            top_outer, top_inner = top_x, top_y
        else:
            bottom_outer, bottom_inner = bottom_y, bottom_x
            top_outer, top_inner = top_y, top_x

        bottom_outer.z_clear = bottom_outer.cover
        bottom_inner.z_clear = bottom_inner.cover + bottom_outer.diameter
        top_outer.z_clear = self.thickness - top_outer.cover - top_outer.diameter
        top_inner.z_clear = self.thickness - top_inner.cover - top_outer.diameter - top_inner.diameter

        layers = [bottom_outer, bottom_inner, top_inner, top_outer]

        # Plausibilität der Höhenlagen: bei dünner Platte und großen
        # Durchmessern können sich obere und untere Lagen durchdringen oder
        # aus der Platte herausfallen — betroffene obere Lagen entfallen dann
        # mit Warnung, statt falsche Bewehrung zu erzeugen
        bottom_layer_top = bottom_inner.z_clear + bottom_inner.diameter

        valid_layers = []

        for layer in layers:
            if layer.z_clear < 0 or (layer.is_top and layer.z_clear < bottom_layer_top):
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
        model_ele_list.append_geometry_3d(self._create_view_geometry())

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
            if any(side != SIDE_NONE for side in (self.side_left, self.side_right,
                                                  self.side_bottom, self.side_top)):
                print('SlabReinforcement: Randbügel/Anschlusseisen werden im '
                      'Polygon-/Elementmodus (noch) nicht erzeugt')

            for layer in self.layers:
                for placement in self._create_contour_layer_placements(layer):
                    reinf_ele_list.append(placement)

            handle_list = HandleList()

        if self.build_ele.IsPythonPart.value:
            pyp_util = PythonPartUtil()
            pyp_util.add_pythonpart_view_2d3d(model_ele_list)
            pyp_util.add_reinforcement_elements(reinf_ele_list)

            return CreateElementResult(pyp_util.create_pythonpart(self.build_ele), handle_list)

        return CreateElementResult(elements=model_ele_list + reinf_ele_list,
                                   handles=handle_list)


    def _create_view_geometry(self):
        """Ansichtsgeometrie: Rechteckmodus ein Plattenkörper (Öffnung wird,
        wenn möglich, boolesch abgezogen); Konturmodus die Konturpolygone
        auf Höhe der Plattenunterkante.
        """

        if self.contour is None:
            slab = AllplanGeo.Polyhedron3D.CreateCuboid(
                AllplanGeo.AxisPlacement3D(self._pnt(0, 0)),
                self.length, self.width, self.thickness)

            if not self.has_opening:
                return slab

            opening = AllplanGeo.Polyhedron3D.CreateCuboid(
                AllplanGeo.AxisPlacement3D(self._pnt(self.opening_x[0], self.opening_y[0], -1.0)),
                self.opening_x[1] - self.opening_x[0],
                self.opening_y[1] - self.opening_y[0],
                self.thickness + 2.0)

            err, slab_with_opening = AllplanGeo.MakeSubtraction(slab, opening)

            if err != AllplanGeo.eGeometryErrorCode.eOK or slab_with_opening is None:
                return slab

            return slab_with_opening

        polygon = AllplanGeo.Polygon3D()

        for x, y in self.contour:
            polygon += AllplanGeo.Point3D(x, y, self.base_z)

        polygon += AllplanGeo.Point3D(self.contour[0][0], self.contour[0][1], self.base_z)

        return polygon


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

        Die Höhenlage wird über die "bottom"-Deckung eingestellt: Sie ist der
        lichte Abstand der Stabunterkante zur Placement-Ebene, analog zur
        Längsbewehrung im offiziellen BarPlacement-Beispiel.

        Das Shape entsteht im lokalen XY-System (Stab entlang lokal X, die
        bottom-Deckung versetzt in lokal +Y). Die erste 90°-Drehung um X kippt
        den Deckungsversatz nach global +Z, die zweite Drehung um Z stellt die
        Stabrichtung ein — wie RotationUtil(90, 0, 90) im BarPlacement-Beispiel.
        """

        model_angles = RotationUtil(90, 0, 0) if layer.direction == 'X' else RotationUtil(90, 0, 90)

        cover_props = ConcreteCoverProperties.left_right_bottom(cover_start,
                                                                cover_end,
                                                                layer.z_clear)

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
        min_segment_length = max(self.build_ele.MinBarLength.value,
                                 2 * self.side_cover + 10)

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
                cover_start = 0.0 if ae_start else self.side_cover
                cover_end = 0.0 if ae_end else self.side_cover

                shape = self._create_straight_bar_shape(layer,
                                                        run_to - run_from + ae_start + ae_end,
                                                        cover_start, cover_end)

                run_origin = run_from - ae_start

                if layer.direction == 'X':
                    from_pnt = self._pnt(run_origin, band.dist_from)
                    to_pnt = self._pnt(run_origin, band.dist_to)
                else:
                    from_pnt = self._pnt(band.dist_from, run_origin)
                    to_pnt = self._pnt(band.dist_to, run_origin)

                # Verteil-Deckung nur an echten Plattenrändern, nicht an
                # Bandgrenzen mitten in der Platte
                place_cover_from = self.side_cover if band.dist_from == 0 else 0
                place_cover_to = self.side_cover if band.dist_to == dist_len else 0

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
                    placement = LinearBarBuilder.create_linear_bar_placement_from_to_by_dist(
                        self._next_position(),
                        AllplanReinf.BendingShape(shape),
                        region_from,
                        region_to,
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

        bottom_base = max(layer.z_clear + layer.diameter for layer in bottom_mains) if bottom_mains else None
        top_base = min(layer.z_clear for layer in top_mains) if top_mains else None

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
                                         main_layer.cover,
                                         main_layer.steel_grade)

                if is_top:
                    edge_layer.z_clear = top_base - (stack_index + 1) * edge_diameter
                else:
                    edge_layer.z_clear = bottom_base + stack_index * edge_diameter

                if edge_layer.z_clear < 0 or \
                        (is_top and bottom_base is not None and edge_layer.z_clear < bottom_base):
                    print(f'SlabReinforcement: Zulage "{edge_layer.name}" entfällt — '
                          f'kein Platz innerhalb der Hauptlagen')
                    continue

                edge_layer.bending_roller = AllplanReinf.BendingRollerService.GetBendingRollerFactor(
                    edge_layer.diameter, edge_layer.steel_grade, -1, False)

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
                                             opening_run, lap_length, zone_width):
                cover_start = self.side_cover if run.run_from == 0 else 0
                cover_end = self.side_cover if run.run_to == run_len else 0

                shape = self._create_straight_bar_shape(edge_layer,
                                                        run.run_to - run.run_from,
                                                        cover_start, cover_end)

                if edge_layer.direction == 'X':
                    from_pnt = self._pnt(run.run_from, run.dist_from)
                    to_pnt = self._pnt(run.run_from, run.dist_to)
                else:
                    from_pnt = self._pnt(run.dist_from, run.run_from)
                    to_pnt = self._pnt(run.dist_to, run.run_from)

                placements.append(
                    LinearBarBuilder.create_linear_bar_placement_from_to_by_count(
                        self._next_position(),
                        shape,
                        from_pnt,
                        to_pnt,
                        0,
                        0,
                        bar_count))

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
                            from_pnt = self._pnt(run_pos, dist_from)
                            to_pnt = self._pnt(run_pos, dist_to)
                        else:
                            from_pnt = self._pnt(dist_from, run_pos)
                            to_pnt = self._pnt(dist_to, run_pos)

                        placement = LinearBarBuilder.create_linear_bar_placement_from_to_by_dist(
                            self._next_position(),
                            shape,
                            from_pnt,
                            to_pnt,
                            self.side_cover if dist_from == 0 else 0,
                            self.side_cover if dist_to == dist_len else 0,
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

            # Außenmaß über beide Lagen, auf ganze cm abgerundet; für den
            # ShapeBuilder wird das Achsmaß (Außenmaß − Ø) übergeben
            outer_height = (top_layer.z_clear + top_layer.diameter) - bottom_layer.z_clear
            web_height = int(outer_height / 10.0) * 10.0 - diameter
            leg_length = self.overlap_factor * diameter - 0.5 * diameter

            if web_height <= 0 or leg_length <= 0:
                print(f'SlabReinforcement: Randbügel {direction} entfallen — '
                      f'Bügelhöhe/Schenkellänge nicht darstellbar')
                continue

            z_pos = bottom_layer.z_clear + diameter / 2.0

            shape_props = ReinforcementShapeProperties.rebar(
                diameter, bottom_layer.bending_roller, bottom_layer.steel_grade,
                self.concrete_grade, AllplanReinf.BendingShapeType.OpenStirrup)

            no_cover = ConcreteCoverProperties(0.0, 0.0, 0.0, 0.0)

            stirrup_layer_id = self.build_ele.LayerStirrupX.value if direction == 'X' \
                else self.build_ele.LayerStirrupY.value

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
                    edge_pos = self.side_cover if at_start else self.length - self.side_cover
                else:
                    angles = RotationAngles(0, -90, 0) if at_start else RotationAngles(0, -90, 180)
                    edge_pos = self.side_cover if at_start else self.width - self.side_cover

                shape = GeneralShapeBuilder.create_open_stirrup(
                    web_height, leg_length, angles, shape_props, no_cover,
                    -1, -1, 0.0, 0.0)

                if not shape.IsValid():
                    print(f'SlabReinforcement: Randbügel-Shape {direction} ungültig — übersprungen')
                    continue

                # Verlegestrecke unterbrechen, wo die Öffnung den Randstreifen
                # (Bügelschenkel-Tiefe ab Kante) schneidet
                strip_depth = self.side_cover + leg_length
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
                        self.side_cover if dist_from == 0 else 0,
                        self.side_cover if dist_to == dist_len else 0,
                        bottom_layer.spacing)

                    self._set_placement_layer(placement, stirrup_layer_id)
                    placements.append(placement)

        return placements


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

        bars = compute_contour_bars(
            self.contour, self.contour_openings, run_axis,
            layer.spacing, self.side_cover, min_bar_length,
            edge_zone_length=self.edge_zone_length if self.edge_zones_active else 0.0,
            edge_zone_spacing=self.edge_zone_spacing if self.edge_zones_active else 0.0)

        placements: list[AllplanReinf.BarPlacement] = []

        for run in group_bars_into_runs(bars):
            for seg_from, seg_to in run.segments:
                shape = self._create_straight_bar_shape(layer, seg_to - seg_from,
                                                        self.side_cover, self.side_cover)

                first, last = run.positions[0], run.positions[-1]

                if len(run.positions) == 1:
                    # Einzelstab: halben Lagenabstand als Verlegefenster,
                    # der Stab landet mittig exakt auf der Scan-Position
                    window = layer.spacing / 2.0

                    if run_axis == 0:
                        from_pnt = self._pnt(seg_from, first - window)
                        to_pnt = self._pnt(seg_from, first + window)
                    else:
                        from_pnt = self._pnt(first - window, seg_from)
                        to_pnt = self._pnt(first + window, seg_from)

                    placement = LinearBarBuilder.create_linear_bar_placement_from_to_by_count(
                        self._next_position(),
                        shape,
                        from_pnt,
                        to_pnt,
                        0,
                        0,
                        1)
                else:
                    if run_axis == 0:
                        from_pnt = self._pnt(seg_from, first)
                        to_pnt = self._pnt(seg_from, last)
                    else:
                        from_pnt = self._pnt(first, seg_from)
                        to_pnt = self._pnt(last, seg_from)

                    placement = LinearBarBuilder.create_linear_bar_placement_from_to_by_dist(
                        self._next_position(),
                        shape,
                        from_pnt,
                        to_pnt,
                        0,
                        0,
                        run.spacing)

                self._set_placement_layer(placement, layer.allplan_layer)
                placements.append(placement)

        layer.placements = placements

        return placements
