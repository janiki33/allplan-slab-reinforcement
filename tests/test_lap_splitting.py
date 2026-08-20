"""Tests für die Stosslogik (ohne Allplan lauffähig)."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'PythonPartsScripts' / 'SlabReinforcement'))

from lap_splitting import (clamp_joint_shift, joint_positions, required_piece_count,
                           split_bar_with_laps, split_with_preferred_joints)


class RequiredPieceCountTest(unittest.TestCase):

    def test_short_bar_needs_no_lap(self):
        self.assertEqual(required_piece_count(7000, 8000, 600), 1)
        self.assertEqual(required_piece_count(8000, 8000, 600), 1)

    def test_two_pieces(self):
        self.assertEqual(required_piece_count(8001, 8000, 600), 2)
        self.assertEqual(required_piece_count(15000, 8000, 600), 2)

    def test_three_pieces(self):
        # 2 Stäbe könnten nur 2*8000 - 600 = 15400 abdecken
        self.assertEqual(required_piece_count(15500, 8000, 600), 3)

    def test_lap_longer_than_bar_is_rejected(self):
        with self.assertRaises(ValueError):
            required_piece_count(20000, 500, 600)


class SplitBarWithLapsTest(unittest.TestCase):

    def test_no_split_below_max_length(self):
        self.assertEqual(split_bar_with_laps((0, 7000), 8000, 600), [(0, 7000)])

    def test_pieces_cover_the_full_bar(self):
        pieces = split_bar_with_laps((0, 20000), 8000, 600)

        self.assertEqual(pieces[0][0], 0)
        self.assertEqual(pieces[-1][1], 20000)

    def test_every_piece_within_max_length(self):
        pieces = split_bar_with_laps((0, 20000), 8000, 600)

        for piece_from, piece_to in pieces:
            self.assertLessEqual(piece_to - piece_from, 8000 + 1e-6)

    def test_consecutive_pieces_overlap_by_lap_length(self):
        pieces = split_bar_with_laps((0, 20000), 8000, 600)

        for previous, following in zip(pieces, pieces[1:]):
            self.assertAlmostEqual(previous[1] - following[0], 600, places=6)

    def test_equal_pieces_without_shift(self):
        pieces = split_bar_with_laps((0, 20000), 8000, 600)
        lengths = [round(piece_to - piece_from, 6) for piece_from, piece_to in pieces]

        self.assertEqual(len(set(lengths)), 1)

    def test_shift_moves_all_joints(self):
        plain = split_bar_with_laps((0, 20000), 8000, 600)
        shifted = split_bar_with_laps((0, 20000), 8000, 600, joint_shift=300)

        for a, b in zip(joint_positions(plain, 600), joint_positions(shifted, 600)):
            self.assertAlmostEqual(b - a, 300, places=6)

        self.assertEqual(shifted[0][0], 0)
        self.assertEqual(shifted[-1][1], 20000)

    def test_shift_is_clamped_to_max_bar_length(self):
        pieces = split_bar_with_laps((0, 20000), 8000, 600, joint_shift=99999)

        for piece_from, piece_to in pieces:
            self.assertLessEqual(piece_to - piece_from, 8000 + 1e-6)

    def test_clamp_returns_zero_without_room(self):
        # Grundlänge = Maximallänge -> kein Spielraum
        self.assertEqual(clamp_joint_shift(500, 8000, 8000, 600), 0.0)

    def test_empty_segment(self):
        self.assertEqual(split_bar_with_laps((100, 100), 8000, 600), [])



class ForbiddenZoneTest(unittest.TestCase):

    def test_joint_is_moved_out_of_the_zone(self):
        # Ohne Verschiebung läge die Stossmitte bei 10000
        plain = split_bar_with_laps((0, 20000), 12000, 600)
        self.assertAlmostEqual(joint_positions(plain, 600)[0], 10000, delta=200)

        pieces = split_with_preferred_joints((0, 20000), 12000, 600,
                                             forbidden_zones=[(9000, 11000)])

        for joint in joint_positions(pieces, 600):
            self.assertFalse(9000 <= joint <= 11000)

    def test_pieces_stay_valid_after_avoiding_a_zone(self):
        pieces = split_with_preferred_joints((0, 20000), 12000, 600,
                                             forbidden_zones=[(9000, 11000)])

        self.assertEqual(pieces[0][0], 0)
        self.assertEqual(pieces[-1][1], 20000)

        for piece_from, piece_to in pieces:
            self.assertLessEqual(piece_to - piece_from, 12000 + 1e-6)

    def test_preferred_shift_is_kept_when_no_zone_is_hit(self):
        with_zone = split_with_preferred_joints((0, 20000), 12000, 600,
                                                preferred_shift=400,
                                                forbidden_zones=[(0, 100)])
        without_zone = split_bar_with_laps((0, 20000), 12000, 600, joint_shift=400)

        self.assertEqual(with_zone, without_zone)

    def test_no_zones_behaves_like_plain_split(self):
        self.assertEqual(split_with_preferred_joints((0, 20000), 8000, 600),
                         split_bar_with_laps((0, 20000), 8000, 600))


if __name__ == '__main__':
    unittest.main()
