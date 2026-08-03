"""SlabReinforcement — automatische Flächenbewehrung für Flachdecken.

PythonPart für Allplan 2026. Erzeugt für eine rechteckige Platte vier
Bewehrungslagen (oben/unten, jeweils X- und Y-Richtung) als lineare
Stabplatzierungen. Optional wird eine rechteckige Öffnung berücksichtigt:
Die Hauptstäbe werden im Öffnungsbereich gekappt und die Öffnung erhält
umlaufende Randverstärkungsstäbe.

Aufbau nach dem Muster der offiziellen Beispiele
(NemetschekAllplan/PythonPartsExamples, Branch 2026,
ReinforcementExamples/BarPlacement/BarPlacement.py).

Alle Längenangaben in mm (Allplan-Standardeinheit).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import NemAll_Python_Geometry as AllplanGeo
import NemAll_Python_IFW_ElementAdapter as AllplanEleAdapter
import NemAll_Python_Reinforcement as AllplanReinf
import StdReinfShapeBuilder.GeneralReinfShapeBuilder as GeneralShapeBuilder
import StdReinfShapeBuilder.LinearBarPlacementBuilder as LinearBarBuilder
from CreateElementResult import CreateElementResult
from PythonPartUtil import PythonPartUtil
from StdReinfShapeBuilder.ConcreteCoverProperties import ConcreteCoverProperties
from StdReinfShapeBuilder.ReinforcementShapeProperties import ReinforcementShapeProperties
from TypeCollections.ModelEleList import ModelEleList
from Utils.RotationUtil import RotationUtil

from SlabReinforcement.opening_clipping import compute_placement_bands, compute_edge_bar_runs

if TYPE_CHECKING:
    from __BuildingElementStubFiles.SlabReinforcementBuildingElement import \
        SlabReinforcementBuildingElement as BuildingElement  # type: ignore
else:
    from BuildingElement import BuildingElement

print('Load SlabReinforcement.py')


def check_allplan_version(_build_ele: BuildingElement,
                          _version: str) -> bool:
    """Prüfung der Allplan-Version — entwickelt und getestet für Allplan >= 2026,
    die verwendeten APIs existieren aber unverändert seit 2025.
    """

    return True


def create_element(build_ele: BuildingElement,
                   doc: AllplanEleAdapter.DocumentAdapter) -> CreateElementResult:
    """Elementerzeugung — wird von Allplan bei jeder Parameteränderung erneut
    aufgerufen (Live-Vorschau) und beim Absetzen für das endgültige Element.
    """

    return SlabReinforcement(build_ele, doc).create()


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

    placements: list = field(default_factory=list)


class SlabReinforcement():
    """Erzeugt die Deckenbewehrung aus den Palettenparametern."""

    def __init__(self,
                 build_ele: BuildingElement,
                 doc: AllplanEleAdapter.DocumentAdapter):
        self.build_ele = build_ele
        self.document = doc

        self.length = build_ele.SlabLength.value
        self.width = build_ele.SlabWidth.value
        self.thickness = build_ele.SlabThickness.value

        self.side_cover = build_ele.SideCover.value
        self.concrete_grade = build_ele.ConcreteGrade.value

        self.position_counter = 0

        self.layers = self._create_layer_configs()

        # Öffnungsdaten (nur eine rechteckige Öffnung in v0.2)
        self.has_opening = build_ele.HasOpening.value
        self.opening_x = (build_ele.OpeningX.value,
                          build_ele.OpeningX.value + build_ele.OpeningWidth.value)
        self.opening_y = (build_ele.OpeningY.value,
                          build_ele.OpeningY.value + build_ele.OpeningHeight.value)

        if self.has_opening and (build_ele.OpeningWidth.value <= 0 or build_ele.OpeningHeight.value <= 0):
            print('SlabReinforcement: Öffnung mit Breite/Höhe <= 0 wird ignoriert')
            self.has_opening = False


    def _next_position(self) -> int:
        """Nächste freie Positionsnummer (Markennummer)."""

        self.position_counter += 1
        return self.position_counter


    def _create_layer_configs(self) -> list[LayerConfig]:
        """Liest die vier Lagen aus der Palette und berechnet ihre Höhenlage.

        Lagenreihenfolge (Konvention dieses PythonParts, siehe README):
        unten liegt die X-Lage außen (direkt auf der Deckung), die Y-Lage
        darüber; oben liegt die X-Lage außen (direkt unter der Deckung),
        die Y-Lage darunter.
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

        # lichte Abstände der Stabunterkanten zur Plattenunterkante (z=0):
        bottom_x.z_clear = bottom_x.cover
        bottom_y.z_clear = bottom_y.cover + bottom_x.diameter
        top_x.z_clear = self.thickness - top_x.cover - top_x.diameter
        top_y.z_clear = self.thickness - top_y.cover - top_x.diameter - top_y.diameter

        layers = [bottom_x, bottom_y, top_x, top_y]

        # Plausibilität der Höhenlagen: bei dünner Platte und großen
        # Durchmessern können sich obere und untere Lagen durchdringen oder
        # aus der Platte herausfallen — betroffene obere Lagen entfallen dann
        # mit Warnung, statt falsche Bewehrung zu erzeugen
        bottom_layer_top = bottom_y.z_clear + bottom_y.diameter

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


    def create(self) -> CreateElementResult:
        """Erzeugt Plattenkörper (Ansichtsgeometrie) und alle Placements."""

        model_ele_list = ModelEleList(self.build_ele.CommonProp.value)
        model_ele_list.append_geometry_3d(self._create_slab_geometry())

        reinf_ele_list = ModelEleList()

        for layer in self.layers:
            for placement in self._create_layer_placements(layer):
                reinf_ele_list.append(placement)

        if self.has_opening and self.build_ele.EdgeReinfActive.value:
            for placement in self._create_opening_edge_reinforcement():
                reinf_ele_list.append(placement)

        if self.build_ele.IsPythonPart.value:
            pyp_util = PythonPartUtil()
            pyp_util.add_pythonpart_view_2d3d(model_ele_list)
            pyp_util.add_reinforcement_elements(reinf_ele_list)

            return CreateElementResult(pyp_util.create_pythonpart(self.build_ele))

        return CreateElementResult(elements=model_ele_list + reinf_ele_list)


    def _create_slab_geometry(self) -> AllplanGeo.Polyhedron3D:
        """Plattenkörper für die Vorschau; die Öffnung wird, wenn möglich,
        boolesch abgezogen — schlägt die Subtraktion fehl, bleibt der
        Vollquader (rein optisch, ohne Einfluss auf die Bewehrung).
        """

        slab = AllplanGeo.Polyhedron3D.CreateCuboid(self.length, self.width, self.thickness)

        if not self.has_opening:
            return slab

        opening = AllplanGeo.Polyhedron3D.CreateCuboid(
            AllplanGeo.AxisPlacement3D(AllplanGeo.Point3D(self.opening_x[0], self.opening_y[0], -1.0)),
            self.opening_x[1] - self.opening_x[0],
            self.opening_y[1] - self.opening_y[0],
            self.thickness + 2.0)

        err, slab_with_opening = AllplanGeo.MakeSubtraction(slab, opening)

        if err != AllplanGeo.eGeometryErrorCode.eOK or slab_with_opening is None:
            return slab

        return slab_with_opening


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
        lichte Abstand der Stabunterkante zur Placement-Ebene (z=0), analog zur
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


    def _create_layer_placements(self, layer: LayerConfig) -> list[AllplanReinf.BarPlacement]:
        """Erzeugt die Placements einer Lage, bei aktiver Öffnung bandweise
        mit gekappten Stäben links/rechts der Öffnung.
        """

        if layer.diameter <= 0 or layer.spacing <= 0:
            return []

        if layer.direction == 'X':
            run_len, dist_len = self.length, self.width
            opening_run, opening_dist = self.opening_x, self.opening_y
        else:
            run_len, dist_len = self.width, self.length
            opening_run, opening_dist = self.opening_y, self.opening_x

        if not self.has_opening:
            opening_run = opening_dist = None

        # Reststäbe unterhalb der konfigurierten Mindestlänge (mindestens aber
        # beidseitige Deckung + 10 mm Reststab) entfallen ersatzlos
        min_segment_length = max(self.build_ele.MinBarLength.value,
                                 2 * self.side_cover + 10)

        bands = compute_placement_bands(dist_len, run_len, opening_dist, opening_run,
                                        min_segment_length=min_segment_length)

        placements: list[AllplanReinf.BarPlacement] = []

        for band in bands:
            for run_from, run_to in band.run_segments:
                # Deckung an den Stabenden: Plattenrand -> seitliche Deckung,
                # Öffnungsrand -> ebenfalls seitliche Deckung (konfigurierbar
                # über denselben Parameter, bewusst keine Norm-Annahme)
                cover_start = self.side_cover
                cover_end = self.side_cover

                shape = self._create_straight_bar_shape(layer, run_to - run_from,
                                                        cover_start, cover_end)

                if layer.direction == 'X':
                    from_pnt = AllplanGeo.Point3D(run_from, band.dist_from, 0)
                    to_pnt = AllplanGeo.Point3D(run_from, band.dist_to, 0)
                else:
                    from_pnt = AllplanGeo.Point3D(band.dist_from, run_from, 0)
                    to_pnt = AllplanGeo.Point3D(band.dist_to, run_from, 0)

                # Verteil-Deckung nur an echten Plattenrändern, nicht an
                # Bandgrenzen mitten in der Platte
                place_cover_from = self.side_cover if band.dist_from == 0 else 0
                place_cover_to = self.side_cover if band.dist_to == dist_len else 0

                placements.append(
                    LinearBarBuilder.create_linear_bar_placement_from_to_by_dist(
                        self._next_position(),
                        shape,
                        from_pnt,
                        to_pnt,
                        place_cover_from,
                        place_cover_to,
                        layer.spacing))

        layer.placements = placements

        return placements


    def _create_opening_edge_reinforcement(self) -> list[AllplanReinf.BarPlacement]:
        """Randverstärkung um die Öffnung: je Öffnungskante eine Schar
        Zulagestäbe parallel zur Kante, mit beidseitigem Überstand um die
        (konfigurierbare) Übergreifungslänge. Die Stäbe werden in Höhe der
        jeweiligen Haupt-Lagen (unten und oben) eingebaut.
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
                    from_pnt = AllplanGeo.Point3D(run.run_from, run.dist_from, 0)
                    to_pnt = AllplanGeo.Point3D(run.run_from, run.dist_to, 0)
                else:
                    from_pnt = AllplanGeo.Point3D(run.dist_from, run.run_from, 0)
                    to_pnt = AllplanGeo.Point3D(run.dist_to, run.run_from, 0)

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
