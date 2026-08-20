"""Tests der Zustandssicherung eines abgesetzten PythonParts."""

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..',
                                'PythonPartsScripts', 'SlabReinforcement'))

from state_persistence import STATE_VERSION, decode_state, encode_state  # noqa: E402


RECHTECK = ((1234.56, -789.04, 300.0), None, [], [], 0.0, None)


class TestRoundTrip(unittest.TestCase):
    """Was gesichert wurde, muss unveraendert zurueckkommen."""

    def test_absetzpunkt_ueberlebt(self):
        state = decode_state(encode_state(*RECHTECK))

        self.assertIsNotNone(state)
        self.assertAlmostEqual(state['placement_pnt'][0], 1234.6)
        self.assertAlmostEqual(state['placement_pnt'][1], -789.0)
        self.assertAlmostEqual(state['placement_pnt'][2], 300.0)

    def test_kontur_ueberlebt(self):
        contour = [(0.0, 0.0), (5000.0, 0.0), (5000.0, 4000.0), (0.0, 4000.0)]
        state = decode_state(encode_state((0, 0, 0), contour, [], [], 0.0, None))

        self.assertEqual(state['contour'], contour)

    def test_aussparungen_bleiben_getrennt(self):
        detected = [[(1000.0, 1000.0), (1500.0, 1000.0), (1500.0, 1500.0)]]
        drawn = [[(2000.0, 2000.0), (2500.0, 2000.0), (2500.0, 2500.0)],
                 [(3000.0, 3000.0), (3200.0, 3000.0), (3200.0, 3200.0)]]

        state = decode_state(encode_state((0, 0, 0), None, detected, drawn, 0.0, None))

        self.assertEqual(state['detected_openings'], detected)
        self.assertEqual(state['drawn_openings'], drawn)

    def test_hoehenlage_und_dicke_ueberleben(self):
        state = decode_state(encode_state((0, 0, 0), None, [], [], 250.0, 220.0))

        self.assertAlmostEqual(state['z_offset'], 250.0)
        self.assertAlmostEqual(state['thickness_override'], 220.0)

    def test_fehlende_dicke_bleibt_none(self):
        """None heisst 'Dicke aus der Palette' — darf nicht zu 0.0 werden."""

        state = decode_state(encode_state((0, 0, 0), None, [], [], 0.0, None))

        self.assertIsNone(state['thickness_override'])

    def test_waende_ueberleben(self):
        walls = [[(1000.0, 2000.0), (4000.0, 2000.0),
                  (4000.0, 2240.0), (1000.0, 2240.0)]]
        state = decode_state(encode_state((0, 0, 0), None, [], [], 0.0, None,
                                          walls=walls))

        self.assertEqual(state['walls'], walls)

    def test_alter_stand_ohne_waende_liefert_leere_liste(self):
        # Stand aus einer Fassung vor dem Wandanschluss
        raw = encode_state((0, 0, 0), None, [], [], 0.0, None)
        state = decode_state(raw.replace(',"walls":[]', ''))

        self.assertEqual(state['walls'], [])

    def test_leere_kontur_bleibt_none(self):
        """None unterscheidet den Rechteck- vom Konturmodus."""

        state = decode_state(encode_state((0, 0, 0), None, [], [], 0.0, None))

        self.assertIsNone(state['contour'])

    def test_rundung_bleibt_unter_zehntelmillimeter(self):
        contour = [(0.04, 0.06), (4999.94, 0.0)]
        state = decode_state(encode_state((0, 0, 0), contour, [], [], 0.0, None))

        for (gx, gy), (rx, ry) in zip(contour, state['contour']):
            self.assertLess(abs(gx - rx), 0.05)
            self.assertLess(abs(gy - ry), 0.05)


class TestRobustheit(unittest.TestCase):
    """Unbrauchbare Staende muessen None liefern, nicht abstuerzen."""

    def test_leerer_parameter(self):
        self.assertIsNone(decode_state(''))
        self.assertIsNone(decode_state(None))

    def test_kein_json(self):
        self.assertIsNone(decode_state('kein json'))

    def test_fremde_fassung_wird_verworfen(self):
        raw = json.dumps({'v': STATE_VERSION + 1, 'pnt': [0, 0, 0]})

        self.assertIsNone(decode_state(raw))

    def test_fehlender_punkt(self):
        self.assertIsNone(decode_state(json.dumps({'v': STATE_VERSION})))

    def test_unvollstaendiger_punkt(self):
        raw = json.dumps({'v': STATE_VERSION, 'pnt': [0, 0]})

        self.assertIsNone(decode_state(raw))

    def test_kaputte_koordinate(self):
        raw = json.dumps({'v': STATE_VERSION, 'pnt': [0, 0, 0],
                          'contour': [[0, 0], ['x', 1]]})

        self.assertIsNone(decode_state(raw))

    def test_liste_statt_objekt(self):
        self.assertIsNone(decode_state(json.dumps([1, 2, 3])))


class TestGroesse(unittest.TestCase):
    """Der Stand landet in einem Palettenparameter — er muss kurz bleiben."""

    def test_grosse_kontur_bleibt_handhabbar(self):
        contour = [(i * 137.7, i * 91.3) for i in range(60)]
        raw = encode_state((0, 0, 0), contour, [], [], 0.0, None)

        self.assertLess(len(raw), 2000)

    def test_kontur_mit_aussparungen(self):
        contour = [(i * 100.0, i * 100.0) for i in range(40)]
        openings = [[(i * 10.0, i * 10.0) for i in range(8)] for _ in range(6)]
        raw = encode_state((0, 0, 0), contour, openings, openings, 0.0, None)

        self.assertLess(len(raw), 6000)
        self.assertIsNotNone(decode_state(raw))


if __name__ == '__main__':
    unittest.main()
