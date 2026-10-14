#!/usr/bin/env python3
# Copyright (C) 2026 The MegaMek Team. SPDX-License-Identifier: GPL-3.0-or-later
"""Intrinsic lava-channel boundaries; the full deterministic bake is checked separately."""
import unittest

import numpy as np

from build_magma_materials import finish_lava


class LavaSkinTest(unittest.TestCase):
    def material(self):
        return {'lava.png': np.array([[[0, 0, 0], [0, 0, 0]],
                                     [[96, 112, 128], [64, 80, 96]]], dtype=np.uint8),
                'lava-surface.png': np.array([[[0, 50, 180, 13], [255, 50, 200, 13]],
                                             [[0, 253, 210, 13], [128, 253, 220, 13]]], dtype=np.uint8),
                'lava-heat.png': np.array([[[0, 2, 3, 4], [255, 5, 6, 7]],
                                          [[0, 8, 9, 10], [255, 11, 12, 13]]], dtype=np.uint8),
                'lava-normal.png': np.full((2, 2, 3), 128, dtype=np.uint8)}

    def test_cold_floor_is_linear_and_hot_skin_keeps_authored_black(self):
        maps = self.material()
        finish_lava(maps)
        # Cold height-zero floor is .025*.7 = .0175 linear, encoded once into the color image.
        code = round((1.055 * .0175 ** (1 / 2.4) - .055) * 255)
        np.testing.assert_array_equal(maps['lava.png'][0, 0], [code] * 3)
        np.testing.assert_array_equal(maps['lava.png'][0, 1], [0, 0, 0])
        self.assertEqual(round(.96 * 255), int(maps['lava-surface.png'][0, 0, 1]))
        self.assertEqual(round(.92 * 255), int(maps['lava-surface.png'][0, 1, 1]))

    def test_authored_values_above_floor_and_every_other_channel_survive(self):
        maps = self.material()
        before = {name: data.copy() for name, data in maps.items()}
        finish_lava(maps)
        np.testing.assert_array_equal(maps['lava.png'][1], before['lava.png'][1])
        np.testing.assert_array_equal(maps['lava-surface.png'][1, :, 1], [253, 253])
        np.testing.assert_array_equal(maps['lava-surface.png'][..., [0, 2, 3]],
                                      before['lava-surface.png'][..., [0, 2, 3]])
        for name in ('lava-normal.png', 'lava-heat.png'):
            np.testing.assert_array_equal(maps[name], before[name])

    def test_partial_exposure_stays_between_cold_and_hot_material(self):
        maps = self.material()
        maps['lava-heat.png'][0, 0, 0] = 115
        finish_lava(maps)
        self.assertTrue(0 < int(maps['lava.png'][0, 0, 0]) < 36)
        self.assertTrue(round(.92 * 255) < int(maps['lava-surface.png'][0, 0, 1]) < round(.96 * 255))


if __name__ == '__main__':
    unittest.main()
