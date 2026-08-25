"""Tests der Lagerichtung — Variante 1 muss die 1./4. Lage senkrecht (Y)
legen, Variante 2 waagrecht (X)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'PythonPartsScripts' / 'SlabReinforcement'))

from layer_scheme import (LAYER_SCHEME_OUTER_X, LAYER_SCHEME_OUTER_Y,
                          layer_scheme_value, outer_direction)


class LayerSchemeTest(unittest.TestCase):

    def test_variante_1_legt_die_aeusseren_lagen_in_y(self):
        self.assertEqual(layer_scheme_value('Variante 1'), LAYER_SCHEME_OUTER_Y)
        self.assertEqual(outer_direction('Variante 1'), 'Y')

    def test_variante_2_legt_die_aeusseren_lagen_in_x(self):
        self.assertEqual(layer_scheme_value('Variante 2'), LAYER_SCHEME_OUTER_X)
        self.assertEqual(outer_direction('Variante 2'), 'X')

    def test_alte_zahlenwerte_bleiben_lesbar(self):
        for raw in (1, '1', 1.0, ' 1 '):
            self.assertEqual(outer_direction(raw), 'Y', raw)

        for raw in (2, '2', 2.0):
            self.assertEqual(outer_direction(raw), 'X', raw)

    def test_unbekannter_wert_faellt_auf_variante_2_zurueck(self):
        for raw in ('', None, 'X-Richtung', 0, 7, 'Variante'):
            self.assertEqual(outer_direction(raw), 'X', raw)


if __name__ == '__main__':
    unittest.main()
